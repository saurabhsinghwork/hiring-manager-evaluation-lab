"""Tests for TraceCollector and trace sanitization."""
import pytest
from datetime import datetime, timezone
import uuid

from app.services.trace_collector import TraceCollector, sanitize_text, sanitize_value
from app.schemas.evaluations import EvaluationTrace
from app.schemas.workflow import WorkflowStatus, AgentStatus

def test_secret_sanitization():
    """Confirms bearer tokens and API keys are redacted from text and nested structures."""
    dirty_text = "Error calling endpoint with Authorization: Bearer eyJhbGciOiJIUzI1Ni... and key sk-1234567890abcdef123456."
    cleaned = sanitize_text(dirty_text)
    assert "Bearer [REDACTED]" in cleaned
    assert "[REDACTED_KEY]" in cleaned
    assert "sk-1234567890abcdef123456" not in cleaned

    dirty_dict = {
        "headers": {"auth": "Bearer secret-token-xyz"},
        "nested": [{"key": "sk-9876543210fedcba9876"}]
    }
    cleaned_dict = sanitize_value(dirty_dict)
    assert cleaned_dict["headers"]["auth"] == "Bearer [REDACTED]"
    assert cleaned_dict["nested"][0]["key"] == "[REDACTED_KEY]"

def test_trace_collector_on_completed_execution():
    """Generates complete valid EvaluationTrace from completed state."""
    now_iso = datetime.now(timezone.utc).isoformat()
    state = {
        "execution_id": str(uuid.uuid4()),
        "source_input": {
            "candidate_profile": {"name": "Taylor"},
            "job_description": {"title": "Director"},
            "company_context": {"stage": "Growth"}
        },
        "input_hash": "a" * 64,
        "model_config_key": "chatgpt_paid",
        "for_result": {"argument": "Good fit", "confidence_score": 8, "supporting_evidence": [{"source_field": "title", "exact_value": "Director"}]},
        "against_result": {"argument": "Not fit", "confidence_score": 4, "supporting_evidence": [{"source_field": "title", "exact_value": "Director"}]},
        "judge_result": {
            "decision": "FOR",
            "winning_argument": "Good fit",
            "reasoning": "Strong match",
            "confidence_percentage": 85
        },
        "agent_traces": {
            "for": {
                "model_id": "gpt-4o",
                "status": AgentStatus.COMPLETED,
                "input": {"prompt": "Prompt for agent with Bearer eyJhbGciOiJIUz..."},
                "output": {"argument": "Good fit"},
                "started_at": now_iso,
                "completed_at": now_iso,
                "duration_ms": 1100,
                "error": None
            },
            "against": {
                "model_id": "gpt-4o",
                "status": AgentStatus.COMPLETED,
                "input": {"prompt": "Prompt against"},
                "output": {"argument": "Not fit"},
                "started_at": now_iso,
                "completed_at": now_iso,
                "duration_ms": 1050,
                "error": None
            },
            "judge": {
                "model_id": "gpt-4o",
                "status": AgentStatus.COMPLETED,
                "input": {"prompt": "Judge prompt without model identity"},
                "output": {"decision": "FOR"},
                "started_at": now_iso,
                "completed_at": now_iso,
                "duration_ms": 1300,
                "error": None
            }
        },
        "errors": [],
        "started_at": now_iso,
        "completed_at": now_iso,
        "duration_ms": 3450,
        "workflow_status": WorkflowStatus.COMPLETED.value
    }

    trace = TraceCollector.build_trace_from_state(state)
    assert isinstance(trace, EvaluationTrace)
    assert trace.workflow_status == WorkflowStatus.COMPLETED
    assert trace.agents["for"].status == AgentStatus.COMPLETED
    assert trace.agents["against"].status == AgentStatus.COMPLETED
    assert trace.agents["judge"].status == AgentStatus.COMPLETED
    assert trace.judge_result.decision == "FOR"
    # Ensure bearer token in agent prompt input was redacted
    assert "Bearer [REDACTED]" in trace.agents["for"].input["prompt"]

def test_trace_collector_on_failed_execution():
    """Generates complete inspectable trace even when execution fails and Judge is skipped."""
    now_iso = datetime.now(timezone.utc).isoformat()
    state = {
        "execution_id": str(uuid.uuid4()),
        "source_input": {"candidate_profile": {"name": "Jordan"}, "job_description": {}, "company_context": {}},
        "input_hash": "hash123",
        "model_config_key": "qwen",
        "for_result": None,
        "against_result": None,
        "judge_result": None,
        "agent_traces": {
            "for": {
                "model_id": "qwen-2.5-72b-instruct",
                "status": AgentStatus.FAILED,
                "input": {"prompt": "Test"},
                "output": None,
                "started_at": now_iso,
                "completed_at": now_iso,
                "duration_ms": 500,
                "error": "Connection timeout using api_key=sk-1234567890abcdef"
            }
        },
        "errors": ["FOR Agent failed: Connection timeout using api_key=sk-1234567890abcdef"],
        "started_at": now_iso,
        "completed_at": now_iso,
        "duration_ms": 500,
        "workflow_status": WorkflowStatus.FAILED.value
    }

    trace = TraceCollector.build_trace_from_state(state)
    assert trace.workflow_status == WorkflowStatus.FAILED
    assert trace.agents["for"].status == AgentStatus.FAILED
    assert "[REDACTED_KEY]" in trace.agents["for"].error
    # Against and judge were automatically captured as SKIPPED
    assert trace.agents["against"].status == AgentStatus.SKIPPED
    assert trace.agents["judge"].status == AgentStatus.SKIPPED
    assert trace.judge_result is None
    assert len(trace.errors) == 1
    assert "[REDACTED_KEY]" in trace.errors[0]

