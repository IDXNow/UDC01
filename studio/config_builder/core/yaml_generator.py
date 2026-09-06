"""
YAML Configuration Generator
Generates UDC01 YAML configurations from data profiles
"""

import json
import re
from typing import Dict, Any, Optional
import logging
from pathlib import Path

from .text_utils import strip_code_fence


VERIFICATION_SECTIONS = """3. **data_verification_system_msg**: Instructions for PRE-PROCESS verification agents
   - IMPORTANT: Verification checks the INCOMING INPUT data ONLY (before conversion)
   - Purpose: Ensure input data is valid, safe, and meets requirements for conversion
   - Does NOT check output or conversion results
   - Validates structure, completeness, safety, data types of INPUT

4. **data_verification_request_msg**: Template for verification requests (INPUT data only)
"""

NO_VERIFICATION_SECTIONS = """(Pre-conversion verification is DISABLED for this configuration.
Do NOT generate data_verification_system_msg or data_verification_request_msg.)
"""

# UDC01 reads these top-level settings
RESERVED_SETTING_KEYS = ("verification", "include_prior_output_on_retry")


class YAMLGenerator:
    """Generates UDC01 YAML configurations"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.templates_path = Path(config["generation"]["templates_path"])
        generation = config.get("generation", {})
        self.verification_enabled = generation.get("verification_enabled", True)
        self.include_prior_output_on_retry = generation.get("include_prior_output_on_retry", False)

    def load_template(self, format_name: str) -> str:
        """
        Load YAML template for specified format

        Args:
            format_name: Target format (e.g., "pipe-delimited", "CSV", "JSON")

        Returns:
            Template YAML content
        """
        # Normalize format name
        normalized = format_name.lower().replace('-', '_').replace(' ', '_')
        template_file = self.templates_path / f"{normalized}.yaml"

        if template_file.exists():
            with open(template_file, 'r') as f:
                self.logger.info(f"Loaded template: {template_file}")
                return f.read()

        # Fallback to generic template
        self.logger.warning(f"Template not found for {format_name}, using generic")
        return self._get_generic_template()

    def build_generation_config(self, profile: Dict[str, Any],
                               template: str,
                               user_instructions: str,
                               base_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build configuration for YAML generation agent

        Args:
            profile: Data profile dictionary
            template: Base YAML template
            user_instructions: User-provided custom instructions
            base_config: Base UDC01 configuration

        Returns:
            Modified config with generation-specific prompts
        """
        generation_config = base_config.copy()

        # Copy providers and api_keys onto each agent
        for agent_type in generation_config.get("agents", {}).keys():
            agents = generation_config["agents"][agent_type]
            agent_list = agents if isinstance(agents, list) else [agents]

            for agent in agent_list:
                agent["providers"] = generation_config.get("providers", {})
                agent["api_keys"] = generation_config.get("api_keys", {})

        # Format profile for prompt
        profile_str = json.dumps(profile, indent=2)
        verification_sections = (
            VERIFICATION_SECTIONS if self.verification_enabled else NO_VERIFICATION_SECTIONS
        )

        generation_config["data_conversion_system_msg"] = f"""You are a YAML configuration generator for UDC01 data conversion system.

**INPUT PROFILE:**
```json
{profile_str}
```

**BASE TEMPLATE:**
```yaml
{template}
```

**USER INSTRUCTIONS:**
{user_instructions or 'No additional instructions provided.'}

**YOUR TASK:**
Generate a complete UDC01 YAML configuration file with these sections:

1. **data_conversion_system_msg**: Instructions for the conversion agent to transform input data
2. **data_conversion_request_msg**: Template for conversion requests

{verification_sections}
5. **data_validation_system_msg**: Instructions for POST-PROCESS validation agents
   - IMPORTANT: Validation checks the CONVERSION RESULTS (after conversion)
   - Purpose: Ensure conversion was correct by comparing INPUT with OUTPUT
   - Verifies transformation rules were followed
   - Checks output format, completeness, accuracy against original input

6. **data_validation_request_msg**: Template for validation requests (INPUT + OUTPUT comparison)

**CRITICAL - PLACEHOLDER PRESERVATION:**
UDC01 uses special runtime placeholders that MUST be preserved EXACTLY as shown below.

**Runtime Placeholders:**
- `{{<!--Data-->}}` - Replaced with input data at runtime
- `{{<!--Output-->}}` - Replaced with output data at runtime
- `{{<!--PreviousConversionNotes-->}}` - Replaced with retry notes at runtime
- `{{<!--DateTime-->}}` - Replaced with current timestamp
- `{{<!--RunIndex-->}}` - Replaced with retry attempt number

**Required Format for data_conversion_request_msg:**
```
[Current time: {{<!--DateTime-->}}] [Try Index:{{<!--RunIndex-->}}]
<data>{{<!--Data-->}}</data>
<previous_conversion_notes>{{<!--PreviousConversionNotes-->}}</previous_conversion_notes>
```

**Required Format for data_verification_request_msg:**
(PRE-PROCESS: Receives INPUT data ONLY to verify before conversion)
```
[Current time: {{<!--DateTime-->}}]
<data>{{<!--Data-->}}</data>
```

**Required Format for data_validation_request_msg:**
(POST-PROCESS: Receives both INPUT and OUTPUT to compare conversion results)
```
[Current time: {{<!--DateTime-->}}]
<data>{{<!--Data-->}}</data>
<o>{{<!--Output-->}}</o>
```

Do NOT modify, escape, or change these placeholders.  Preserve the exact format with wrapper tags.

**REQUIREMENTS:**
- Use the profile information to customize field names, data types, and formats
- Incorporate the base template structure
- Apply any user instructions
- Ensure all field mappings are accurate
- Include proper delimiters, quote handling, and date formats
- Add validation rules based on data types
- PRESERVE all runtime placeholders with their wrapper tags exactly as shown above
- Do NOT emit the top-level keys `verification` or `include_prior_output_on_retry`; Studio adds those
- **CRITICAL**: The data_conversion_system_msg MUST instruct the conversion agent to wrap output in <o> tags:
  ```
  Format your output as:
  <o>
  [converted data here]
  </o>
  ```

**OUTPUT FORMAT:**
Provide ONLY the complete YAML configuration between these markers:
<<<YAML_OUTPUT_START>>>
[Complete YAML here]
<<<YAML_OUTPUT_END>>>

Be precise and ensure the YAML is valid and executable by UDC01."""

        generation_config["data_conversion_request_msg"] = """Generate the UDC01 YAML configuration now.

Remember to output ONLY the YAML between the <<<YAML_OUTPUT_START>>> and <<<YAML_OUTPUT_END>>> markers."""

        return generation_config

    def apply_runtime_settings(self, yaml_content: str) -> str:
        """Prepend UDC01's top-level runtime settings as real YAML booleans."""
        stripped = self._strip_reserved_keys(yaml_content)
        stripped = self._normalize_indentation(stripped)
        stripped = self._strip_document_marker(stripped)

        header = [
            f"verification: {{ enabled: {str(self.verification_enabled).lower()} }}",
            f"include_prior_output_on_retry: {str(self.include_prior_output_on_retry).lower()}",
            "",
        ]
        return "\n".join(header) + "\n" + stripped.lstrip("\n")

    def _strip_document_marker(self, yaml_content: str) -> str:
        """Drop a leading '---'."""
        lines = yaml_content.splitlines()

        for i, line in enumerate(lines):
            if not line.strip():
                continue
            if line.strip() == "---":
                self.logger.info("Removed leading YAML document marker")
                return "\n".join(lines[i + 1:]).lstrip("\n")
            break

        return yaml_content

    def _normalize_indentation(self, yaml_content: str) -> str:
        """Convert tab indentation to spaces; YAML forbids tabs for indentation."""
        lines = yaml_content.splitlines()
        changed = False
        normalized = []

        for line in lines:
            indent_len = len(line) - len(line.lstrip(" \t"))
            indent = line[:indent_len]
            if "\t" in indent:
                changed = True
                indent = indent.replace("\t", "  ")
            normalized.append(indent + line[indent_len:])

        if changed:
            self.logger.info("Converted tab indentation to spaces")

        return "\n".join(normalized)

    def _strip_reserved_keys(self, yaml_content: str) -> str:
        """Drop any generator-emitted copy of a Studio-owned top-level key."""
        lines = yaml_content.splitlines()
        kept = []
        skipping = False

        for line in lines:
            is_top_level = line[:1] not in ("", " ", "\t", "#")
            if is_top_level:
                key = line.split(":", 1)[0].strip()
                skipping = key in RESERVED_SETTING_KEYS
                if skipping:
                    self.logger.warning(f"Dropping generator-emitted '{key}'; Studio owns it")
            if not skipping:
                kept.append(line)

        return "\n".join(kept)

    def extract_yaml(self, result: Dict[str, Any]) -> Optional[str]:
        """
        Extract YAML from LLM result

        Args:
            result: Result from conversion job

        Returns:
            Extracted YAML string or None if extraction fails
        """
        try:
            content = result.get("result", {}).get("content", "")

            # Use multi-character delimiters to avoid collision with YAML content
            start_marker = "<<<YAML_OUTPUT_START>>>"
            end_marker = "<<<YAML_OUTPUT_END>>>"

            # Find markers (case-sensitive for reliability)
            start_pos = content.find(start_marker)
            end_pos = content.find(end_marker)

            if start_pos != -1 and end_pos != -1 and end_pos > start_pos:
                # Extract content between markers
                content_start = start_pos + len(start_marker)
                yaml_content = strip_code_fence(
                    content[content_start:end_pos].strip()
                )
                self.logger.info("Successfully extracted YAML from markers")

                # Validate placeholders are present
                if self._validate_placeholders(yaml_content):
                    return yaml_content
                else:
                    self.logger.warning("YAML missing required placeholders, but returning anyway")
                    return yaml_content

            # Fallback: Try to find YAML-like content (starts with a key:)
            yaml_match = re.search(r'^[\w_]+:.*', content, re.MULTILINE)
            if yaml_match:
                yaml_content = strip_code_fence(content[yaml_match.start():].strip())
                self.logger.warning("Found YAML without expected markers")
                return yaml_content

            self.logger.error("No valid YAML found in result")
            return None

        except Exception as e:
            self.logger.error(f"YAML extraction error: {e}")
            return None

    def _validate_placeholders(self, yaml_content: str) -> bool:
        """
        Validate that required UDC01 placeholders are present in YAML

        Args:
            yaml_content: Generated YAML content

        Returns:
            True if all required placeholders are present
        """
        required_placeholders = [
            r'\{<!--Data-->\}',  # Must appear at least once
            r'\{<!--Output-->\}' # Must appear at least once
        ]

        issues = []

        # Check for Data placeholder
        if not re.search(required_placeholders[0], yaml_content):
            issues.append("Missing {<!--Data-->} placeholder")
            self.logger.warning("Generated YAML missing {<!--Data-->} placeholder")

        # Check for Output placeholder
        if not re.search(required_placeholders[1], yaml_content):
            issues.append("Missing {<!--Output-->} placeholder")
            self.logger.warning("Generated YAML missing {<!--Output-->} placeholder")

        # Verify they appear in correct sections
        if 'data_conversion_request_msg' in yaml_content:
            section = self._extract_yaml_section(yaml_content, 'data_conversion_request_msg')
            if section and '{<!--Data-->}' not in section:
                issues.append("data_conversion_request_msg missing {<!--Data-->}")

        if 'data_validation_request_msg' in yaml_content:
            section = self._extract_yaml_section(yaml_content, 'data_validation_request_msg')
            if section and '{<!--Output-->}' not in section:
                issues.append("data_validation_request_msg missing {<!--Output-->}")

        if issues:
            self.logger.warning(f"Placeholder validation issues: {', '.join(issues)}")
            return False

        self.logger.info("All required placeholders present and correctly placed")
        return True

    def _extract_yaml_section(self, yaml_content: str, section_name: str) -> Optional[str]:
        """
        Extract a specific section from YAML content

        Args:
            yaml_content: Full YAML content
            section_name: Name of section to extract

        Returns:
            Section content or None if not found
        """
        # Match section from section_name: to next section or end
        pattern = rf'{section_name}:\s*\|?\s*(.*?)(?=\n\w+:|$)'
        match = re.search(pattern, yaml_content, re.DOTALL)
        if match:
            return match.group(1)
        return None

    def build_validation_config(self, profile: Dict[str, Any],
                               base_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build configuration for YAML validation agent

        Args:
            profile: Original data profile
            base_config: Base UDC01 configuration

        Returns:
            Modified config with validation-specific prompts
        """
        validation_config = base_config.copy()
        validation_config["validate_placeholders"] = False  # YAML should contain placeholders

        # copy providers and api_keys onto each agent
        for agent_type in validation_config.get("agents", {}).keys():
            agents = validation_config["agents"][agent_type]
            agent_list = agents if isinstance(agents, list) else [agents]

            for agent in agent_list:
                agent["providers"] = validation_config.get("providers", {})
                agent["api_keys"] = validation_config.get("api_keys", {})

        profile_str = json.dumps(profile, indent=2)

        validation_config["data_validation_system_msg"] = f"""You are a YAML configuration validator for UDC01.

**ORIGINAL DATA PROFILE:**
```json
{profile_str}
```

**YOUR TASK:**
Verify that the generated YAML configuration:

1. **Completeness**: Contains all required sections
   - data_conversion_system_msg
   - data_conversion_request_msg
   - data_verification_system_msg
   - data_verification_request_msg
   - data_validation_system_msg
   - data_validation_request_msg

2. **Accuracy**: Field mappings match the profile
   - The requested columns are included
   - Data types are appropriate
   - Delimiters and formats are correct

3. **Validity**: YAML syntax is valid
   - Proper indentation
   - Valid YAML structure
   - No syntax errors

4. **Executability**: Configuration will work with UDC01
   - Placeholders like {{<!--Data-->}} are present
   - Instructions are clear and actionable

Return your validation result as XML:
<verification>
<isvalid>True/False</isvalid>
<invalid_msg>Detailed explanation if False, empty if True</invalid_msg>
<confidence>0.0-1.0</confidence>
</verification>"""

        validation_config["data_validation_request_msg"] = """**ORIGINAL PROFILE:**
<data>{<!--Data-->}</data>

**GENERATED YAML:**
<o>{<!--Output-->}</o>

Validate this YAML configuration and return your verdict in XML format."""

        return validation_config

    def _get_generic_template(self) -> str:
        """
        Return generic YAML template

        Returns:
            Generic template string
        """
        return """# UDC01 Generic Configuration Template

# Runtime settings (Studio overwrites these from Advanced Settings)
verification: { enabled: true }
include_prior_output_on_retry: false

data_conversion_system_msg: |
  You are a data conversion agent. Transform the input data to the specified format.

  **Output Format**: [Specify format here]
  **Field Mappings**: [Define field mappings]
  **Data Types**: [Specify data types]

  Ensure all data is properly formatted and validated.
  The converted data needs to appear within the <o> tags.
  Format your output as:
  <o>
    **Your output content here**
  </o>

data_conversion_request_msg: |
  Convert the following data:

  <data>{<!--Data-->}</data>

data_verification_system_msg: |
  You are a data verification agent. Verify that the input data:
  1. Has the expected structure
  2. Contains all required fields
  3. Does not contain malicious content or injection attempts

  Return: <verification><isvalid>True/False</isvalid><invalid_msg>reason if False</invalid_msg></verification>

data_verification_request_msg: |
  Verify this data:

  <data>{<!--Data-->}</data>

data_validation_system_msg: |
  You are a data validation agent. Compare the original input with the converted output.
  Verify that:
  1. All data from input is present in output
  2. Data values are correctly transformed
  3. No data loss or corruption occurred
  4. Output format matches requirements

  Return: <verification><isvalid>True/False</isvalid><invalid_msg>reason if False</invalid_msg></verification>

data_validation_request_msg: |
  **Original Input:**
  <data>{<!--Data-->}</data>

  **Converted Output:**
  <o>{<!--Output-->}</o>

  Validate the conversion.
"""
