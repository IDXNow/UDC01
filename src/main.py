import argparse
import json
import os
from data_flow import process_data
from messaging_flow import send_notifications, save_logs
import glob
import logging
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

def main():
    parser = argparse.ArgumentParser(description="Universal Data Converter")
    parser.add_argument("--config", type=str, default="config/default_config.json", help="Path to main configuration file")
    parser.add_argument("--file", type=str, help="Specific file to load", default=None)
    parser.add_argument("--folder", type=str, help="Folder to search for files", default=None)
    parser.add_argument("--pattern", type=str, help="File search pattern (e.g., '*.csv')", default=None)
    parser.add_argument("--output-folder", type=str, help="Folder to save output files", default=None)
    parser.add_argument("--conversion", type=str, default="config/conversions/default.yaml", help="path to conversion yaml")  

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
        logging.warning("No file or folder/pattern specified. Nothing to process.")
        return

    # Process each file
    for file_path in files_to_process:
        logging.info(f"Processing file: {file_path}")
        try:
            conversion_result = process_data(file_path, config)
            
            # Test conversion for now, no notification
            #send_notifications(conversion_result, config)
            save_logs(conversion_result, config)
        except Exception as e:
            logging.error(f"Error processing file {file_path}: {e}")

if __name__ == "__main__":
    main()
