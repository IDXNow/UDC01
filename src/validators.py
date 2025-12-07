import logging
from datetime import datetime
import requests
import re
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

################################################################################
# Helper functions                                                             #
################################################################################
def validate_no_placeholders(text: str) -> bool:
    """Check if any unreplaced placeholders remain."""
    placeholders = ["{<!--Data-->}", "{<!--DateTime-->}", "{<!--RunIndex-->}", "{<!--Output-->}"]
    for ph in placeholders:
        if ph in text:
            logging.error(f"Unreplaced placeholder found: {ph}")
            return False
    return True

def prepare_agent(agent_cfg: dict, config: dict):
    """Populate common runtime attributes onto an agent configuration."""
    agent_cfg["base_url"] = config["api_base_url"]
    agent_cfg["endpoint"] = config["default_endpoint"]


def verify_input_data_2of3(raw_data: str, config: dict) -> list:
    """Run the data-verification agents using the 2/3 strategy
    - We always execute the first two agents.
    - If their <isvalid> results agree we *stop* - consensus reached.
    - If they disagree (one True, one False) we execute the third agent to break the tie.
    The function returns a list of parsed verification dictionaries - one for every agent *actually run* (two or three).
    """
    agents = config["agents"]["data_verifier"]
    results = []
    logging.info(f"Verifying input data") # comment

    for idx, agent in enumerate(agents):
        if idx == 2 and len(results) == 2:
            # Only reach here when the first two results were opposing.
            same = results[0]["isvalid"] == results[1]["isvalid"]
            if same:
                break  # No need to run the third agent.
        prepare_agent(agent, config)
        payload = {
            "request": config.get(agent.get("request_instructions"), "")
            .replace("{<!--Data-->}", raw_data)
            .replace("{<!--DateTime-->}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "instructions": config.get(agent.get("instructions"), ""),
        }

        # Validate no placeholders remain
        if not validate_no_placeholders(payload["request"]):
            logging.error(f"Unreplaced placeholders in verification request for agent {agent.get('name')}")
            results.append({"isvalid": False, "invalid_msg": "Unreplaced placeholders in request"})
            continue

        logging.debug(
            f"Payload for verification agent {agent.get('name')}: {payload}"
        )
        message = run_agent(agent, payload)
        if "error" in message:
            logging.error(f"Agent {agent.get('name')} failed: {message['error']}")
            results.append({"isvalid": False, "invalid_msg": f"Agent error: {message['error']}"})
        else:
            parsed = parse_isvalid(message.get("content", ""))
            results.append(parsed)

        # After the second agent, decide if we need a tie‑breaker.
        if idx == 1 and results[0]["isvalid"] == results[1]["isvalid"]:
            break  # Consensus (both True or both False).
    return results


def validate_output_2of3(raw_data: str, output_data: str, config: dict) -> list:
    """Run the data-validation agents using the same 2/3 early-exit logic"""
    agents = config["agents"]["data_validator"]
    results = []
    logging.info(f"Validating output data") # comment

    for idx, agent in enumerate(agents):
        if idx == 2 and len(results) == 2:
            if results[0]["isvalid"] == results[1]["isvalid"]:
                break  # consensus already achieved
        prepare_agent(agent, config)
        payload = {
            "instructions": config.get(agent.get("instructions"), ""),
            "request": config.get(agent.get("request_instructions"), "")
            .replace("{<!--Data-->}", raw_data)
            .replace("{<!--Output-->}", output_data)
            .replace("{<!--DateTime-->}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        }

        # Validate no placeholders remain
        if not validate_no_placeholders(payload["request"]):
            logging.error(f"Unreplaced placeholders in validation request for agent {agent.get('name')}")
            results.append({"isvalid": False, "invalid_msg": "Unreplaced placeholders in request"})
            continue

        logging.debug(
            f"Payload for validation agent {agent.get('name')}: {payload}"
        )
        message = run_agent(agent, payload)
        if "error" in message:
            logging.error(f"Agent {agent.get('name')} failed: {message['error']}")
            results.append({"isvalid": False, "invalid_msg": f"Agent error: {message['error']}"})
        else:
            parsed = parse_isvalid(message.get("content", ""))
            results.append(parsed)

        if idx == 1 and results[0]["isvalid"] == results[1]["isvalid"]:
            break  # early consensus
    return results


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


