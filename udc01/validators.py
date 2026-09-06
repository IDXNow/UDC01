import logging
from datetime import datetime
import requests
import re
import time
from concurrent.futures import ThreadPoolExecutor

################################################################################
# Helper functions                                                             #
################################################################################
def validate_no_placeholders(text: str) -> bool:
    """Check if any unreplaced placeholders remain."""
    placeholders = ["{<!--Data-->}", "{<!--DateTime-->}", "{<!--RunIndex-->}", "{<!--Output-->}", "{<!--PreviousConversionNotes-->}"]
    for ph in placeholders:
        if ph in text:
            logging.error(f"Unreplaced placeholder found: {ph}")
            return False
    return True

def get_provider(agent_config: dict) -> str:
    """Determines the provider for an agent (explicit or default)."""
    return agent_config.get("provider", agent_config.get("default_provider", "local"))

def build_provider_url(provider_config: dict, model: str) -> str:
    """Builds the full API URL for the provider."""
    base_url = provider_config["base_url"]
    endpoint = provider_config["endpoint"]

    # Google requires model name in URL path
    if "{model}" in endpoint:
        model_name = model.split("/")[-1] if "/" in model else model
        endpoint = endpoint.replace("{model}", model_name)

    # Ensure no double slashes
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    return base_url + endpoint

def build_provider_headers(provider: str, provider_config: dict, api_keys: dict) -> dict:
    """Builds authentication headers for the provider."""
    headers = {"Content-Type": "application/json"}

    auth_header = provider_config.get("auth_header")
    if auth_header:
        api_key = api_keys.get(provider, "")
        if api_key:
            auth_prefix = provider_config.get("auth_prefix", "")
            if auth_prefix:
                headers[auth_header] = f"{auth_prefix} {api_key}"
            else:
                headers[auth_header] = api_key

            # Debug logging (show first/last 4 chars of key for security)
            key_preview = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
            logging.debug(f"Auth header for '{provider}': {auth_header}={auth_prefix} {key_preview}".strip())
        else:
            logging.warning(f"No API key found for provider '{provider}' - request may fail")

    # Anthropic-specific version header
    if "version_header" in provider_config:
        headers[provider_config["version_header"]] = provider_config["version"]

    return headers

def format_request_for_provider(
        provider_config: dict, model: str,
        temperature: float, messages: list,
        thinking_budget: int = None,
        reasoning_effort: str = None,
        max_tokens: int = None,
        supports_temperature: bool = None,
        token_param: str = None) -> dict:
    """Formats the request payload for specific provider."""
    request_format = provider_config.get("request_format", "openai")

    # Resolved values win; the provider profile is the fallback for direct callers
    if supports_temperature is None:
        supports_temperature = provider_config.get("supports_temperature", True)
    if token_param is None:
        token_param = provider_config.get("token_param", "max_tokens")

    if reasoning_effort is not None and thinking_budget is not None:
        logging.warning(f"Both reasoning_effort and thinking_budget set for '{request_format}' - using reasoning_effort")
        thinking_budget = None

    # Current models reject or ignore sampling params
    if not supports_temperature:
        temperature = None

    if request_format == "anthropic":
        # Anthropic uses different format: separate system message from messages array
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_messages = [m for m in messages if m["role"] != "system"]
        payload = {
            "model": model,
            "max_tokens": max_tokens if max_tokens is not None else 120000,
            "system": system_msg,
            "messages": user_messages
        }
        if reasoning_effort is not None:
            # Current models: adaptive thinking, depth set by effort level
            payload["thinking"] = {"type": "adaptive"}
            payload["output_config"] = {"effort": reasoning_effort}
        elif thinking_budget is not None:
            # Legacy form for pre-4.6 models: temperature is forced to 1 by the API
            payload["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
            payload["temperature"] = 1
        elif temperature is not None:
            payload["temperature"] = temperature
        return payload
    elif request_format == "google":
        # Google Gemini uses different format: contents with parts
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        contents = []
        for msg in messages:
            if msg["role"] == "system":
                continue
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        gen_config = {}
        if max_tokens is not None:
            gen_config["maxOutputTokens"] = max_tokens
        if temperature is not None:
            gen_config["temperature"] = temperature
        if reasoning_effort is not None:
            gen_config["thinkingConfig"] = {"thinkingLevel": reasoning_effort}
        elif thinking_budget is not None:
            gen_config["thinkingConfig"] = {"thinkingBudget": thinking_budget}
        payload = {
            "contents": contents,
            "generationConfig": gen_config
        }
        if system_msg:
            payload["systemInstruction"] = {"parts": [{"text": system_msg}]}
        return payload
    else:
        # OpenAI format (default for local and openai providers)
        payload = {
            "model": model,
            "stream": False,
            "messages": messages
        }
        if max_tokens is not None:
            # GPT-5.x requires max_completion_tokens; local servers still want max_tokens
            payload[token_param] = max_tokens
        if reasoning_effort is not None:
            # Reasoning models: reasoning_effort replaces temperature
            payload["reasoning_effort"] = reasoning_effort
        elif temperature is not None:
            payload["temperature"] = temperature
        return payload

REASONING_TAGS = ("think", "thinking", "reasoning")


def strip_reasoning_blocks(text: str) -> str:
    """Removes <think>-style blocks so reasoning can't reach the tag extractors."""
    if not text:
        return ""

    for tag in REASONING_TAGS:
        text = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Some templates prefill the opening tag, so only the closer arrives - drop the lead-in
    for tag in REASONING_TAGS:
        closers = list(re.finditer(rf"</{tag}>", text, re.IGNORECASE))
        if closers:
            text = text[closers[-1].end():]

    # An unclosed opener means the response was cut off mid-thought; nothing usable follows
    for tag in REASONING_TAGS:
        if re.search(rf"<{tag}\b[^>]*>", text, re.IGNORECASE):
            return ""

    return text.strip()


def parse_provider_response(provider_config: dict, response_data: dict) -> dict:
    """Parses provider-specific response to standard format."""
    request_format = provider_config.get("request_format", "openai")

    if request_format == "anthropic":
        # Thinking blocks precede the answer, so scan rather than assume position 0
        blocks = response_data.get("content", [])
        text = next((b.get("text") for b in blocks if b.get("type") == "text"), None)
        if text is None:
            stop_reason = response_data.get("stop_reason", "unknown")
            raise ValueError(f"No text block in Anthropic response (stop_reason: {stop_reason})")
        return {"role": "assistant", "content": text}
    elif request_format == "google":
        candidates = response_data.get("candidates", [])
        if not candidates:
            raise ValueError("No candidates in Gemini response")
        # A blocked or truncated candidate can carry no parts at all
        parts = candidates[0].get("content", {}).get("parts", [])
        text = next((p["text"] for p in parts if "text" in p and not p.get("thought")), None)
        if text is None:
            finish_reason = candidates[0].get("finishReason", "unknown")
            raise ValueError(f"No text part in Gemini response (finishReason: {finish_reason})")
        return {"role": "assistant", "content": text}
    else:
        # OpenAI format (default)
        choices = response_data.get("choices", [])
        if not choices:
            raise ValueError("No choices in response")
        message = dict(choices[0].get("message") or {})
        finish_reason = choices[0].get("finish_reason", "unknown")

        # LM Studio returns reasoning_content, Ollama returns reasoning - keep both out of content
        for field in ("reasoning_content", "reasoning"):
            if field in message:
                message["_reasoning"] = message.pop(field)
                break

        content = message.get("content") or ""
        if content and provider_config.get("strip_reasoning", True):
            stripped = strip_reasoning_blocks(content)
            if not stripped:
                logging.warning(
                    f"Response was entirely reasoning, no answer returned "
                    f"(finish_reason: {finish_reason}, {len(content)} chars)"
                )
            message["content"] = stripped
        return message

def prepare_agent(agent_cfg: dict, config: dict):
    """Fill in default runtime attributes only if not already set by config injection."""
    agent_cfg.setdefault("default_model", config.get("default_model", ""))
    agent_cfg.setdefault("default_temperature", config.get("default_temperature"))
    agent_cfg.setdefault("default_supports_temperature", config.get("supports_temperature", True))
    agent_cfg.setdefault("default_token_param", config.get("token_param", "max_tokens"))


def run_2of3_consensus(agents: list, payload_builder, config: dict, agent_type: str) -> list:
    """
    Generic 2/3 consensus runner with early-exit optimization and optional parallelism.

    Args:
        agents: List of agent configurations
        payload_builder: Callable that builds the payload for each agent
        config: Global configuration dict
        agent_type: Type of agent for logging (e.g., "verification", "validation")

    Returns:
        List of parsed results from agents that were actually run (2 or 3)
    """
    parallel_enabled = config.get("parallel_agents", False)

    if parallel_enabled:
        return _run_2of3_parallel(agents, payload_builder, config, agent_type)
    else:
        return _run_2of3_sequential(agents, payload_builder, config, agent_type)


def _agent_failure(reason: str) -> dict:
    """Build a result for an agent that never produced a usable verdict."""
    return {"isvalid": False, "failed": True, "invalid_msg": reason}


def _parse_verdict(message: dict, agent: dict, agent_type: str) -> dict:
    """Parse an agent response into a verdict, or a failure when it's not present."""
    content = message.get("content") or ""
    parsed = parse_isvalid(content)

    if "isvalid" not in parsed:
        model = message.get("_metadata", {}).get("model", "unknown")
        logging.error(
            f"{agent_type} agent {agent.get('name')} ({model}) returned no <isvalid> "
            f"verdict in {len(content)} chars of content"
        )
        return _agent_failure(
            f"Agent {agent.get('name')} returned no <isvalid> verdict "
            f"({len(content)} chars received)"
        )

    return parsed


def _run_2of3_sequential(agents: list, payload_builder, config: dict, agent_type: str) -> list:
    """Sequential execution with early-exit optimization (original behavior)."""
    results = []
    
    if config.get("log_details", False):
        logging.info(f"Running {agent_type} agents (sequential)")

    for idx, agent in enumerate(agents):
        # Early exit check: if first two agents agree, skip the third
        if idx == 2 and len(results) == 2:
            if results[0].get("isvalid") == results[1].get("isvalid"):
                if config.get("log_details", False):
                    logging.info(f"Early exit: first two {agent_type} agents agree, skipping third agent")
                break  # Outcome already determined

        prepare_agent(agent, config)
        payload = payload_builder(agent, config)

        # Validate no placeholders remain
        if config.get("validate_placeholders", True) and not validate_no_placeholders(payload["request"]):
            logging.error(f"Unreplaced placeholders in {agent_type} request for agent {agent.get('name')}")
            results.append(_agent_failure("Unreplaced placeholders in request"))
            continue

        if config.get("log_details", False):
            logging.debug(f"Payload for {agent_type} agent {agent.get('name')}: {payload}")

        message = run_agent(agent, payload)
        if "error" in message:
            logging.error(f"Agent {agent.get('name')} failed: {message['error']}")
            results.append(_agent_failure(f"Agent error: {message['error']}"))
        else:
            results.append(_parse_verdict(message, agent, agent_type))

        # After the second agent, check for early consensus
        if idx == 1 and results[0].get("isvalid") == results[1].get("isvalid"):
            if config.get("log_details", False):
                logging.info(f"Early exit: first two {agent_type} agents agree")
            break  # Consensus (both True or both False)

    return results


def _run_2of3_parallel(agents: list, payload_builder, config: dict, agent_type: str) -> list:
    """
    Optimized parallel execution: Run first 2 agents in parallel, then decide if 3rd is needed.

    Strategy:
    1. Launch first 2 agents in parallel
    2. If they agree → Done! (consensus reached)
    3. If they disagree → Launch 3rd agent as tie-breaker

    """
    max_workers = config.get("max_parallel_workers", 3)
    if config.get("log_details", False):
        logging.info(f"Running {agent_type} agents (parallel mode)")

    def run_single_agent(idx, agent):
        """Execute a single agent and return (index, result)."""
        prepare_agent(agent, config)
        payload = payload_builder(agent, config)

        # Validate no placeholders remain
        if config.get("validate_placeholders", True) and not validate_no_placeholders(payload["request"]):
            logging.error(f"Unreplaced placeholders in {agent_type} request for agent {agent.get('name')}")
            return (idx, _agent_failure("Unreplaced placeholders in request"))

        if config.get("log_details", False):
            logging.debug(f"Payload for {agent_type} agent {agent.get('name')}: {payload}")

        message = run_agent(agent, payload)
        if "error" in message:
            logging.error(f"Agent {agent.get('name')} failed: {message['error']}")
            return (idx, _agent_failure(f"Agent error: {message['error']}"))
        else:
            return (idx, _parse_verdict(message, agent, agent_type))

    results = []

    # Phase 1: Run first 2 agents in parallel
    with ThreadPoolExecutor(max_workers=min(2, max_workers)) as executor:
        future_0 = executor.submit(run_single_agent, 0, agents[0])
        future_1 = executor.submit(run_single_agent, 1, agents[1])

        # Wait for both to complete
        idx_0, result_0 = future_0.result()
        idx_1, result_1 = future_1.result()

    results.append(result_0)
    results.append(result_1)

    # Phase 2: Check if first 2 agents agree
    if result_0.get("isvalid") == result_1.get("isvalid"):
        if config.get("log_details", False):
            logging.info(f"Early consensus: first 2 {agent_type} agents agree ({result_0.get('isvalid')}), skipping 3rd agent")
        return results  # Consensus reached, no need for 3rd agent

    # Phase 3: Disagreement - run 3rd agent as tie-breaker
    if config.get("log_details", False):
        logging.info(f"First 2 {agent_type} agents disagree, running 3rd agent as tie-breaker")
    idx_2, result_2 = run_single_agent(2, agents[2])
    results.append(result_2)

    return results


def verify_input_data_2of3(raw_data: str, config: dict) -> list:
    """Run the data-verification agents using the 2/3 strategy.
    Returns a list of parsed verification dictionaries - one for every agent actually run (two or three).
    """
    agents = config["agents"]["data_verifier"]

    def build_verification_payload(agent, config):
        return {
            "request": config.get(agent.get("request_instructions"), "")
            .replace("{<!--Data-->}", raw_data)
            .replace("{<!--DateTime-->}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "instructions": config.get(agent.get("instructions"), ""),
        }

    return run_2of3_consensus(agents, build_verification_payload, config, "verification")


def validate_output_2of3(raw_data: str, output_data: str, config: dict) -> list:
    """Run the data-validation agents using the 2/3 strategy.
    Returns a list of parsed validation dictionaries - one for every agent actually run (two or three).
    """
    agents = config["agents"]["data_validator"]

    def build_validation_payload(agent, config):
        return {
            "request": config.get(agent.get("request_instructions"), "")
            .replace("{<!--Data-->}", raw_data)
            .replace("{<!--Output-->}", output_data)
            .replace("{<!--DateTime-->}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "instructions": config.get(agent.get("instructions"), ""),
        }

    return run_2of3_consensus(agents, build_validation_payload, config, "validation")


def run_agent(agent_config: dict, payload: dict) -> dict:
    """Calls the specified LLM agent with the given payload with retry logic."""
    start_time = time.time()

    max_retries = agent_config.get("retry_attempts", 3)
    backoff = agent_config.get("retry_backoff", 2)
    timeout = agent_config.get("timeout", 600)

    # Determine provider and get provider configuration
    provider = get_provider(agent_config)
    providers = agent_config.get("providers", {})

    # determine model: agent's explicit model --> resolved default --> provider profile (uninjected agents)
    if "model" in agent_config:
        model = agent_config["model"]
    elif agent_config.get("default_model"):
        model = agent_config["default_model"]
    elif provider in providers and "default_model" in providers[provider]:
        model = providers[provider]["default_model"]
    else:
        model = "openai/gpt-oss-20b"

    temperature = agent_config.get("temperature", agent_config.get("default_temperature"))
    thinking_budget = agent_config.get("thinking_budget", agent_config.get("default_thinking_budget"))
    reasoning_effort = agent_config.get("reasoning_effort", agent_config.get("default_reasoning_effort"))
    max_tokens = agent_config.get("max_tokens", agent_config.get("default_max_tokens"))
    supports_temperature = agent_config.get("supports_temperature", agent_config.get("default_supports_temperature"))
    token_param = agent_config.get("token_param", agent_config.get("default_token_param"))

    if provider not in providers:
        logging.error(f"Provider '{provider}' not found in configuration")
        return {
            "error": f"Provider '{provider}' not configured",
            "_metadata": {
                "agent_name": agent_config.get("name"),
                "failed": True
            }
        }

    provider_config = providers[provider]
    api_keys = agent_config.get("api_keys", {})

    # Build provider-specific URL and headers
    url = build_provider_url(provider_config, model)
    headers = build_provider_headers(provider, provider_config, api_keys)

    # Create the messages structure.
    messages = []
    system_msg = {"role":"system", "content": payload.get("instructions")}
    messages.append(system_msg)

    user_query = {"role":"user", "content":payload.get("request")}
    messages.append(user_query)

    # Create provider-specific request payload
    json_payload = format_request_for_provider(
        provider_config, model, temperature, messages,
        thinking_budget=thinking_budget,
        reasoning_effort=reasoning_effort,
        max_tokens=max_tokens,
        supports_temperature=supports_temperature,
        token_param=token_param
    )

    # Retry loop with exponential backoff
    last_error = None
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=json_payload, headers=headers, timeout=timeout)
            response.raise_for_status()  # Raise HTTPError for bad responses

            # Parse provider-specific response
            result = parse_provider_response(provider_config, response.json())

            # Add performance metadata
            elapsed_time = time.time() - start_time
            result["_metadata"] = {
                "agent_name": agent_config.get("name"),
                "agent_role": agent_config.get("role"),
                "elapsed_time": round(elapsed_time, 2),
                "model": model,
                "temperature": temperature,
                "thinking_budget": thinking_budget,
                "reasoning_effort": reasoning_effort,
                "provider": provider,
                "retry_count": attempt
            }
            
            # print(f"Agent {agent_config.get('name')} ({provider}/{model}) completed in {elapsed_time:.2f}s (attempt {attempt + 1}/{max_retries})") # --> testing
            logging.debug(f"Agent {agent_config.get('name')} ({provider}/{model}) completed in {elapsed_time:.2f}s (attempt {attempt + 1}/{max_retries})")

            return result

        except (requests.exceptions.RequestException, KeyError, IndexError, ValueError, TypeError) as e:
            # Response-shape errors are caught too, so they retry and report like any other failure
            last_error = e
            # get detailed error message from response
            error_detail = f"{type(e).__name__}: {e}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_json = e.response.json()
                    if 'error' in error_json:
                        
                        err = error_json['error']
                        if isinstance(err, dict):
                            msg = err.get('message', err)
                            # Google returns 'status' where OpenAI/Anthropic return 'type'
                            error_type = err.get('type', err.get('status', 'unknown'))
                            error_code = err.get('code', '')
                            error_detail = f"{e}\n  Error Type: {error_type}\n  Message: {msg}"
                            if error_code:
                                error_detail += f"\n  Code: {error_code}"
                        else:
                            error_detail = f"{e} - Error: {err}"
                except Exception:
                    # If JSON parsing fails, show raw response
                    error_detail = f"{e}\n  Raw Response: {e.response.text[:500]}"

            if attempt < max_retries - 1:
                wait_time = backoff ** attempt
                logging.warning(f"Agent {agent_config.get('name')} failed (attempt {attempt + 1}/{max_retries}), "
                              f"retrying in {wait_time}s: {error_detail}")
                time.sleep(wait_time)
            else:
                # Final attempt failed
                elapsed_time = time.time() - start_time
                logging.error(f"Agent {agent_config.get('name')} failed after {max_retries} attempts ({elapsed_time:.2f}s): {error_detail}")

    # All retries exhausted
    elapsed_time = time.time() - start_time
    return {
        "error": str(last_error),
        "_metadata": {
            "agent_name": agent_config.get("name"),
            "elapsed_time": round(elapsed_time, 2),
            "failed": True,
            "retry_count": max_retries
        }
    }

def get_str_between_tags(s_value: str, start_tag: str, end_tag: str, first_last: bool = False, last: bool = False) -> str | None:
    """
    Extracts the string between the specified start and end tags.

    Args:
        s_value: The string to search within.
        start_tag: The opening tag (e.g., "<isvalid>").
        end_tag: The closing tag (e.g., "</isvalid>").
        first_last: Span from the first start tag to the last end tag.
        last: Return the last tag pair rather than the first.

    Returns:
        The string between the tags if both are found, otherwise None.
    """

    if first_last:
        # Case-insensitive search
        s_lower = s_value.lower()
        start_lower = start_tag.lower()
        end_lower = end_tag.lower()

        # Find FIRST occurrence of start tag
        start_pos = s_lower.find(start_lower)
        if start_pos == -1:
            return None

        # Find LAST occurrence of end tag
        end_pos = s_lower.rfind(end_lower)
        if end_pos == -1 or end_pos <= start_pos:
            return None

        # Extract content between first start tag and last end tag
        content_start = start_pos + len(start_tag)
        content = s_value[content_start:end_pos]

        return content.strip()
    else:
        # Escape special characters in the tags
        start_tag = re.escape(start_tag) 
        end_tag = re.escape(end_tag) 

        pattern = f"{start_tag}(.*?){end_tag}"

        if last:
            # Reasoning models rehearse answers; the final tag pair is the real one
            matches = re.findall(pattern, s_value, re.DOTALL | re.IGNORECASE)
            return matches[-1].strip() if matches else None

        match = re.search(pattern, s_value, re.DOTALL | re.IGNORECASE)

        if match:
            return match.group(1).strip()
        else:
            return None


def parse_isvalid(result_string: str) -> dict:
    """
    Parses the result string from an agent and returns a dict with the <isvalid> and <invalid_msg> values, if present.
    Returns a dict.
    """
    result = {}

    isvalid_text = get_str_between_tags(result_string, "<isvalid>", "</isvalid>", last=True)
    if isvalid_text:
        result["isvalid"] = isvalid_text.lower() == "true"

    invalid_msg = get_str_between_tags(result_string, "<invalid_msg>", "</invalid_msg>", last=True)
    if invalid_msg:
        result["invalid_msg"] = invalid_msg

    return result


