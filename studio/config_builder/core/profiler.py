"""
Data Profiler
Analyzes sample data to extract structure, patterns, and metadata
"""

import csv
import io
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import logging

from .text_utils import loads_forgiving


class DataProfiler:
    """Analyzes data structure and extracts profile information"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def build_profiling_config(self, base_config: Dict[str, Any],
                              custom_instructions: str = "") -> Dict[str, Any]:
        """
        Build configuration for data profiling agent

        Args:
            base_config: Base UDC01 configuration
            custom_instructions: Optional user-provided profiling instructions

        Returns:
            Modified config with profiling-specific prompts
        """
        profiling_config = base_config.copy()

        # Copy providers and api_keys onto each agent
        for agent_type in profiling_config.get("agents", {}).keys():
            agents = profiling_config["agents"][agent_type]
            agent_list = agents if isinstance(agents, list) else [agents]

            for agent in agent_list:
                agent["providers"] = profiling_config.get("providers", {})
                agent["api_keys"] = profiling_config.get("api_keys", {})

        # Build custom instructions section
        custom_section = ""
        if custom_instructions and custom_instructions.strip():
            custom_section = f"""
**CUSTOM INSTRUCTIONS FROM USER:**
{custom_instructions.strip()}

Please incorporate these specific requirements into your analysis. Focus on extracting or profiling the elements mentioned in the custom instructions above.
"""

        profiling_config["data_conversion_system_msg"] = f"""You are a data profiling agent. Analyze the sample data and extract:

1. **Format**:
   - Structured: CSV, JSON, XML, pipe-delimited, tab-delimited, fixed-width, etc.
   - Unstructured: text, article, document, narrative, etc.
2. **Columns/Fields**:
   - For structured data: List all column names or field identifiers in order
   - For unstructured text: Identify key semantic elements (title, subject, author, body, sections, etc.)
3. **Data Types**: Infer types for each column/field (string, number, integer, float, date, datetime, boolean, text)
4. **Patterns**: Identify:
   - For structured: Delimiters (comma, pipe, tab, etc.), quote characters, null representations
   - For text: Document structure, sections, headers, formatting patterns
   - Date/time formats (if present)
   - Encoding (UTF-8, ASCII, etc.)
5. **Sample Values**: For each field, provide 2-3 representative example values
6. **Structure Notes**: Any hierarchies, relationships, or special formatting
{custom_section}
Output ONLY valid JSON within <o> tags:
<o>
{{
  "format": "pipe-delimited|csv|json|xml|unstructured|...",
  "delimiter": "|",
  "quote_char": "\\"",
  "encoding": "UTF-8",
  "has_header": true,
  "columns": [
    {{
      "name": "column_name",
      "position": 0,
      "data_type": "string|number|date|...",
      "nullable": true,
      "samples": ["value1", "value2", "value3"]
    }}
  ],
  "date_formats": ["YYYY-MM-DD", "MM/DD/YYYY"],
  "null_representations": ["", "NULL", "N/A"],
  "row_count_sample": 100,
  "notes": "Any additional observations"
}}
</o>

**OUTPUT RULES (a violation makes the response unusable):**
- Emit ONLY the JSON object between the <o> tags: no markdown fences, no prose, no comments.
- Escape every double quote inside a value as \\" — source values may already contain quotes.
- No trailing commas.
- At most 3 values in each "samples" array, each no longer than 120 characters.

Be precise and thorough. Extract actual values from the data."""

        profiling_config["data_conversion_request_msg"] = """Analyze this sample data and provide a complete profile:
<previous_conversion_notes>{<!--PreviousConversionNotes-->}</previous_conversion_notes>
<data>{<!--Data-->}</data>

Remember to output ONLY the JSON structure within <o> tags."""

        return profiling_config

    def parse_profile_result(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract a structured profile from an LLM result (None if it cannot be parsed)."""
        profile, _ = self.parse_profile_result_verbose(result)
        return profile

    def parse_profile_result_verbose(
        self, result: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Parse a profile, returning (profile, error) so the caller can retry usefully."""
        try:
            if result.get("error"):
                return None, str(result["error"])

            content = result.get("result", {}).get("content")

            if not content or not str(content).strip():
                return None, "the model returned an empty response"

            content = str(content)

            # UDC01's own extractor: case-insensitive
            from udc01.data_flow import parse_output

            payload = parse_output(content)
            source = "<o> tags"

            if payload is None:
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match is None:
                    return None, "no JSON object found in the response"
                payload, source = match.group(0), "raw response"

            profile, error = loads_forgiving(payload)

            # A matched <o> block that will not parse still deserves the greedy fallback
            if profile is None and source == "<o> tags":
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    profile, fallback_error = loads_forgiving(match.group(0))
                    error = None if profile is not None else (fallback_error or error)

            if profile is None:
                return None, error or "could not parse JSON from the response"

            if not isinstance(profile, dict):
                return None, f"expected a JSON object, got {type(profile).__name__}"

            self.logger.info(f"Successfully parsed profile from {source}")
            return profile, None

        except Exception as e:
            self.logger.error(f"Profile parsing error: {e}")
            return None, f"{type(e).__name__}: {e}"

    # ========================================================================
    # Local profiling: exact, instant, and immune to LLM transcription errors
    # ========================================================================

    DELIMITER_CANDIDATES = [(",", "csv"), ("|", "pipe-delimited"),
                            ("\t", "tsv"), (";", "semicolon-delimited")]
    MAX_SAMPLES = 3
    MAX_SAMPLE_LENGTH = 120
    DATE_FORMATS = [("%Y-%m-%d", "YYYY-MM-DD"), ("%m/%d/%Y", "MM/DD/YYYY"),
                    ("%d/%m/%Y", "DD/MM/YYYY"), ("%Y/%m/%d", "YYYY/MM/DD")]
    DATETIME_FORMATS = [("%Y-%m-%d %H:%M:%S", "YYYY-MM-DD HH:MM:SS"),
                        ("%Y-%m-%dT%H:%M:%S", "YYYY-MM-DDTHH:MM:SS")]
    BOOLEAN_VALUES = {"true", "false", "yes", "no", "y", "n"}
    NULL_VALUES = ["", "NULL", "null", "N/A", "NA", "None"]

    def profile_locally(self, sample_data: str) -> Optional[Dict[str, Any]]:
        """Build a profile from delimited data directly. Returns None if not delimited."""
        if not sample_data or not sample_data.strip():
            return None

        detected = self._detect_dialect(sample_data)
        if detected is None:
            return None

        delimiter, format_name, quote_char = detected

        try:
            rows = [
                row for row in csv.reader(
                    io.StringIO(sample_data), delimiter=delimiter, quotechar=quote_char
                )
                if row
            ]
        except csv.Error as e:
            self.logger.warning(f"Local profiling failed to read rows: {e}")
            return None

        if len(rows) < 2 or not self._is_rectangular(rows):
            return None

        has_header = self._has_header(rows)
        header = rows[0] if has_header else []
        data_rows = rows[1:] if has_header else rows

        if not data_rows:
            return None

        width = max(len(row) for row in rows)
        columns = []
        date_formats = set()

        for position in range(width):
            values = [row[position] if position < len(row) else "" for row in data_rows]
            present = [v for v in values if v.strip()]

            name = (
                header[position].strip()
                if position < len(header) and header[position].strip()
                else f"column_{position + 1}"
            )
            data_type, matched_format = self._infer_type(present)
            if matched_format:
                date_formats.add(matched_format)

            columns.append({
                "name": name,
                "position": position,
                "data_type": data_type,
                "nullable": len(present) < len(values),
                "samples": self._pick_samples(present),
            })

        return {
            "format": format_name,
            "delimiter": delimiter,
            "quote_char": quote_char,
            "encoding": "UTF-8",
            "has_header": has_header,
            "columns": columns,
            "date_formats": sorted(date_formats),
            "null_representations": [v for v in self.NULL_VALUES if v],
            "row_count_sample": len(data_rows),
            "notes": f"Profiled locally from {len(data_rows)} sample rows.",
        }

    def _detect_dialect(self, sample_data: str):
        """Return (delimiter, format_name, quote_char), or None if not delimited."""
        head = sample_data[:8192]
        quote_char = '"'

        try:
            sniffed = csv.Sniffer().sniff(head, delimiters="".join(
                d for d, _ in self.DELIMITER_CANDIDATES
            ))
            delimiter = sniffed.delimiter
            quote_char = sniffed.quotechar or '"'
        except csv.Error:
            # The sniffer gives up on short or irregular samples; count instead
            first_line = head.splitlines()[0] if head.splitlines() else ""
            counts = {d: first_line.count(d) for d, _ in self.DELIMITER_CANDIDATES}
            delimiter = max(counts, key=counts.get)
            if counts[delimiter] == 0:
                return None

        format_name = next(
            (name for d, name in self.DELIMITER_CANDIDATES if d == delimiter),
            "delimited",
        )
        return delimiter, format_name, quote_char

    def _is_rectangular(self, rows: List[List[str]]) -> bool:
        """Delimited data has a consistent field count; prose with commas does not."""
        widths = [len(row) for row in rows]
        modal = max(set(widths), key=widths.count)

        if modal < 2:
            return False

        return widths.count(modal) / len(widths) >= 0.8

    def _has_header(self, rows: List[List[str]]) -> bool:
        """A header row is all non-empty, non-numeric, and distinct."""
        first = rows[0]
        if not first or any(not cell.strip() for cell in first):
            return False
        if len(set(first)) != len(first):
            return False
        return not any(self._is_number(cell) for cell in first)

    def _pick_samples(self, values: List[str]) -> List[str]:
        """Up to MAX_SAMPLES distinct values, each truncated."""
        samples = []
        for value in values:
            trimmed = value.strip()
            if trimmed not in samples:
                samples.append(trimmed[:self.MAX_SAMPLE_LENGTH])
            if len(samples) == self.MAX_SAMPLES:
                break
        return samples

    def _infer_type(self, values: List[str]):
        """Return (data_type, date_format_label) for a column's non-empty values."""
        if not values:
            return "string", None

        if all(self._is_integer(v) for v in values):
            return "integer", None
        if all(self._is_number(v) for v in values):
            return "float", None
        if all(v.strip().lower() in self.BOOLEAN_VALUES for v in values):
            return "boolean", None

        for fmt, label in self.DATETIME_FORMATS:
            if all(self._matches_format(v, fmt) for v in values):
                return "datetime", label
        for fmt, label in self.DATE_FORMATS:
            if all(self._matches_format(v, fmt) for v in values):
                return "date", label

        return "string", None

    @staticmethod
    def _matches_format(value: str, fmt: str) -> bool:
        try:
            datetime.strptime(value.strip(), fmt)
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_integer(value: str) -> bool:
        try:
            int(value.strip())
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_number(value: str) -> bool:
        try:
            float(value.strip())
            return True
        except ValueError:
            return False

    def validate_profile(self, profile: Dict[str, Any]) -> bool:
        """
        Validate that profile contains required fields

        Args:
            profile: Profile dictionary to validate

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["format", "columns"]

        for field in required_fields:
            if field not in profile:
                self.logger.error(f"Profile missing required field: {field}")
                return False

        # Validate columns structure
        if not isinstance(profile["columns"], list):
            self.logger.error("Profile 'columns' must be a list")
            return False

        if len(profile["columns"]) == 0:
            self.logger.error("Profile must have at least one column")
            return False

        # Validate each column has required fields
        for i, col in enumerate(profile["columns"]):
            if "name" not in col:
                self.logger.error(f"Column {i} missing 'name' field")
                return False
            if "data_type" not in col:
                self.logger.error(f"Column {i} missing 'data_type' field")
                return False

        self.logger.info("Profile validation passed")
        return True

    def enrich_profile(self, profile: Dict[str, Any],
                      sample_data: str) -> Dict[str, Any]:
        """
        Add additional metadata to profile

        Args:
            profile: Base profile dictionary
            sample_data: Original sample data

        Returns:
            Enriched profile
        """
        # Add sample size
        lines = sample_data.strip().split('\n')
        profile["sample_line_count"] = len(lines)

        # Add byte size
        profile["sample_byte_size"] = len(sample_data.encode('utf-8'))

        # Add column count
        profile["column_count"] = len(profile.get("columns", []))

        # Infer primary format category
        format_type = profile.get("format", "").lower()
        if any(x in format_type for x in ["pipe", "delimited", "csv", "tsv"]):
            profile["format_category"] = "delimited"
        elif "json" in format_type:
            profile["format_category"] = "json"
        elif "xml" in format_type:
            profile["format_category"] = "xml"
        elif "fixed" in format_type:
            profile["format_category"] = "fixed_width"
        elif any(x in format_type for x in ["text", "article", "document", "narrative", "unstructured"]):
            profile["format_category"] = "text"
        else:
            profile["format_category"] = "other"

        return profile
