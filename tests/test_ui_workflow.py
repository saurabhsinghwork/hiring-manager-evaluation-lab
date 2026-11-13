"""Tests for Streamlit Workflow Tab components and validation."""
import pytest
from app.ui.components.json_editor import parse_and_validate_json
from app.ui.sample_data import SCENARIO_STRONG_MATCH, SCENARIO_DISPUTED_MATCH

def test_json_editor_validation_valid():
    text = '{"name": "Elena", "title": "Director"}'
    valid, parsed, err = parse_and_validate_json(text, "Candidate Profile")
    assert valid is True
    assert parsed["name"] == "Elena"
    assert err is None

def test_json_editor_validation_empty_string():
    valid, parsed, err = parse_and_validate_json("   ", "Candidate Profile")
    assert valid is False
    assert "cannot be empty" in err

def test_json_editor_validation_empty_object():
    valid, parsed, err = parse_and_validate_json("{}", "Candidate Profile")
    assert valid is False
    assert "cannot be an empty object" in err

def test_json_editor_validation_invalid_syntax():
    valid, parsed, err = parse_and_validate_json("{invalid json}", "Candidate Profile")
    assert valid is False
    assert "contains invalid JSON" in err

def test_sample_scenarios_are_valid():
    assert "candidate_profile" in SCENARIO_STRONG_MATCH
    assert "job_description" in SCENARIO_STRONG_MATCH
    assert "company_context" in SCENARIO_STRONG_MATCH
    assert "candidate_profile" in SCENARIO_DISPUTED_MATCH

