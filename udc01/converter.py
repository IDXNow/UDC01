import argparse
import copy
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

# ---------------------------------------------------------------------------
# Hardcoded defaults - lowest priority, overridden by config file then CLI args
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "default_provider": "local",
    "default_model": "openai/gpt-oss-20b",
    "default_endpoint": "v1/chat/completions",
    "default_temperature": None,
    "max_retries": 3,
    "api_timeout": 600,
    "api_retry_attempts": 3,
    "api_retry_backoff": 2,
    "parallel_agents": False,
    "max_parallel_workers": 3,
    "log_details": False,
    "validate_placeholders": True,
    "providers": {
        "local": {
            "base_url": "http://localhost:1234",
            "endpoint": "v1/chat/completions",
            "auth_header": None,
            "request_format": "openai"
        }
    },
    "api_keys": {},
    "file_load": {
        "folder": ".",
        "search_pattern": "*.csv"
    },
    "file_save": {
        "folder": "output/",
        "file_extension": "txt"
    },
    "log_file": {
        "folder": "logs/",
        "file_extension": "log"
    }
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base, recursively merging nested dicts.
    Override values take precedence; nested dicts are merged rather than replaced."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def validate_conversion_yaml(yaml_data: dict, conversion_path: str):
    """Validates that YAML contains all required message components."""
    verification_enabled = yaml_data.get("verification", {}).get("enabled", True)

    required_keys = [
        "data_conversion_system_msg",
        "data_conversion_request_msg",
        "data_validation_system_msg",
        "data_validation_request_msg",
    ]
    if verification_enabled is not False:
        required_keys += [
            "data_verification_system_msg",
            "data_verification_request_msg",
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

    logging.debug(f"Conversion YAML validation passed for {conversion_path}")

def validate_agent_config(config: dict):
    """Validates agent configuration structure."""
    required_agent_types = ["data_verifier", "data_conversion", "data_validator"]

    for agent_type in required_agent_types:
        if agent_type not in config.get("agents", {}):
            raise ValueError(f"Missing required agent type: {agent_type}")

        agent_group = config["agents"][agent_type]

        # Support role-group format: {"default_provider": "...", "agents": [...]}
        if isinstance(agent_group, dict) and "agents" in agent_group:
            inner = agent_group["agents"]
            agent_list = inner if isinstance(inner, list) else [inner]
        elif isinstance(agent_group, list):
            agent_list = agent_group
        else:
            agent_list = [agent_group]

        for agent in agent_list:
            required_keys = ["name", "role"]
            missing = [k for k in required_keys if k not in agent]
            if missing:
                raise ValueError(
                    f"Agent '{agent.get('name', 'unknown')}' in '{agent_type}' missing required keys: {missing}"
                )

    if config.get("log_details", False):
        logging.info("Agent configuration validation passed")

def load_config(config_path: str, conversion_path: str) -> dict:
    """Loads and merges configuration: defaults -> config file -> conversion YAML."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    if not os.path.exists(conversion_path):
        raise FileNotFoundError(f"Conversion file not found: {conversion_path}")
    try:
        # Layer 1: hardcoded defaults
        config = copy.deepcopy(DEFAULT_CONFIG)

        # Layer 2: config file deep-merged over defaults
        with open(config_path, 'r') as f:
            config = _deep_merge(config, json.load(f))

        # Layer 3: conversion YAML merged on top (top-level string fields)
        with open(conversion_path, "r") as y:
            yaml_data = yaml.safe_load(y)

        validate_conversion_yaml(yaml_data, conversion_path)
        config.update(yaml_data)

        # Validate agent configuration structure
        validate_agent_config(config)

        # Process keys
        api_keys = config.get("api_keys", {})
        resolved_api_keys = {}
        for provider, key_value in api_keys.items():
            if isinstance(key_value, str) and key_value.startswith("${") and key_value.endswith("}"):
                # Extract env variable name
                env_var_name = key_value[2:-1]
                env_value = os.getenv(env_var_name)
                if env_value:
                    
                    resolved_api_keys[provider] = env_value.strip()
                    if config.get("log_details", False):
                        logging.info(f"Loaded API key for '{provider}' from environment variable {env_var_name}")
                else:
                    if config.get("log_details", False):
                        logging.warning(f"Environment variable {env_var_name} not set for provider '{provider}'")
                    resolved_api_keys[provider] = ""
            else:
                # Use value directly from config (for fast usage)
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

        # Inject config into agents using 3-level hierarchy:
        # global defaults -> role-level defaults -> agent-level values (agent wins)
        global_provider = config.get("default_provider", "local")

        for agent_type, agent_group in config["agents"].items():
            # Unpack role-group format or flat format and extract role-level overrides
            if isinstance(agent_group, dict) and "agents" in agent_group:
                # Role-group format: {"default_provider": "...", "agents": [...]}
                role_provider = agent_group.get("default_provider", global_provider)
                role_temp_override = agent_group.get("default_temperature")
                role_model_override = agent_group.get("default_model")
                role_thinking_override = agent_group.get("default_thinking_budget")
                role_effort_override = agent_group.get("default_reasoning_effort")
                role_max_tokens_override = agent_group.get("default_max_tokens")
                inner = agent_group["agents"]
                agents_list = inner if isinstance(inner, list) else [inner]
            elif isinstance(agent_group, list):
                role_provider = global_provider
                role_temp_override = None
                role_model_override = None
                role_thinking_override = None
                role_effort_override = None
                role_max_tokens_override = None
                agents_list = agent_group
            else:
                # Single agent dict
                role_provider = global_provider
                role_temp_override = None
                role_model_override = None
                role_thinking_override = None
                role_effort_override = None
                role_max_tokens_override = None
                agents_list = [agent_group]

            provider_config = config["providers"].get(role_provider, {})

            # Resolve default model: role-level explicit -> role provider's default_model -> global fallback
            if role_model_override is not None:
                role_default_model = role_model_override
            elif "default_model" in provider_config:
                role_default_model = provider_config["default_model"]
            else:
                role_default_model = config.get("default_model", "openai/gpt-oss-20b")

            # Resolve default temperature: role-level explicit -> provider's default_temperature -> None (omit)
            if role_temp_override is not None:
                role_default_temperature = role_temp_override
            elif "default_temperature" in provider_config:
                role_default_temperature = provider_config["default_temperature"]
            else:
                role_default_temperature = None

            # Resolve thinking_budget: role-level -> provider profile -> None (omit)
            if role_thinking_override is not None:
                role_default_thinking_budget = role_thinking_override
            elif "default_thinking_budget" in provider_config:
                role_default_thinking_budget = provider_config["default_thinking_budget"]
            else:
                role_default_thinking_budget = None

            # Resolve reasoning_effort: role-level -> provider profile -> None (omit)
            if role_effort_override is not None:
                role_default_reasoning_effort = role_effort_override
            elif "default_reasoning_effort" in provider_config:
                role_default_reasoning_effort = provider_config["default_reasoning_effort"]
            else:
                role_default_reasoning_effort = None

            # Resolve max_tokens: role-level -> provider profile -> None (provider handles its own default)
            if role_max_tokens_override is not None:
                role_default_max_tokens = role_max_tokens_override
            elif "default_max_tokens" in provider_config:
                role_default_max_tokens = provider_config["default_max_tokens"]
            else:
                role_default_max_tokens = None

            for agent in agents_list:
                agent["default_provider"] = role_provider
                agent["default_model"] = role_default_model
                agent["default_temperature"] = role_default_temperature
                agent["default_thinking_budget"] = role_default_thinking_budget
                agent["default_reasoning_effort"] = role_default_reasoning_effort
                agent["default_max_tokens"] = role_default_max_tokens
                agent["timeout"] = config.get("api_timeout", 600)
                agent["retry_attempts"] = config.get("api_retry_attempts", 3)
                agent["retry_backoff"] = config.get("api_retry_backoff", 2)
                agent["providers"] = config["providers"]
                agent["api_keys"] = config["api_keys"]

            if isinstance(agent_group, dict) and "agents" in agent_group:
                config["agents"][agent_type] = inner

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
        unique_id = str(uuid.uuid4())[:8]  # Use first 8 characters of UUID
        log_filename = f"{timestamp}_{unique_id}.{log_extension}"
        log_filepath = os.path.join(log_folder, log_filename)

        # If log_details is enabled, include captured logging messages
        if config.get("log_details", False):
            log_data["system_logs"] = log_capture_handler.get_logs()

        # Save the log data to the file
        with open(log_filepath, "w") as log_file:
            json.dump(log_data, log_file, indent=4)

        if config.get("log_details", False):
            logging.info(f"Log data saved to: {log_filepath}")

        # Clear captured logs after saving to avoid accumulation across multiple files
        if config.get("log_details", False):
            log_capture_handler.clear_logs()

    except (KeyError, OSError) as e:
        logging.error(f"Error saving log data: {e}")


def main():
    parser = argparse.ArgumentParser(description="Universal Data Converter")
    parser.add_argument("--config", type=str, default="udc01/default_config.json",
                        help="Path to configuration file (default: udc01/default_config.json)")
    parser.add_argument("--conversion", type=str, default="samples/conversions/sales_invoice_conv.yaml",
                        help="Path to conversion YAML file")
    parser.add_argument("--file", type=str, default=None,
                        help="Specific file to process (overrides config file_load.default_file)")
    parser.add_argument("--folder", type=str, default=None,
                        help="Folder to search for files (overrides config file_load.folder)")
    parser.add_argument("--pattern", type=str, default=None,
                        help="File search pattern, e.g. '*.csv' (overrides config file_load.search_pattern)")
    parser.add_argument("--output-folder", type=str, default=None,
                        help="Folder to save output files (overrides config file_save.folder)")
    parser.add_argument("--parallel-agents", action="store_true",
                        help="Run validator agents in parallel (overrides config parallel_agents)")

    args = parser.parse_args()

    # Load configuration: defaults -> config file -> conversion YAML
    try:
        config = load_config(args.config, args.conversion)
    except (FileNotFoundError, ValueError) as e:
        logging.error(f"Error loading configuration: {e}")
        return

    # Apply CLI overrides - highest priority, override config file values
    if args.file:
        config["file_load"]["default_file"] = args.file
    if args.folder:
        config["file_load"]["folder"] = args.folder
    if args.pattern:
        config["file_load"]["search_pattern"] = args.pattern
    if args.output_folder:
        config["file_save"]["folder"] = args.output_folder
    if args.parallel_agents:
        config["parallel_agents"] = True
        if config.get("log_details", False):
            logging.info("Parallel agent execution enabled via --parallel-agents flag")

    # Determine file(s) to process - read from config after all overrides applied.
    # Explicit --folder or --pattern bypasses default_file even if set in config.
    files_to_process = []
    default_file = config["file_load"].get("default_file")
    if default_file and not (args.folder or args.pattern):
        files_to_process.append(default_file)
    else:
        folder = config["file_load"].get("folder", ".")
        pattern = config["file_load"].get("search_pattern", "*.csv")
        files_to_process = glob.glob(os.path.join(folder, pattern))

    if not files_to_process:
        logging.warning("No files to process. Specify --file, set file_load.default_file in config, or use --folder with --pattern.")
        return

    # Process each file
    for file_path in files_to_process:
        if config.get("log_details", False):
            logging.info(f"Processing file: {file_path}")
        try:
            conversion_result = process_data(file_path, config)
            save_logs(conversion_result, config)
        except Exception as e:
            logging.error(f"Error processing file {file_path}: {e}")

if __name__ == "__main__":
    main()
