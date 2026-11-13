"""Trace collector for capturing, sanitizing, and packaging execution traces."""
import re
from typing import Any, Dict
from datetime import datetime, timezone

from app.schemas.evaluations import EvaluationTrace, AgentTrace
from app.schemas.agents import JudgeOutput
from app.schemas.workflow import WorkflowStatus, AgentStatus
from app.graph.state import GraphState

SECRET_PATTERNS = [
    (re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]+", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"sk-[a-zA-Z0-9_\-\.]{15,}", re.IGNORECASE), "[REDACTED_KEY]"),
    (re.compile(r"api[-_]?key\s*[:=]\s*['\"]?[a-zA-Z0-9_\-\.]+['\"]?", re.IGNORECASE), "api_key=[REDACTED]"),
]

def sanitize_text(text: str) -> str:
    """Removes sensitive authorization tokens and API keys from arbitrary text."""
    sanitized = text
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized

def sanitize_value(val: Any) -> Any:
    """Recursively sanitizes dictionaries, lists, and strings."""
    if isinstance(val, str):
        return sanitize_text(val)
    elif isinstance(val, dict):
        return {k: sanitize_value(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [sanitize_value(item) for item in val]
    return val

class TraceCollector:
    """Orchestration-level collector that builds complete inspectable traces."""

    @staticmethod
    def build_trace_from_state(state: GraphState) -> EvaluationTrace:
        """Constructs and validates a full EvaluationTrace from the final GraphState."""
        now_iso = datetime.now(timezone.utc).isoformat()
        created_at = state.get("started_at") or now_iso
        completed_at = state.get("completed_at") or now_iso

        # Extract agent traces with default fallback envelopes
        raw_traces = state.get("agent_traces", {})
        processed_agents: Dict[str, AgentTrace] = {}

        for role in ["for", "against", "judge"]:
            if role in raw_traces:
                entry = raw_traces[role]
                sanitized_input = sanitize_value(entry.get("input", {}))
                sanitized_output = sanitize_value(entry.get("output"))
                sanitized_error = sanitize_text(entry.get("error", "")) if entry.get("error") else None

                processed_agents[role] = AgentTrace(
                    model_id=entry.get("model_id", "unknown"),
                    status=entry.get("status", AgentStatus.PENDING),
                    input=sanitized_input,
                    output=sanitized_output,
                    started_at=entry.get("started_at", created_at),
                    completed_at=entry.get("completed_at", completed_at),
                    duration_ms=entry.get("duration_ms", 0),
                    error=sanitized_error
                )
            else:
                # Agent did not execute
                processed_agents[role] = AgentTrace(
                    model_id=state.get("model_config_key", "unknown"),
                    status=AgentStatus.SKIPPED,
                    input={},
                    output=None,
                    started_at=created_at,
                    completed_at=completed_at,
                    duration_ms=0,
                    error=f"{role.upper()} agent did not execute."
                )

        # Parse Judge output if present
        judge_result = None
        if state.get("judge_result"):
            try:
                judge_result = JudgeOutput.model_validate(state["judge_result"])
            except Exception:
                judge_result = None

        # Sanitize top-level errors
        raw_errors = state.get("errors", [])
        sanitized_errors = [sanitize_text(err) for err in raw_errors]

        # Determine overall workflow status
        wf_status_str = state.get("workflow_status", WorkflowStatus.FAILED)
        try:
            wf_status = WorkflowStatus(wf_status_str)
        except ValueError:
            wf_status = WorkflowStatus.FAILED

        return EvaluationTrace(
            execution_id=state["execution_id"],
            created_at=created_at,
            completed_at=completed_at,
            source_input=sanitize_value(state["source_input"]),
            input_hash=state.get("input_hash", ""),
            model_config_key=state["model_config_key"],
            workflow_status=wf_status,
            agents=processed_agents,
            judge_result=judge_result,
            duration_ms=state.get("duration_ms", 0),
            errors=sanitized_errors
        )

trace_collector = TraceCollector()

