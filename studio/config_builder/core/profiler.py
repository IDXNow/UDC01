"""
Data Profiler
Analyzes sample data to extract structure, patterns, and metadata
"""

import json
import re
from typing import Dict, Any, List, Optional
import logging


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
Output ONLY valid JSON within <output> tags:
<output>
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
</output>

Be precise and thorough. Extract actual values from the data."""

        profiling_config["data_conversion_request_msg"] = """Analyze this sample data and provide a complete profile:
<previous_conversion_notes>{<!--PreviousConversionNotes-->}</previous_conversion_notes>
<data>{<!--Data-->}</data>

Remember to output ONLY the JSON structure within <output> tags."""

        return profiling_config

    def parse_profile_result(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract structured profile from LLM result

        Args:
            result: Result from conversion job

        Returns:
            Parsed profile dictionary or None if parsing fails
        """
        try:
            content = result.get("result", {}).get("content", "")

            # Extract json from <output> tags
            match = re.search(r'<output>\s*(\{.*?\})\s*</output>', content, re.DOTALL)
            if match:
                profile_json = match.group(1)
                profile = json.loads(profile_json)
                self.logger.info("Successfully parsed profile from result")
                return profile
            else:
                # Try to find json anywhere in the content
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    profile = json.loads(json_match.group(0))
                    self.logger.warning("Found JSON without <output> tags")
                    return profile

            self.logger.error("No valid JSON found in result")
            return None

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Profile parsing error: {e}")
            return None

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
