"""Tests for LangGraph state machine assembly and execution."""
import pytest
from datetime import datetime, timezone
import uuid

from app.graph.workflow import build_evaluation_graph
from app.schemas.workflow import WorkflowStatus, AgentStatus
from app.schemas.agents import ArgumentAgentOutput, EvidenceItem, JudgeOutput
from app.llm.base import BaseChatAdapter

class WorkflowMockAdapter(BaseChatAdapter):
    """Configurable mock adapter for end-to-end graph testing."""
    def __init__(self, fail_for: bool = False, fail_judge: bool = False):
        super().__init__(model_id="mock-gpt-4o", provider_name="mock_provider")
        self.fail_for = fail_for
        self.fail_judge = fail_judge
        self.call_counts = {"for": 0, "against": 0, "judge": 0}

    async def generate_structured(self, prompt: str, system_prompt: str, response_model):
        if "FOR Argument Generation" in system_prompt:
            self.call_counts["for"] += 1
            if self.fail_for:
                raise RuntimeError("Simulated FOR failure")
            return ArgumentAgentOutput(
                argument="Candidate has direct engineering management experience in fintech.",
                supporting_evidence=[
                    EvidenceItem(source_field="candidate_profile.title", exact_value="VP Engineering")
                ],
                confidence_score=9
            )
        elif "AGAINST Argument Generation" in system_prompt:
            self.call_counts["against"] += 1
            return ArgumentAgentOutput(
                argument="Candidate tenure in current role is under one year.",
                supporting_evidence=[
                    EvidenceItem(source_field="candidate_profile.tenure", exact_value="8 months")
                ],
                confidence_score=6
            )
        elif "Judge Agent" in system_prompt:
            self.call_counts["judge"] += 1
            if self.fail_judge:
                raise RuntimeError("Simulated Judge failure")
            return JudgeOutput(
                decision="FOR",
                winning_argument="Candidate has direct engineering management experience in fintech.",
                reasoning="The candidate's VP Engineering role strongly supports the hiring manager position.",
                confidence_percentage=82
            )
        raise ValueError(f"Unexpected prompt: {system_prompt}")

@pytest.fixture
def initial_graph_input():
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "execution_id": str(uuid.uuid4()),
        "source_input": {
            "candidate_profile": {"name": "Morgan Davis", "title": "VP Engineering", "tenure": "8 months"},
            "job_description": {"title": "Engineering Director", "department": "Core Banking"},
            "company_context": {"domain": "Fintech", "scale": "Enterprise"}
        },
        "input_hash": "dummyhash123",
        "model_config_key": "chatgpt_paid",
        "for_result": None,
        "against_result": None,
        "judge_result": None,
        "agent_traces": {},
        "errors": [],
        "started_at": now_iso,
        "completed_at": None,
        "duration_ms": 0,
        "workflow_status": WorkflowStatus.QUEUED
    }

@pytest.mark.asyncio
async def test_full_graph_successful_execution(initial_graph_input):
    """Complete workflow invocation executes parallel branches, join, and judge."""
    adapter = WorkflowMockAdapter()
    graph = build_evaluation_graph(adapter)

    final_state = await graph.ainvoke(initial_graph_input)

    assert final_state["workflow_status"] == WorkflowStatus.COMPLETED
    assert final_state["for_result"] is not None
    assert final_state["against_result"] is not None
    assert final_state["judge_result"] is not None
    assert final_state["judge_result"]["decision"] == "FOR"

    # Verify both argument agents were called concurrently
    assert adapter.call_counts["for"] == 1
    assert adapter.call_counts["against"] == 1
    assert adapter.call_counts["judge"] == 1

    # Verify traces are merged properly
    traces = final_state["agent_traces"]
    assert "for" in traces and traces["for"]["status"] == AgentStatus.COMPLETED
    assert "against" in traces and traces["against"]["status"] == AgentStatus.COMPLETED
    assert "judge" in traces and traces["judge"]["status"] == AgentStatus.COMPLETED

    assert final_state["duration_ms"] >= 0
    assert final_state["completed_at"] is not None

@pytest.mark.asyncio
async def test_graph_skips_judge_on_argument_failure(initial_graph_input):
    """When FOR agent fails, join step routes directly to finalize without running Judge."""
    adapter = WorkflowMockAdapter(fail_for=True)
    graph = build_evaluation_graph(adapter)

    final_state = await graph.ainvoke(initial_graph_input)

    assert final_state["workflow_status"] == WorkflowStatus.FAILED
    assert final_state["for_result"] is None
    assert final_state["against_result"] is not None
    assert final_state["judge_result"] is None

    # Judge must NEVER be called
    assert adapter.call_counts["judge"] == 0

    # Traces must reflect failure and skip
    traces = final_state["agent_traces"]
    assert traces["for"]["status"] == AgentStatus.FAILED
    assert traces["against"]["status"] == AgentStatus.COMPLETED
    assert traces["judge"]["status"] == AgentStatus.SKIPPED
    assert len(final_state["errors"]) >= 1

