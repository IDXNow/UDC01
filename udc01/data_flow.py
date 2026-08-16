import os
import pandas as pd
import logging
import time
from datetime import datetime
from .validators import prepare_agent, run_agent, validate_output_2of3, verify_input_data_2of3, get_str_between_tags, validate_no_placeholders

################################################################################
# Conversion logic                                                             #
################################################################################

def perform_conversion(raw_data: str, config: dict, run_index: int = 0, prev_note: str = '') -> dict:
    """Calls the Data Conversion agent to transform *raw_data*."""

    agent = config["agents"]["data_conversion"]
    conversion_instructions = config["data_conversion_system_msg"]
    request_instructions = (
        config["data_conversion_request_msg"]
        .replace("{<!--Data-->}", raw_data)
        .replace("{<!--RunIndex-->}", str(run_index))
        .replace("{<!--DateTime-->}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        .replace("{<!--PreviousConversionNotes-->}", prev_note)
    )


    prepare_agent(agent, config)

    payload = {
        "request": request_instructions,
        "instructions": conversion_instructions,
    }

    # Validate no placeholders remain
    if not validate_no_placeholders(payload["request"]):
        logging.error(f"Unreplaced placeholders in conversion request")
        return {"error": "Unreplaced placeholders in request", "content": None}

    logging.debug(f"Payload for conversion agent {agent.get('name')}: {payload}")
    if config.get("log_details", False):
        logging.info(f"Running conversion (attempt {run_index + 1})")

    response = run_agent(agent, payload)
    if "error" in response:
        logging.error(f"Conversion agent failed: {response['error']}")
        return {"error": response["error"], "content": None}
    return response

################################################################################
# Processing pipeline                                                          #
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
    prev_conv_msg = ""

    raw_data = load_file(file_path)
    if raw_data is None:
        return {"error": "Could not load file", "file_path": file_path}

    # -----------------------------------------------------------------
    # 1. Pre-conversion verification
    # -----------------------------------------------------------------
    if config.get("verification", {}).get("enabled", True) is not False:
        pre_verification_results = verify_input_data_2of3(raw_data, config)
        success_count = sum(1 for r in pre_verification_results if r.get("isvalid"))

        # No verifier returned a verdict
        if pre_verification_results and all(r.get("failed") for r in pre_verification_results):
            logging.error("All verification agents failed to return a verdict; input was not evaluated.")
            return {
                "status": "verification_unavailable",
                "pre_verification_results": pre_verification_results,
                "file_path": file_path,
            }

        if success_count < 2:
            logging.error("Pre-conversion verification failed (2/3 rule not met).")
            return {
                "status": "pre-verification_failed",
                "pre_verification_results": pre_verification_results,
                "file_path": file_path,
            }
    else:
        if config.get("log_details", False):
            logging.info("Pre-conversion verification skipped (verification.enabled: false)")

    # -----------------------------------------------------------------
    # 2. Conversion + validation with retry logic
    # -----------------------------------------------------------------
    while retry_count < max_retries:
        conv_response = perform_conversion(raw_data, config, retry_count, prev_conv_msg)
        conversion_content = conv_response.get("content") if isinstance(conv_response, dict) else None
        output_data = parse_output(conversion_content) if conversion_content else None

        if output_data is None:
            retry_count += 1
            logging.warning(f"Conversion response missing <o> section (attempt {retry_count}/{max_retries}); retrying…")
            prev_conv_msg = "Your previous response was missing the required <o>…</o> tags. You MUST wrap all output in <o> and </o> tags."
            continue

        # Validate converted output
        validation_results = validate_output_2of3(raw_data, output_data, config)
        val_success_count = sum(1 for r in validation_results if r.get("isvalid"))

        # No validator returned a verdict
        if validation_results and all(r.get("failed") for r in validation_results):
            logging.error("All validation agents failed to return a verdict; aborting conversion retries.")
            return {
                "status": "validation_unavailable",
                "validation": validation_results,
                "retries": retry_count,
                "file_path": file_path,
            }

        if val_success_count >= 2:
            # Success – save the file and break.
            output_path = save_output_data(output_data, file_path, config)
            conversion_result = {
                "status": "success",
                "validation": validation_results,
                "output_path": output_path if output_path else "save_failed",
            }
            break
        else:
            # append error note for next conversion attempt
            # Only feed back genuine rejections. A failed agent's message describes possible network issue.
            prev_conv_msg = "\n\n".join([
                item.get("invalid_msg", "")
                for item in validation_results
                if not item.get("isvalid", True) and not item.get("failed")
            ])
            if config.get("include_prior_output_on_retry", False):
                prev_conv_msg += "\n\n<prev_output>" + output_data + "</prev_output>"
            
            

        # Log detailed validation errors before retrying
        retry_count += 1
        logging.warning(f"Validation failed (attempt {retry_count}/{max_retries}); retrying conversion…")
        logging.warning(f"Validation results: {val_success_count}/3 validators approved")
        for idx, result in enumerate(validation_results, 1):
            if result.get("failed"):
                status = "! FAILED"
            else:
                status = "✓ VALID" if result.get("isvalid") else "✗ INVALID"
            msg = result.get("invalid_msg", "No message provided")
            logging.warning(f"  Validator {idx}: {status} - {msg}")

    # ------------------------------------------------------------------
    # 3. Wrap-up summary
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

def extract_pdf_text(file_path: str) -> str | None:
    """
    Extract text content from a PDF file using pdfplumber for now.

    Handles:
    - Simple text-based PDFs
    - PDFs with tables (extracts tables as structured text)
    - Multi-page documents
    - Complex layouts (multi-column)

    Args:
        file_path: Path to the PDF file

    Returns:
        Extracted text as a single string, or None if extraction fails
    """
    try:
        import pdfplumber
    except ImportError:
        logging.error(
            "pdfplumber is not installed. Install it with: pip install pdfplumber"
        )
        return None

    try:
        extracted_text = []

        with pdfplumber.open(file_path) as pdf:
            if len(pdf.pages) == 0:
                logging.warning(f"PDF file {file_path} contains no pages")
                return None

            for page_num, page in enumerate(pdf.pages, start=1):
                # Extract tables first (if any)
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        # Convert table to text format (pipe-delimited rows)
                        for row in table:
                            if row:  # Skip empty rows
                                row_text = "|".join(str(cell or "").strip() for cell in row)
                                extracted_text.append(row_text)

                # Extract regular text
                page_text = page.extract_text()
                if page_text:
                    extracted_text.append(page_text.strip())

        if not extracted_text:
            logging.warning(f"No text could be extracted from PDF: {file_path}")
            return None

        # Join all text with double newlines between sections
        return "\n\n".join(extracted_text)

    except Exception as exc:
        logging.error(f"Error extracting text from PDF {file_path}: {exc}")
        return None


def load_file(file_path: str) -> str | None:
    """Load file content as string.  Supports text, Excel, and PDF formats"""
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = file_path.split(".")[-1].lower()

        # Excel files
        if ext in {"xlsx", "xlsm", "xlsb", "odf", "ods", "xls"}:
            df = pd.read_excel(file_path)
            return df.to_string(index=False)

        # PDF files
        elif ext == "pdf":
            return extract_pdf_text(file_path)

        # Text-based files (CSV, TXT, XML, JSON, HTML, etc.)
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read()

    except Exception as exc:
        logging.error(f"Error loading file {file_path}: {exc}")
        return None


def parse_output(message_content: str) -> str | None:
    """Extract the <o>…</o> section from an agent message."""
    return get_str_between_tags(message_content, "<o>", "</o>", True)


def parse_tabular_data(output_data: str) -> pd.DataFrame | None:
    """
    Parse structured text output into a pandas DataFrame.

    Supports:
    - Pipe-delimited format (col1|col2|col3)
    - CSV format (col1,col2,col3)
    - JSON array format ([{"col1": "val1"}, ...])

    Args:
        output_data: String containing structured data

    Returns:
        DataFrame if parsing succeeds, None otherwise
    """
    import io
    import json

    output_data = output_data.strip()

    if not output_data:
        logging.warning("Empty output data, cannot create Excel file")
        return None

    try:
        # Try JSON array format first
        if output_data.startswith('[') and output_data.endswith(']'):
            data = json.loads(output_data)
            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data)
                logging.debug(f"Parsed JSON array: {len(df)} rows, {len(df.columns)} columns")
                return df
    except (json.JSONDecodeError, ValueError):
        pass

    # Try pipe-delimited format
    if '|' in output_data:
        try:
            lines = output_data.strip().split('\n')
            if len(lines) >= 1:
                # First line is header
                headers = [h.strip() for h in lines[0].split('|')]

                # Remaining lines are data rows
                data_rows = []
                for line in lines[1:]:
                    if line.strip():
                        row = [cell.strip() for cell in line.split('|')]
                        data_rows.append(row)

                df = pd.DataFrame(data_rows, columns=headers)
                logging.debug(f"Parsed pipe-delimited: {len(df)} rows, {len(df.columns)} columns")
                return df
        except Exception as exc:
            logging.warning(f"Failed to parse as pipe-delimited: {exc}")

    # Try CSV format
    try:
        df = pd.read_csv(io.StringIO(output_data))
        if not df.empty:
            logging.debug(f"Parsed CSV: {len(df)} rows, {len(df.columns)} columns")
            return df
    except Exception as exc:
        logging.warning(f"Failed to parse as CSV: {exc}")

    # If all parsing attempts fail
    logging.error("Could not parse output data as tabular format (pipe-delimited, CSV, or JSON array)")
    return None


def save_as_excel(df: pd.DataFrame, file_path: str) -> bool:
    """
    Save a DataFrame to an Excel file.

    Args:
        df: pandas DataFrame to save
        file_path: Output file path (.xlsx)

    Returns:
        True if save succeeds, False otherwise
    """
    try:
        # Save to Excel with basic formatting
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Data')

            # Optional: Auto-adjust column widths
            worksheet = writer.sheets['Data']
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(str(col))
                )
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)

        logging.debug(f"Excel file saved: {file_path}")
        return True
    except Exception as exc:
        logging.error(f"Error saving Excel file {file_path}: {exc}")
        return False


def save_output_data(output_data: str, file_path: str, config: dict) -> str | None:
    """
    Persist *output_data* to disk in the configured output directory.
    Supports both text and Excel output formats.

    Returns the output file path on success, None on failure.
    """
    try:
        output_dir = config["file_save"]["folder"]
        file_ext = config["file_save"]["file_extension"]
        os.makedirs(output_dir, exist_ok=True)

        basename = os.path.splitext(os.path.basename(file_path))[0]
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        out_path = os.path.join(output_dir, f"{basename}-{timestamp}.{file_ext}")

        # Excel output
        if file_ext.lower() in {"xlsx", "xls"}:
            df = parse_tabular_data(output_data)
            if df is None:
                logging.warning("Could not parse output as tabular data.  Falling back to text output.")
                # Fallback: save as text with .txt extension
                text_path = os.path.join(output_dir, f"{basename}-{timestamp}.txt")
                with open(text_path, "w", encoding="utf-8") as fh:
                    fh.write(output_data)
                if config.get("log_details", False):
                    logging.info(f"Output saved as text (fallback): {text_path}")
                return text_path

            if save_as_excel(df, out_path):
                return out_path
            else:
                return None

        # Text output (default)
        else:
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(output_data)
            if config.get("log_details", False):
                logging.info(f"Output saved to {out_path}")
            return out_path

    except Exception as exc:
        logging.error(f"Error saving output data: {exc}")
        return None
