"""Reusable JSON editor component with validation and formatting helpers."""
import json
from typing import Tuple, Optional, Any, Dict
import streamlit as st

def parse_and_validate_json(raw_text: str, label: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Validates that text is valid non-empty JSON object."""
    stripped = raw_text.strip()
    if not stripped:
        return False, None, f"{label} cannot be empty."
    try:
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            return False, None, f"{label} must be a JSON object (enclosed in curly braces {{}})."
        if not parsed:
            return False, None, f"{label} cannot be an empty object {{}}."
        return True, parsed, None
    except json.JSONDecodeError as err:
        return False, None, f"{label} contains invalid JSON: {str(err)}"

def render_json_input_area(key: str, label: str, default_value: str, height: int = 220) -> str:
    """Renders a labeled textarea for JSON entry."""
    return st.text_area(
        label=label,
        value=default_value,
        height=height,
        key=key,
        help=f"Enter valid JSON object for {label}."
    )

