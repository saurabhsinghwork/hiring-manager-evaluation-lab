"""Unit tests verifying all Pydantic contracts and validation rules."""
import pytest
from pydantic import ValidationError
import uuid
from datetime import datetime, timezone

from app.schemas.inputs import WorkflowRequest
from app.schemas.agents import EvidenceItem, ArgumentAgentOutput, JudgeOutput
from app.schemas.workflow import WorkflowStatus, AgentStatus, WorkflowResponse
from app.schemas.evaluations import AgentTrace, EvaluationTrace

def test_workflow_request_valid():
    """Valid request parses successfully and computes stable input hash."""
    req_data = {
        "candidate_profile": {"name": "Alex Taylor", "title": "Engineering Director", "experience_years": 12},
        "job_description": {"title": "Senior Engineering Manager", "department": "Platform"},
        "company_context": {"industry": "FinTech", "stage": "Series C"},
        "model_config": "gpt_oss_120b"
    }
    req = WorkflowRequest(**req_data)
    assert req.model_config_key == "gpt_oss_120b"
    hash1 = req.compute_input_hash()
    hash2 = req.compute_input_hash()
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex string

def test_workflow_request_rejects_empty_objects():
    """Empty dictionary for any required top-level object must fail validation."""
    with pytest.raises(ValidationError):
        WorkflowRequest(
            candidate_profile={},
            job_description={"title": "Manager"},
            company_context={"industry": "Tech"},
            model_config="gpt_oss_120b"
        )

def test_argument_agent_output_valid():
    """Valid argument agent output validates cleanly."""
    data = {
        "argument": "Alex Taylor has 12 years of relevant engineering management experience.",
        "supporting_evidence": [
            {"source_field": "candidate_profile.title", "exact_value": "Engineering Director"},
            {"source_field": "candidate_profile.experience_years", "exact_value": "12"}
        ],
        "confidence_score": 8
    }
    out = ArgumentAgentOutput(**data)
    assert out.confidence_score == 8
    assert len(out.supporting_evidence) == 2

def test_argument_agent_output_invalid_confidence():
    """Confidence score must be clamped between 0 and 10."""
    with pytest.raises(ValidationError):
        ArgumentAgentOutput(
            argument="Valid argument text.",
            supporting_evidence=[{"source_field": "field", "exact_value": "value"}],
            confidence_score=15  # Out of range!
        )

def test_argument_agent_output_requires_evidence():
    """Empty supporting evidence must be rejected."""
    with pytest.raises(ValidationError):
        ArgumentAgentOutput(
            argument="Valid argument text.",
            supporting_evidence=[],  # Invalid: min_length=1
            confidence_score=7
        )

def test_judge_output_binary_decision():
    """Judge output must only accept 'FOR' or 'AGAINST'."""
    valid_data = {
        "decision": "FOR",
        "winning_argument": "Alex Taylor matches the technical leadership requirements.",
        "reasoning": "The FOR case demonstrated direct alignment with platform leadership needs.",
        "confidence_percentage": 85
    }
    judge = JudgeOutput(**valid_data)
    assert judge.decision == "FOR"

    # Must reject non-binary decisions
    invalid_data = valid_data.copy()
    invalid_data["decision"] = "INSUFFICIENT_EVIDENCE"
    with pytest.raises(ValidationError):
        JudgeOutput(**invalid_data)

def test_evaluation_trace_roundtrip():
    """Complete EvaluationTrace object serializes and validates."""
    now_iso = datetime.now(timezone.utc).isoformat()
    trace_data = {
        "execution_id": str(uuid.uuid4()),
        "created_at": now_iso,
        "completed_at": now_iso,
        "source_input": {
            "candidate_profile": {"name": "Alex"},
            "job_description": {"title": "Manager"},
            "company_context": {"stage": "Growth"}
        },
        "input_hash": "a" * 64,
        "model_config": "gpt_oss_120b",
        "workflow_status": WorkflowStatus.COMPLETED,
        "agents": {
            "for": AgentTrace(
                model_id="gpt-oss-120b",
                status=AgentStatus.COMPLETED,
                input={"prompt": "Evaluate FOR"},
                output={"argument": "Good match", "confidence_score": 8},
                started_at=now_iso,
                completed_at=now_iso,
                duration_ms=1200
            ),
            "against": AgentTrace(
                model_id="gpt-oss-120b",
                status=AgentStatus.COMPLETED,
                input={"prompt": "Evaluate AGAINST"},
                output={"argument": "Not a fit", "confidence_score": 4},
                started_at=now_iso,
                completed_at=now_iso,
                duration_ms=1150
            ),
            "judge": AgentTrace(
                model_id="gpt-oss-120b",
                status=AgentStatus.COMPLETED,
                input={"prompt": "Blind adjudication"},
                output={"decision": "FOR", "confidence_percentage": 85},
                started_at=now_iso,
                completed_at=now_iso,
                duration_ms=1500
            )
        },
        "judge_result": JudgeOutput(
            decision="FOR",
            winning_argument="Alex matches the technical leadership requirements.",
            reasoning="The FOR case is solidly grounded in the candidate's verified record.",
            confidence_percentage=85
        ),
        "duration_ms": 3850,
        "errors": []
    }
    trace = EvaluationTrace(**trace_data)
    assert trace.workflow_status == WorkflowStatus.COMPLETED
    assert trace.agents["for"].status == AgentStatus.COMPLETED
    assert trace.judge_result.decision == "FOR"
    dumped = trace.model_dump(by_alias=True)
    assert dumped["model_config"] == "gpt_oss_120b"
