"""Node functions for FOR, AGAINST, and Judge agents."""
import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.schemas.agents import ArgumentAgentOutput, JudgeOutput
from app.schemas.workflow import AgentStatus
from app.graph.prompts import (
    FOR_SYSTEM_PROMPT,
    AGAINST_SYSTEM_PROMPT,
    JUDGE_SYSTEM_PROMPT,
    format_argument_agent_prompt,
    format_judge_prompt,
)
from app.llm.base import BaseChatAdapter

def _get_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()

async def generate_for_node(state: Dict[str, Any], adapter: BaseChatAdapter) -> Dict[str, Any]:
    """Executes the FOR agent to construct evidence-based argument favoring the candidate."""
    start_time = time.perf_counter()
    started_at = _get_iso_now()
    
    source = state["source_input"]
    prompt = format_argument_agent_prompt(
        candidate_profile=source["candidate_profile"],
        job_description=source["job_description"],
        company_context=source["company_context"]
    )

    try:
        result: ArgumentAgentOutput = await adapter.generate_structured(
            prompt=prompt,
            system_prompt=FOR_SYSTEM_PROMPT,
            response_model=ArgumentAgentOutput
        )
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        completed_at = _get_iso_now()

        trace_entry = {
            "model_id": adapter.model_id,
            "status": AgentStatus.COMPLETED,
            "input": {"prompt": prompt},
            "output": result.model_dump(),
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "error": None
        }

        return {
            "for_result": result.model_dump(),
            "agent_traces": {**state.get("agent_traces", {}), "for": trace_entry}
        }
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        completed_at = _get_iso_now()
        error_msg = str(exc)

        trace_entry = {
            "model_id": adapter.model_id,
            "status": AgentStatus.FAILED,
            "input": {"prompt": prompt},
            "output": None,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "error": error_msg
        }

        return {
            "for_result": None,
            "agent_traces": {**state.get("agent_traces", {}), "for": trace_entry},
            "errors": state.get("errors", []) + [f"FOR Agent failed: {error_msg}"]
        }

async def generate_against_node(state: Dict[str, Any], adapter: BaseChatAdapter) -> Dict[str, Any]:
    """Executes the AGAINST agent to construct evidence-based argument against the candidate."""
    start_time = time.perf_counter()
    started_at = _get_iso_now()
    
    source = state["source_input"]
    prompt = format_argument_agent_prompt(
        candidate_profile=source["candidate_profile"],
        job_description=source["job_description"],
        company_context=source["company_context"]
    )

    try:
        result: ArgumentAgentOutput = await adapter.generate_structured(
            prompt=prompt,
            system_prompt=AGAINST_SYSTEM_PROMPT,
            response_model=ArgumentAgentOutput
        )
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        completed_at = _get_iso_now()

        trace_entry = {
            "model_id": adapter.model_id,
            "status": AgentStatus.COMPLETED,
            "input": {"prompt": prompt},
            "output": result.model_dump(),
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "error": None
        }

        return {
            "against_result": result.model_dump(),
            "agent_traces": {**state.get("agent_traces", {}), "against": trace_entry}
        }
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        completed_at = _get_iso_now()
        error_msg = str(exc)

        trace_entry = {
            "model_id": adapter.model_id,
            "status": AgentStatus.FAILED,
            "input": {"prompt": prompt},
            "output": None,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "error": error_msg
        }

        return {
            "against_result": None,
            "agent_traces": {**state.get("agent_traces", {}), "against": trace_entry},
            "errors": state.get("errors", []) + [f"AGAINST Agent failed: {error_msg}"]
        }

async def judge_node(state: Dict[str, Any], adapter: BaseChatAdapter) -> Dict[str, Any]:
    """Executes the model-blind Judge agent to adjudicate the FOR and AGAINST arguments."""
    start_time = time.perf_counter()
    started_at = _get_iso_now()

    source = state["source_input"]
    for_result = state.get("for_result")
    against_result = state.get("against_result")

    # If either argument failed or is missing, skip Judge
    if not for_result or not against_result:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        completed_at = _get_iso_now()
        skip_msg = "Judge skipped because one or both argument agents failed to produce a valid output."
        trace_entry = {
            "model_id": adapter.model_id,
            "status": AgentStatus.SKIPPED,
            "input": {},
            "output": None,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "error": skip_msg
        }
        return {
            "judge_result": None,
            "agent_traces": {**state.get("agent_traces", {}), "judge": trace_entry},
            "errors": state.get("errors", []) + [skip_msg]
        }

    # Format judge prompt excluding ANY model/provider metadata
    prompt = format_judge_prompt(
        candidate_profile=source["candidate_profile"],
        job_description=source["job_description"],
        company_context=source["company_context"],
        for_argument=for_result,
        against_argument=against_result
    )

    try:
        result: JudgeOutput = await adapter.generate_structured(
            prompt=prompt,
            system_prompt=JUDGE_SYSTEM_PROMPT,
            response_model=JudgeOutput
        )
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        completed_at = _get_iso_now()

        trace_entry = {
            "model_id": adapter.model_id,
            "status": AgentStatus.COMPLETED,
            "input": {"prompt": prompt},
            "output": result.model_dump(),
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "error": None
        }

        return {
            "judge_result": result.model_dump(),
            "agent_traces": {**state.get("agent_traces", {}), "judge": trace_entry}
        }
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        completed_at = _get_iso_now()
        error_msg = str(exc)

        trace_entry = {
            "model_id": adapter.model_id,
            "status": AgentStatus.FAILED,
            "input": {"prompt": prompt},
            "output": None,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "error": error_msg
        }

        return {
            "judge_result": None,
            "agent_traces": {**state.get("agent_traces", {}), "judge": trace_entry},
            "errors": state.get("errors", []) + [f"Judge Agent failed: {error_msg}"]
        }

