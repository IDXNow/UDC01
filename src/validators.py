import logging
import random
from datetime import datetime
import requests
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_agent(agent_config: dict, payload: dict) -> dict:
    """Calls the specified LLM agent with the given payload."""

    try:
        url = agent_config["base_url"] + agent_config["endpoint"] # pull base url and endpoint from agent config
        headers = {"Content-Type": "application/json"}
        
        model = agent_config.get("model", agent_config["default_model"]) # get the agent model, or the default
        temperature = agent_config.get("temperature", agent_config["default_temperature"]) #get the agent temp, or the default
        
        # Create the messages structure.
        messages = []
        system_msg = {"role":"system", "content": payload.get("instructions")}
        messages.append(system_msg)

        user_query = {"role":"user", "content":payload.get("request")}
        messages.append(user_query)
        
        #create the json payload
        #update these parameters as needed (move to default config)
        json_payload = {
            "model": model,
            "temperature": temperature,
            "max_tokens": -1,
            "stream": False,
            "messages": messages
        }
        
        response = requests.post(url, json=json_payload, headers=headers, timeout=600) # set timeout as needed
        response.raise_for_status()  # Raise HTTPError for bad responses

        #logging.debug(f'payload: {json_payload}')
        #logging.debug(f'response: {response.json()["choices"][0]["message"]}')

        return response.json()["choices"][0]["message"] #just return the message
    except requests.exceptions.RequestException as e:
        logging.error(f"Error calling validation agent {agent_config.get('name')}: {e}")
        return {"error": str(e)}

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
    start_tag = re.escape(start_tag)  # Escape special characters in the start tag
    end_tag = re.escape(end_tag)      # Escape special characters in the end tag
    match = re.search(f"{start_tag}(.*?){end_tag}", s_value, re.DOTALL | re.IGNORECASE) #added re.DOTALL and re.IGNORECASE

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

def validate_output(raw_data: str, output_data: str, config: dict) -> list:
    """
    Run the Data Validation agents on the converted output to verify correctness.
    """

    base_url = config["api_base_url"]
    agents = config["agents"]["data_validator"]
    results = []

    for agent in agents:
        agent["base_url"] = base_url
        agent["endpoint"] = config["default_endpoint"] # for now
        payload = {
            "instructions": config.get(agent.get("instructions"),""),
            "request": config.get(agent.get("request_instructions"),"").replace("{<!--Data-->}",raw_data).replace("{<!--Output-->}",output_data).replace("{<!--DateTime-->}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        }
        
        logging.debug(f"Payload for validation agent {agent.get('name')}: {payload}")
        result = run_agent(agent, payload)
        logging.debug(f"Validation Result: {result}")
        result = parse_isvalid(result["content"])
        results.append(result)
        
    return results

def verify_input_data(raw_data: str, config: dict) -> list:
    """
    Run the Data Verification agents on the raw data to verify correctness before conversion.
    """
    agents = config["agents"]["data_verifier"]
    results = []
    
    for agent in agents:
        
        # add agent props
        agent["base_url"] = config["api_base_url"]
        agent["endpoint"] = config["default_endpoint"]
        
        payload = {
            "request": config.get(agent.get("request_instructions"),"").replace("{<!--Data-->}",raw_data),
            "instructions": config.get(agent.get("instructions"),"")
        }

        logging.debug(f"Payload for pre-verification agent {agent.get('name')}: {payload}")
        result = run_agent(agent, payload)
        logging.debug(f"Pre-verification Result: {result}")
        result = parse_isvalid(result["content"])
        results.append(result)
        
    return results

