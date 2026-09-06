"""
Shared helpers for parsing LLM output
"""

import json
import logging
import re
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)


def strip_code_fence(text: str) -> str:
    """Remove a markdown code fence the model wrapped around its output."""
    lines = text.splitlines()

    while lines and not lines[0].strip():
        lines.pop(0)

    if lines and lines[0].lstrip().startswith("```"):
        lines.pop(0)
        while lines and not lines[-1].lstrip().startswith("```"):
            if lines[-1].strip():
                break
            lines.pop()
        if lines and lines[-1].lstrip().startswith("```"):
            lines.pop()
        logger.debug("Stripped code fence from extracted output")

    return "\n".join(lines).strip()


def _remove_comments(text: str) -> str:
    """Drop // and /* */ comments that JSON does not allow."""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    return re.sub(r'(^|\s)//[^\n]*', r'\1', text)


def _remove_trailing_commas(text: str) -> str:
    """Drop commas that sit immediately before a closing brace or bracket."""
    return re.sub(r',(\s*[}\]])', r'\1', text)


def loads_forgiving(text: str) -> Tuple[Optional[Any], Optional[str]]:
    """Parse JSON, retrying once with comments and trailing commas removed.

    Returns (parsed, None) on success or (None, error message) on failure.
    """
    if not text or not text.strip():
        return None, "empty JSON payload"

    candidate = strip_code_fence(text)

    try:
        return json.loads(candidate), None
    except json.JSONDecodeError as first_error:
        repaired = _remove_trailing_commas(_remove_comments(candidate))
        if repaired != candidate:
            try:
                parsed = json.loads(repaired)
                logger.info("Parsed JSON after removing comments/trailing commas")
                return parsed, None
            except json.JSONDecodeError:
                pass
        return None, f"invalid JSON: {first_error}"
