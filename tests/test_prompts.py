"""Tests for the hiring-manager doctrine prompts and the derived-signals pre-analysis."""
import json
from pathlib import Path

import pytest

from app.graph.prompts import (
    AGAINST_SYSTEM_PROMPT,
    FOR_SYSTEM_PROMPT,
    HIRING_MANAGER_DOCTRINE,
    JUDGE_SYSTEM_PROMPT,
    format_argument_agent_prompt,
    format_judge_prompt,
)
from app.graph.signals import (
    derive_company_size,
    derive_context_signals,
    derive_sector,
    size_tier_for,
)

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"


# --------------------------------------------------------------------------- #
# Company-size derivation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "count,tier",
    [(1, "MICRO"), (10, "MICRO"), (11, "SMALL"), (50, "SMALL"), (51, "GROWTH"), (200, "GROWTH"),
     (201, "MID_SIZE"), (1000, "MID_SIZE"), (1001, "LARGE"), (10000, "LARGE"), (10001, "ENTERPRISE")],
)
def test_size_tier_boundaries(count, tier):
    assert size_tier_for(count) == tier


@pytest.mark.parametrize(
    "context,tier",
    [
        ({"company_size": "51-200 employees"}, "GROWTH"),
        ({"company_size": "11-50 employees"}, "SMALL"),
        ({"company_size": "10,001+ employees"}, "ENTERPRISE"),
        ({"company_size": "5,001-10,000 employees"}, "LARGE"),
        ({"headcount": 1400}, "LARGE"),
        ({"employee_count": 8}, "MICRO"),
        ({"employee_count": 12}, "SMALL"),
        ({"org": {"num_employees": "250"}}, "MID_SIZE"),
        ({"company_size": "1-200"}, "MICRO_TO_GROWTH"),
    ],
)
def test_company_size_structured_fields(context, tier):
    assert derive_company_size(context)["size_tier"] == tier


def test_company_size_open_ended_is_flagged():
    result = derive_company_size({"size": "500+"})
    assert result["size_tier"] == "MID_SIZE"
    assert result["open_ended_lower_bound"] is True


def test_company_size_text_fallback_and_unknown():
    text = derive_company_size({"company_overview": "We are a team of 40 employees building tools."})
    assert text["size_tier"] == "SMALL"
    assert text["basis"] == "TEXT_MENTION"
    unknown = derive_company_size({"company_name": "Acme", "industry": "Widgets"})
    assert unknown["size_tier"] == "UNKNOWN"
    assert unknown["basis"] == "NONE"


def test_company_size_ignores_booleans_and_placeholders():
    assert derive_company_size({"size": True})["size_tier"] == "UNKNOWN"
    assert derive_company_size({"company_size": "Not Available"})["size_tier"] == "UNKNOWN"


# --------------------------------------------------------------------------- #
# Sector and title hints
# --------------------------------------------------------------------------- #
def test_sector_detection_prefers_industry_field():
    assert derive_sector({"industry": "Investment Banking", "company_name": "BNY"})["sector_hint"] == "FINANCIAL_SERVICES"
    assert derive_sector({"industry": "IT System Custom Software Development"})["sector_hint"] == "TECHNOLOGY"
    assert derive_sector({"company_name": "X"})["sector_hint"] == "UNKNOWN"
    # An explicit non-matching industry must not be overridden by a stray overview word.
    travel = derive_sector({"industry": "Travel Arrangements", "company_overview": "We work with every bank."})
    assert travel["sector_hint"] == "OTHER"
    # With no industry field, the overview is the fallback.
    assert derive_sector({"company_overview": "A regional bank serving small business."})["sector_hint"] == "FINANCIAL_SERVICES"


def _titles(cand_title: str, jd_title: str = "Engineer"):
    signals = derive_context_signals(
        {"current_title": cand_title}, {"job_title": jd_title}, {"company_name": "Acme", "headcount": 100}
    )
    return signals["person_titles"][0]["keyword_hints"]


def test_title_keyword_hints():
    assert "VICE_PRESIDENT" in _titles("Vice President, Software Engineering")
    assert "PRESIDENT" not in _titles("Vice President, Software Engineering")
    assert "PRESIDENT" in _titles("President & CEO")
    assert "EVP_SVP" in _titles("Senior Vice President of Technology")
    assert "RECRUITING_OR_PEOPLE_OPS" in _titles("Senior Technical Recruiter")
    assert "NON_PEOPLE_MANAGER_TYPE" in _titles("Senior Product Manager")
    assert "ADVISORY_OR_INVESTOR" in _titles("Startup Advisor / Venture Capital")
    assert "FOUNDER_OWNER" in _titles("Co-Founder & CTO")


# --------------------------------------------------------------------------- #
# Employer match and authoritative statements
# --------------------------------------------------------------------------- #
def test_employer_match_found_and_missing():
    found = derive_context_signals(
        {"experiences": [{"title": "Engineering Manager", "company": "Wilcore Technologies, Inc."}]},
        {"job_title": "DevOps Engineer"},
        {"company_name": "Wilcore Technologies, Inc.", "company_size": "51-200 employees"},
    )
    assert found["employer_match"]["found_in_profile_at"]

    missing = derive_context_signals(
        {"current_title": "VP Engineering at Globex"},
        {"job_title": "DevOps Engineer"},
        {"company_name": "Wilcore Technologies, Inc."},
    )
    assert missing["employer_match"]["found_in_profile_at"] == []
    assert "NOT found" in missing["employer_match"]["note"]


def test_generic_company_name_is_not_matched():
    signals = derive_context_signals(
        {"current_title": "Engineer at Technology firm"}, {"job_title": "x"}, {"company_name": "Technology Company"}
    )
    assert signals["employer_match"]["found_in_profile_at"] == []
    assert "generic" in signals["employer_match"]["note"]


def test_explicit_authority_statements_extracted():
    signals = derive_context_signals(
        {"current_title": "Director of Cloud Infrastructure"},
        {"title": "Staff SRE", "reporting_to": "Director of Cloud Infrastructure", "level": "Not Available"},
        {"company_name": "NovaScale", "hiring_policy": "Staff openings are owned by the divisional Director."},
    )
    jd_paths = [i["path"] for i in signals["explicit_authority_statements"]["job_description_fields"]]
    co_paths = [i["path"] for i in signals["explicit_authority_statements"]["company_context_fields"]]
    assert "job_description.reporting_to" in jd_paths
    assert "company_context.hiring_policy" in co_paths


def test_signals_never_raise_on_odd_input():
    signals = derive_context_signals({"experiences": "not a list"}, {"title": None}, {"headcount": {"a": [1, 2]}})
    assert isinstance(signals, dict)
    json.dumps(signals)  # must be serializable


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #
def test_agent_prompts_share_the_doctrine_and_route_uniquely():
    for prompt in (FOR_SYSTEM_PROMPT, AGAINST_SYSTEM_PROMPT, JUDGE_SYSTEM_PROMPT):
        assert HIRING_MANAGER_DOCTRINE in prompt

    # Routing markers relied on by test doubles and trace tooling must stay unambiguous.
    assert "FOR Argument Generation" in FOR_SYSTEM_PROMPT
    assert "AGAINST Argument Generation" not in FOR_SYSTEM_PROMPT
    assert "AGAINST Argument Generation" in AGAINST_SYSTEM_PROMPT
    assert "FOR Argument Generation" not in AGAINST_SYSTEM_PROMPT
    assert "Judge Agent" in JUDGE_SYSTEM_PROMPT
    for prompt in (JUDGE_SYSTEM_PROMPT,):
        assert "FOR Argument Generation" not in prompt
        assert "AGAINST Argument Generation" not in prompt


@pytest.mark.parametrize(
    "needle",
    [
        "Gate 1", "Gate 2", "Gate 3",
        "MICRO", "SMALL", "GROWTH", "MID_SIZE", "LARGE", "ENTERPRISE",
        "Vice President", "Managing Director", "FINANCIAL SERVICES",
        "Reach rule", "what would change the answer", "reporting_to",
    ],
)
def test_doctrine_covers_required_edge_cases(needle):
    assert needle.lower() in HIRING_MANAGER_DOCTRINE.lower()


def test_prompts_do_not_contradict_the_enforced_schema():
    """Prompts must not carry their own JSON templates or allow empty evidence (schema needs >= 1)."""
    for prompt in (FOR_SYSTEM_PROMPT, AGAINST_SYSTEM_PROMPT):
        assert "empty evidence array" not in prompt
        assert '"main_argument"' not in prompt
        assert "supporting_evidence" in prompt
        assert "confidence_score" in prompt
    assert "decision" in JUDGE_SYSTEM_PROMPT
    assert "confidence_percentage" in JUDGE_SYSTEM_PROMPT
    assert '"final_verdict"' not in JUDGE_SYSTEM_PROMPT


def test_format_prompts_include_signals_and_exclude_model_metadata():
    cand = {"current_title": "Vice President, Engineering", "experiences": [{"company": "Acme Bank"}]}
    jd = {"job_title": "Senior Engineer", "reporting_to": "VP Engineering"}
    co = {"company_name": "Acme Bank", "industry": "Banking", "company_size": "10,001+ employees"}
    agent_prompt = format_argument_agent_prompt(cand, jd, co)
    assert "DERIVED CONTEXT SIGNALS" in agent_prompt
    assert '"size_tier": "ENTERPRISE"' in agent_prompt
    assert '"sector_hint": "FINANCIAL_SERVICES"' in agent_prompt

    judge_prompt = format_judge_prompt(
        cand, jd, co,
        {"argument": "* for", "confidence_score": 7, "supporting_evidence": []},
        {"argument": "* against", "confidence_score": 5, "supporting_evidence": []},
    )
    assert "DERIVED CONTEXT SIGNALS" in judge_prompt
    assert "* for" in judge_prompt and "* against" in judge_prompt


def test_real_samples_produce_sensible_signals():
    """The bundled synthetic sample yields sensible signals without external data."""
    strong = json.loads((SAMPLES / "strong_match.json").read_text(encoding="utf-8"))
    signals = derive_context_signals(strong["candidate_profile"], strong["job_description"], strong["company_context"])
    assert signals["company_size"]["size_tier"] == "LARGE"
    jd_paths = [i["path"] for i in signals["explicit_authority_statements"]["job_description_fields"]]
    assert "job_description.reporting_to" in jd_paths


@pytest.mark.parametrize(
    "needle",
    [
        "OWNING-FUNCTION-HEAD RULE",
        "STRUCTURAL PLAUSIBILITY IS THE NORMAL BASIS",
        "never require, wait for, or penalize the absence of a reporting line",
        "different sub-specialty",
    ],
)
def test_doctrine_handles_missing_reporting_lines_and_small_company_heads(needle):
    assert needle in HIRING_MANAGER_DOCTRINE
    assert needle in JUDGE_SYSTEM_PROMPT or needle.lower() in JUDGE_SYSTEM_PROMPT.lower()
