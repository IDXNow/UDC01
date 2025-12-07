import argparse
import json
import os
from data_flow import process_data
import glob
import logging
import yaml
from datetime import datetime
import uuid


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

def load_config(config_path: str, conversion_path: str) -> dict:
    """Loads the configuration from the specified JSON file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    if not os.path.exists(conversion_path): #check to see if the conversion file is there
        raise FileNotFoundError(f"Conversion file not found: {conversion_path}")
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        with open(conversion_path, "r") as y:  #load the yaml file
            yaml_data = yaml.safe_load(y)

        validate_conversion_yaml(yaml_data, conversion_path)
        config.update(yaml_data) 
        
        # Move global attributes to the agents
        for agent_type in config["agents"]:
            if type(config["agents"][agent_type]) is list:
                for agent in config["agents"][agent_type]:
                    agent["base_url"] = config["api_base_url"]
                    agent["default_model"] = config["default_model"]
                    agent["default_temperature"] = config["default_temperature"]
                    agent["default_endpoint"] = config["default_endpoint"]
            else:
                agent = config["agents"][agent_type]
                agent["base_url"] = config["api_base_url"]
                agent["default_model"] = config["default_model"]
                agent["default_temperature"] = config["default_temperature"]
                agent["default_endpoint"] = config["default_endpoint"]

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

        # Save the log data to the file
        with open(log_filepath, "w") as log_file:
            json.dump(log_data, log_file, indent=4)

        logging.info(f"Log data saved to: {log_filepath}")

    except (KeyError, OSError) as e:
        logging.error(f"Error saving log data: {e}")


def main():
    parser = argparse.ArgumentParser(description="Universal Data Converter")
    parser.add_argument("--config", type=str, default="samples/config/default_config.json", help="Path to main configuration file")
    parser.add_argument("--file", type=str, help="Specific file to load", default=None)
    parser.add_argument("--folder", type=str, help="Folder to search for files", default=None)
    parser.add_argument("--pattern", type=str, help="File search pattern (e.g., '*.csv')", default=None)
    parser.add_argument("--output-folder", type=str, help="Folder to save output files", default=None)
    parser.add_argument("--conversion", type=str, default="samples/conversions/sales_invoice_conv.yaml", help="path to conversion yaml")  

    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config(args.config, args.conversion) 
        if args.output_folder != None:
            config["file_save"]["folder"] = args.output_folder 
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
