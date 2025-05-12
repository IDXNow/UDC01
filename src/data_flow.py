import os
import pandas as pd
import logging
import time
from datetime import datetime
from validators import run_agent, parse_isvalid, get_str_between_tags

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

################################################################################
# Helper functions implementing the early‑exit 2 / 3 consensus logic           #
################################################################################
def _prepare_agent(agent_cfg: dict, config: dict):
    """Populate common runtime attributes onto an agent configuration."""
    agent_cfg["base_url"] = config["api_base_url"]
    agent_cfg["endpoint"] = config["default_endpoint"]


def _verify_input_data_2of3(raw_data: str, config: dict) -> list:
    """Run the data-verification agents using the 2/3 strategy
    - We always execute the first two agents.
    - If their <isvalid> results agree we *stop* - consensus reached.
    - If they disagree (one True, one False) we execute the third agent to break the tie.
    The function returns a list of parsed verification dictionaries - one for every agent *actually run* (two or three).
    """
    agents = config["agents"]["data_verifier"]
    results = []

    for idx, agent in enumerate(agents):
        if idx == 2 and len(results) == 2:
            # Only reach here when the first two results were opposing.
            same = results[0]["isvalid"] == results[1]["isvalid"]
            if same:
                break  # No need to run the third agent.
        _prepare_agent(agent, config)
        payload = {
            "request": config.get(agent.get("request_instructions"), "")
            .replace("{<!--Data-->}", raw_data),
            "instructions": config.get(agent.get("instructions"), ""),
        }
        logging.debug(
            f"Payload for verification agent {agent.get('name')}: {payload}"
        )
        message = run_agent(agent, payload)
        parsed = parse_isvalid(message["content"])
        results.append(parsed)

        # After the second agent, decide if we need a tie‑breaker.
        if idx == 1 and results[0]["isvalid"] == results[1]["isvalid"]:
            break  # Consensus (both True or both False).
    return results


def _validate_output_2of3(raw_data: str, output_data: str, config: dict) -> list:
    """Run the data-validation agents using the same 2/3 early-exit logic"""
    agents = config["agents"]["data_validator"]
    results = []

    for idx, agent in enumerate(agents):
        if idx == 2 and len(results) == 2:
            if results[0]["isvalid"] == results[1]["isvalid"]:
                break  # consensus already achieved
        _prepare_agent(agent, config)
        payload = {
            "instructions": config.get(agent.get("instructions"), ""),
            "request": config.get(agent.get("request_instructions"), "")
            .replace("{<!--Data-->}", raw_data)
            .replace("{<!--Output-->}", output_data)
            .replace("{<!--DateTime-->}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        }
        logging.debug(
            f"Payload for validation agent {agent.get('name')}: {payload}"
        )
        message = run_agent(agent, payload)
        parsed = parse_isvalid(message["content"])
        results.append(parsed)

        if idx == 1 and results[0]["isvalid"] == results[1]["isvalid"]:
            break  # early consensus
    return results


################################################################################
# Conversion logic                                                             #
################################################################################

def perform_conversion(raw_data: str, config: dict, run_index: int = 0) -> dict:
    """Calls the Data Conversion agent to transform *raw_data*."""

    agent = config["agents"]["data_conversion"]
    conversion_instructions = config["data_conversion_system_msg"]
    request_instructions = (
        config["data_conversion_request_msg"]
        .replace("{<!--Data-->}", raw_data)
        .replace("{<!--RunIndex-->}", str(run_index))
        .replace("{<!--DateTime-->}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )

    _prepare_agent(agent, config)

    payload = {
        "request": request_instructions,
        "instructions": conversion_instructions,
    }
    logging.debug(f"Payload for conversion agent {agent.get('name')}: {payload}")
    logging.info(f"Running conversion (attempt {run_index + 1})")

    return run_agent(agent, payload)

################################################################################
# Orchestrating the full processing pipeline                                   #
################################################################################

def process_data(file_path: str, config: dict) -> dict:
    """Process *file_path* through verification -> conversion -> validation.
    Implements a 2/3 majority rule for the verification and validation stages. 
    Retries the conversion up to *config['max_retries']* times if fewer than two validators approve the output.
    """

    max_retries = config.get("max_retries", 3)
    retry_count = 0
    conversion_result: dict = {}
    validation_results: list = []

    raw_data = load_file(file_path)
    if raw_data is None:
        return {"error": "Could not load file", "file_path": file_path}

    # ------------------------------------------------------------------
    # 1. Pre‑conversion verification
    # ------------------------------------------------------------------
    pre_verification_results = _verify_input_data_2of3(raw_data, config)
    success_count = sum(1 for r in pre_verification_results if r.get("isvalid"))
    if success_count < 2:
        logging.error("Pre-conversion verification failed (2/3 rule not met).")
        return {
            "status": "pre-verification_failed",
            "pre_verification_results": pre_verification_results,
            "file_path": file_path,
        }

    # ------------------------------------------------------------------
    # 2. Conversion + validation with retry logic
    # ------------------------------------------------------------------
    while retry_count < max_retries:
        conv_response = perform_conversion(raw_data, config, retry_count)
        conversion_content = conv_response.get("content") if isinstance(conv_response, dict) else None
        output_data = parse_output(conversion_content) if conversion_content else None

        if output_data is None:
            # Conversion agent did not return expected <output> tags.
            logging.warning("Conversion response missing <output> section; aborting.")
            return {
                "status": "conversion_error",
                "conversion_response": conv_response,
                "file_path": file_path,
            }

        # Validate converted output
        validation_results = _validate_output_2of3(raw_data, output_data, config)
        val_success_count = sum(1 for r in validation_results if r.get("isvalid"))

        if val_success_count >= 2:
            # Success – save the file and break.
            save_output_data(output_data, file_path, config)
            conversion_result = {
                "status": "success",
                "validation": validation_results,
                "output_path": "saved",  # path logged inside save_output_data
            }
            break

        retry_count += 1
        logging.warning(f"Validation failed (attempt {retry_count}/{max_retries}); retrying conversion…")

    # ------------------------------------------------------------------
    # 3. Wrap‑up summary
    # ------------------------------------------------------------------
    if conversion_result.get("status") == "success":
        return conversion_result

    return {
        "status": "failed",
        "validation": validation_results,
        "retries": retry_count,
        "file_path": file_path,
    }

################################################################################
# Utility functions                                                            #
################################################################################

def load_file(file_path: str) -> str | None:
    """Load file content as a *string*. Supports several text‑based formats"""
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = file_path.split(".")[-1].lower()
        if ext in {"xlsx", "xlsm", "xlsb", "odf", "ods", "xls"}:
            df = pd.read_excel(file_path)
            return df.to_string(index=False)
        else:  # treat as text‑based
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read()
    except Exception as exc:
        logging.error(f"Error loading file {file_path}: {exc}")
        return None


def parse_output(message_content: str) -> str | None:
    """Extract the <output>…</output> section from an agent message."""
    return get_str_between_tags(message_content, "<output>", "</output>")


def save_output_data(output_data: str, file_path: str, config: dict):
    """Persist *output_data* to disk in the configured output directory."""
    try:
        output_dir = config["file_save"]["folder"]
        file_ext = config["file_save"]["file_extension"]
        os.makedirs(output_dir, exist_ok=True)

        basename = os.path.splitext(os.path.basename(file_path))[0]
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        out_path = os.path.join(output_dir, f"{basename}-{timestamp}.{file_ext}")

        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(output_data)
            #fh.writelines(output_data)
        logging.info(f"Output saved to {out_path}")
    except Exception as exc:
        logging.error(f"Error saving output data: {exc}")

