import logging
from datetime import datetime
import requests
import re
import time
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

def prepare_agent(agent_cfg: dict, config: dict):
    """Populate common runtime attributes onto an agent configuration."""
    agent_cfg["base_url"] = config["api_base_url"]
    agent_cfg["endpoint"] = config["default_endpoint"]


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


def _run_2of3_sequential(agents: list, payload_builder, config: dict, agent_type: str) -> list:
    """Sequential execution with early-exit optimization (original behavior)."""
    results = []
    logging.info(f"Running {agent_type} agents (sequential)")

    for idx, agent in enumerate(agents):
        # Early exit check: if first two agents agree, skip the third
        if idx == 2 and len(results) == 2:
            if results[0]["isvalid"] == results[1]["isvalid"]:
                logging.info(f"Early exit: first two {agent_type} agents agree, skipping third agent")
                break  # Consensus already achieved

        prepare_agent(agent, config)
        payload = payload_builder(agent, config)

        # Validate no placeholders remain
        if not validate_no_placeholders(payload["request"]):
            logging.error(f"Unreplaced placeholders in {agent_type} request for agent {agent.get('name')}")
            results.append({"isvalid": False, "invalid_msg": "Unreplaced placeholders in request"})
            continue

        logging.debug(f"Payload for {agent_type} agent {agent.get('name')}: {payload}")

        message = run_agent(agent, payload)
        if "error" in message:
            logging.error(f"Agent {agent.get('name')} failed: {message['error']}")
            results.append({"isvalid": False, "invalid_msg": f"Agent error: {message['error']}"})
        else:
            parsed = parse_isvalid(message.get("content", ""))
            results.append(parsed)

        # After the second agent, check for early consensus
        if idx == 1 and results[0]["isvalid"] == results[1]["isvalid"]:
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

    This saves API calls 70-80% of the time while maintaining parallelism benefits.
    """
    max_workers = config.get("max_parallel_workers", 3)
    logging.info(f"Running {agent_type} agents (parallel mode)")

    def run_single_agent(idx, agent):
        """Execute a single agent and return (index, result)."""
        prepare_agent(agent, config)
        payload = payload_builder(agent, config)

        # Validate no placeholders remain
        if not validate_no_placeholders(payload["request"]):
            logging.error(f"Unreplaced placeholders in {agent_type} request for agent {agent.get('name')}")
            return (idx, {"isvalid": False, "invalid_msg": "Unreplaced placeholders in request"})

        logging.debug(f"Payload for {agent_type} agent {agent.get('name')}: {payload}")

        message = run_agent(agent, payload)
        if "error" in message:
            logging.error(f"Agent {agent.get('name')} failed: {message['error']}")
            return (idx, {"isvalid": False, "invalid_msg": f"Agent error: {message['error']}"})
        else:
            parsed = parse_isvalid(message.get("content", ""))
            return (idx, parsed)

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
    if result_0["isvalid"] == result_1["isvalid"]:
        logging.info(f"Early consensus: first 2 {agent_type} agents agree ({result_0['isvalid']}), skipping 3rd agent")
        return results  # Consensus reached, no need for 3rd agent

    # Phase 3: Disagreement - run 3rd agent as tie-breaker
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

    url = agent_config["base_url"] + agent_config["endpoint"]
    headers = {"Content-Type": "application/json"}

    model = agent_config.get("model", agent_config["default_model"])
    temperature = agent_config.get("temperature", agent_config["default_temperature"])

    # Create the messages structure.
    messages = []
    system_msg = {"role":"system", "content": payload.get("instructions")}
    messages.append(system_msg)

    user_query = {"role":"user", "content":payload.get("request")}
    messages.append(user_query)

    # create the json payload
    json_payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": -1,
        "stream": False,
        "messages": messages
    }

    # Retry loop with exponential backoff
    last_error = None
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=json_payload, headers=headers, timeout=timeout)
            response.raise_for_status()  # Raise HTTPError for bad responses

            result = response.json()["choices"][0]["message"]

            # Add performance metadata
            elapsed_time = time.time() - start_time
            result["_metadata"] = {
                "agent_name": agent_config.get("name"),
                "agent_role": agent_config.get("role"),
                "elapsed_time": round(elapsed_time, 2),
                "model": model,
                "temperature": temperature,
                "retry_count": attempt
            }
            logging.info(f"Agent {agent_config.get('name')} completed in {elapsed_time:.2f}s (attempt {attempt + 1}/{max_retries})")

            return result

        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = backoff ** attempt
                logging.warning(f"Agent {agent_config.get('name')} failed (attempt {attempt + 1}/{max_retries}), "
                              f"retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                # Final attempt failed
                elapsed_time = time.time() - start_time
                logging.error(f"Agent {agent_config.get('name')} failed after {max_retries} attempts ({elapsed_time:.2f}s): {e}")

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

def get_str_between_tags(s_value: str, start_tag: str, end_tag: str) -> str | None:
    """
    Extracts the string between the specified start and end tags.

    Args:
        s_value: The string to search within.
        start_tag: The opening tag (e.g., "<isvalid>").
        end_tag: The closing tag (e.g., "</isvalid>").

    Returns:
        The string between the tags if both are found, otherwise None.
    """

    # Escape special characters in the tags
    start_tag = re.escape(start_tag) 
    end_tag = re.escape(end_tag) 

    match = re.search(f"{start_tag}(.*?){end_tag}", s_value, re.DOTALL | re.IGNORECASE)

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

    isvalid_text = get_str_between_tags(result_string, "<isvalid>", "</isvalid>")
    if isvalid_text:
        result["isvalid"] = isvalid_text.lower() == "true"

    invalid_msg = get_str_between_tags(result_string, "<invalid_msg>", "</invalid_msg>")
    if invalid_msg:
        result["invalid_msg"] = invalid_msg

    return result


