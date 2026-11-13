"""Unit tests for agent prompts and graph nodes."""
import pytest
from typing import Type, TypeVar
from pydantic import BaseModel

from app.llm.base import BaseChatAdapter
from app.schemas.agents import ArgumentAgentOutput, EvidenceItem, JudgeOutput
from app.schemas.workflow import AgentStatus
from app.graph.prompts import (
    format_argument_agent_prompt,
    format_judge_prompt,
    JUDGE_SYSTEM_PROMPT
)
from app.graph.nodes import (
    generate_for_node,
    generate_against_node,
    judge_node
)

T = TypeVar("T", bound=BaseModel)

class FakeTestingAdapter(BaseChatAdapter):
    """Deterministic adapter for verifying node contracts without network access."""
    def __init__(self, should_fail: bool = False):
        super().__init__(model_id="test-model-4o", provider_name="fake_provider")
        self.should_fail = should_fail
        self.last_prompt = ""
        self.last_system_prompt = ""

    async def generate_structured(self, prompt: str, system_prompt: str, response_model: Type[T]) -> T:
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        if self.should_fail:
            raise RuntimeError("Simulated API 500 error from provider")

        if response_model == ArgumentAgentOutput:
            return ArgumentAgentOutput(
                argument="Test argument showing candidate has relevant leadership background.",
                supporting_evidence=[
                    EvidenceItem(source_field="candidate_profile.title", exact_value="Engineering Lead")
                ],
                confidence_score=8
            )
        elif response_model == JudgeOutput:
            return JudgeOutput(
                decision="FOR",
                winning_argument="Test argument showing candidate has relevant leadership background.",
                reasoning="The candidate demonstrates verified leadership alignment.",
                confidence_percentage=85
            )
        raise ValueError(f"Unknown response model: {response_model}")

@pytest.fixture
def sample_state():
    return {
        "execution_id": "test-uuid-1234",
        "source_input": {
            "candidate_profile": {"name": "Jordan Smith", "title": "Engineering Lead"},
            "job_description": {"title": "Engineering Manager", "department": "Core Platform"},
            "company_context": {"size": "500+", "domain": "Enterprise Cloud"}
        },
        "agent_traces": {},
        "errors": []
    }

@pytest.mark.asyncio
async def test_generate_for_node_success(sample_state):
    adapter = FakeTestingAdapter()
    result = await generate_for_node(sample_state, adapter)
    
    assert result["for_result"] is not None
    assert result["for_result"]["confidence_score"] == 8
    assert "for" in result["agent_traces"]
    assert result["agent_traces"]["for"]["status"] == AgentStatus.COMPLETED
    assert result["agent_traces"]["for"]["model_id"] == "test-model-4o"

@pytest.mark.asyncio
async def test_generate_against_node_success(sample_state):
    adapter = FakeTestingAdapter()
    result = await generate_against_node(sample_state, adapter)
    
    assert result["against_result"] is not None
    assert "against" in result["agent_traces"]
    assert result["agent_traces"]["against"]["status"] == AgentStatus.COMPLETED

@pytest.mark.asyncio
async def test_judge_node_success(sample_state):
    adapter = FakeTestingAdapter()
    sample_state["for_result"] = {
        "argument": "Candidate is lead",
        "supporting_evidence": [{"source_field": "candidate_profile.title", "exact_value": "Engineering Lead"}],
        "confidence_score": 8
    }
    sample_state["against_result"] = {
        "argument": "Candidate lacks platform scale",
        "supporting_evidence": [{"source_field": "candidate_profile.title", "exact_value": "Engineering Lead"}],
        "confidence_score": 5
    }
    
    result = await judge_node(sample_state, adapter)
    assert result["judge_result"] is not None
    assert result["judge_result"]["decision"] == "FOR"
    assert result["judge_result"]["confidence_percentage"] == 85
    assert result["agent_traces"]["judge"]["status"] == AgentStatus.COMPLETED
    
    # Model identity MUST NOT be in the judge prompt
    assert "test-model-4o" not in adapter.last_prompt
    assert "fake_provider" not in adapter.last_prompt

@pytest.mark.asyncio
async def test_judge_node_skipped_on_missing_argument(sample_state):
    adapter = FakeTestingAdapter()
    sample_state["for_result"] = None  # FOR failed!
    sample_state["against_result"] = {"argument": "Against text"}

    result = await judge_node(sample_state, adapter)
    assert result["judge_result"] is None
    assert result["agent_traces"]["judge"]["status"] == AgentStatus.SKIPPED
    assert any("skipped" in err.lower() for err in result["errors"])

@pytest.mark.asyncio
async def test_node_failure_handling_no_retry(sample_state):
    failing_adapter = FakeTestingAdapter(should_fail=True)
    result = await generate_for_node(sample_state, failing_adapter)
    
    assert result["for_result"] is None
    assert result["agent_traces"]["for"]["status"] == AgentStatus.FAILED
    assert "Simulated API 500 error" in result["agent_traces"]["for"]["error"]
    assert len(result["errors"]) == 1

