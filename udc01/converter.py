import argparse
import json
import os
import glob
import logging
import yaml
from datetime import datetime
import uuid


# Custom handler to capture log messages
class LogCaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log_records = []

    def emit(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S'),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        self.log_records.append(log_entry)

    def get_logs(self):
        return self.log_records.copy()

    def clear_logs(self):
        self.log_records.clear()

# Set up logging with console output and optional capture BEFORE importing other modules
log_capture_handler = LogCaptureHandler()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
        log_capture_handler  # Capture for log files
    ]
)

# Import after logging is configured
from .data_flow import process_data

def validate_conversion_yaml(yaml_data: dict, conversion_path: str):
    """Validates that YAML contains all required message components."""
    required_keys = [
        "data_conversion_system_msg",
        "data_conversion_request_msg",
        "data_verification_system_msg",
        "data_verification_request_msg",
        "data_validation_system_msg",
        "data_validation_request_msg"
    ]

    missing_keys = [key for key in required_keys if key not in yaml_data]

    if missing_keys:
        raise ValueError(
            f"Conversion YAML '{conversion_path}' is missing required keys: {missing_keys}\n"
            f"Required keys are: {required_keys}"
        )

    # Validate that values are non-empty strings
    for key in required_keys:
        if not isinstance(yaml_data[key], str) or not yaml_data[key].strip():
            raise ValueError(
                f"Conversion YAML '{conversion_path}' has empty or invalid value for '{key}'"
            )

    logging.info(f"Conversion YAML validation passed for {conversion_path}")

def validate_agent_config(config: dict):
    """Validates agent configuration structure."""
    required_agent_types = ["data_verifier", "data_conversion", "data_validator"]

    for agent_type in required_agent_types:
        if agent_type not in config.get("agents", {}):
            raise ValueError(f"Missing required agent type: {agent_type}")

        agents = config["agents"][agent_type]
        agent_list = agents if isinstance(agents, list) else [agents]

        for agent in agent_list:
            required_keys = ["name", "role"]
            missing = [k for k in required_keys if k not in agent]
            if missing:
                raise ValueError(
                    f"Agent '{agent.get('name', 'unknown')}' in '{agent_type}' missing required keys: {missing}"
                )

    logging.info("Agent configuration validation passed")

def load_config(config_path: str, conversion_path: str) -> dict:
    """Loads the configuration from the specified JSON file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    if not os.path.exists(conversion_path): # check to see if the conversion file is there
        raise FileNotFoundError(f"Conversion file not found: {conversion_path}")
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        with open(conversion_path, "r") as y:  # load the yaml file
            yaml_data = yaml.safe_load(y)


        validate_conversion_yaml(yaml_data, conversion_path)
        config.update(yaml_data)

        # Validate agent configuration structure
        validate_agent_config(config)

        # Process API keys - replace ${ENV_VAR} placeholders with environment variables
        api_keys = config.get("api_keys", {})
        resolved_api_keys = {}
        for provider, key_value in api_keys.items():
            if isinstance(key_value, str) and key_value.startswith("${") and key_value.endswith("}"):
                # Extract environment variable name
                env_var_name = key_value[2:-1]
                env_value = os.getenv(env_var_name)
                if env_value:
                    # Strip whitespace/newlines from environment variable
                    resolved_api_keys[provider] = env_value.strip()
                    if config.get("log_details", False):
                        logging.info(f"Loaded API key for '{provider}' from environment variable {env_var_name}")
                else:
                    if config.get("log_details", False):
                        logging.warning(f"Environment variable {env_var_name} not set for provider '{provider}'")
                    resolved_api_keys[provider] = ""
            else:
                # Use value directly from config (for fast usage), strip whitespace
                resolved_api_keys[provider] = key_value.strip() if isinstance(key_value, str) else key_value

        config["api_keys"] = resolved_api_keys

        # Validate providers configuration exists
        if "providers" not in config:
            logging.warning("No 'providers' section in config - using legacy single-endpoint mode")
            config["providers"] = {
                "local": {
                    "base_url": "http://localhost:1234",
                    "endpoint": config.get("default_endpoint", "v1/chat/completions"),
                    "auth_header": None,
                    "request_format": "openai"
                }
            }

        # Move global attributes to the agents
        for agent_type in config["agents"]:
            if type(config["agents"][agent_type]) is list:
                for agent in config["agents"][agent_type]:
                    agent["default_model"] = config["default_model"]
                    agent["default_provider"] = config.get("default_provider", "local")
                    agent["default_temperature"] = config["default_temperature"]
                    agent["default_endpoint"] = config["default_endpoint"]
                    agent["timeout"] = config.get("api_timeout", 600)
                    agent["retry_attempts"] = config.get("api_retry_attempts", 3)
                    agent["retry_backoff"] = config.get("api_retry_backoff", 2)
                    agent["providers"] = config["providers"]
                    agent["api_keys"] = config["api_keys"]
            else:
                agent = config["agents"][agent_type]
                agent["default_model"] = config["default_model"]
                agent["default_provider"] = config.get("default_provider", "local")
                agent["default_temperature"] = config["default_temperature"]
                agent["default_endpoint"] = config["default_endpoint"]
                agent["timeout"] = config.get("api_timeout", 600)
                agent["retry_attempts"] = config.get("api_retry_attempts", 3)
                agent["retry_backoff"] = config.get("api_retry_backoff", 2)
                agent["providers"] = config["providers"]
                agent["api_keys"] = config["api_keys"]

        return config
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in config file: {e}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML format in config file: {e}")


def save_logs(log_data: dict, config: dict):
    """
    Saves log data to a file with a unique filename.

    Args:
        log_data (dict): The log data to be saved.
        config (dict): The configuration dictionary containing log file settings.
    """
    try:
        log_folder = config["log_file"]["folder"]
        log_extension = config["log_file"]["file_extension"]

        # Ensure the log folder exists
        os.makedirs(log_folder, exist_ok=True)

        # Generate a unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]  # Use first 8 characters of UUID for brevity
        log_filename = f"{timestamp}_{unique_id}.{log_extension}"
        log_filepath = os.path.join(log_folder, log_filename)

        # If log_details is enabled, include captured logging messages
        if config.get("log_details", False):
            log_data["system_logs"] = log_capture_handler.get_logs()

        # Save the log data to the file
        with open(log_filepath, "w") as log_file:
            json.dump(log_data, log_file, indent=4)

        logging.info(f"Log data saved to: {log_filepath}")

        # Clear captured logs after saving to avoid accumulation across multiple files
        if config.get("log_details", False):
            log_capture_handler.clear_logs()

    except (KeyError, OSError) as e:
        logging.error(f"Error saving log data: {e}")


def main():
    parser = argparse.ArgumentParser(description="Universal Data Converter")
    parser.add_argument("--config", type=str, default="udc01/default_config.json", help="Path to main configuration file")
    parser.add_argument("--file", type=str, help="Specific file to load", default=None)
    parser.add_argument("--folder", type=str, help="Folder to search for files", default=None)
    parser.add_argument("--pattern", type=str, help="File search pattern (e.g., '*.csv')", default=None)
    parser.add_argument("--output-folder", type=str, help="Folder to save output files", default=None)
    parser.add_argument("--conversion", type=str, default="samples/conversions/sales_invoice_conv.yaml", help="path to conversion yaml")
    parser.add_argument("--parallel-agents", action="store_true", help="Run validator agents in parallel (faster for cloud APIs, not recommended for local LLMs)")

    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config(args.config, args.conversion)
        if args.output_folder != None:
            config["file_save"]["folder"] = args.output_folder
        if args.parallel_agents:
            config["parallel_agents"] = True
            logging.info("Parallel agent execution enabled via --parallel-agents flag")

    except (FileNotFoundError, ValueError) as e:
        logging.error(f"Error loading configuration: {e}")
        return

    # Determine file(s) to process
    files_to_process = []
    if args.file:
        files_to_process.append(args.file)
    elif args.folder and args.pattern:
        search_path = os.path.join(args.folder, args.pattern)
        files_to_process = glob.glob(search_path)
    else:
        logging.warning("No file or folder/pattern specified.  Nothing to process.")
        return

    # Process each file
    for file_path in files_to_process:
        logging.info(f"Processing file: {file_path}")
        try:
            conversion_result = process_data(file_path, config)
            save_logs(conversion_result, config)
        except Exception as e:
            logging.error(f"Error processing file {file_path}: {e}")

if __name__ == "__main__":
    main()
