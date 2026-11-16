"""Workflow service coordinating model resolution, graph execution, and trace building."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.schemas.inputs import WorkflowRequest
from app.schemas.workflow import WorkflowResponse, WorkflowStatus
from app.schemas.agents import ArgumentAgentOutput
from app.services.model_registry import ModelRegistry, model_registry
from app.services.trace_collector import trace_collector
from app.graph.workflow import build_evaluation_graph
from app.graph.state import GraphState

def _get_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()

# Cross-model judging: GPT-OSS arguments are judged by Qwen and vice versa. Other models judge themselves.
_CROSS_JUDGE = {"gpt_oss_120b": "qwen", "qwen": "gpt_oss_120b"}


class WorkflowService:
    """Coordinates end-to-end adversarial evaluation workflow."""

    def __init__(self, registry: Optional[ModelRegistry] = None):
        self.registry = registry or model_registry

    async def execute_workflow(self, request: WorkflowRequest) -> WorkflowResponse:
        """Executes the complete three-agent evaluation workflow and returns validated response."""
        execution_id = str(uuid.uuid4())
        started_at = _get_iso_now()
        input_hash = request.compute_input_hash()

        # 1. Resolve model adapter
        adapter = self.registry.get_adapter(request.model_config_key)

        # 2. Compile LangGraph workflow
        judge_adapter = None
        judge_key = _CROSS_JUDGE.get(request.model_config_key)
        if judge_key:
            try:
                judge_adapter = self.registry.get_adapter(judge_key)
            except ValueError:
                judge_adapter = None  # judge model not configured: fall back to the selected model
        graph = build_evaluation_graph(adapter, judge_adapter)

        # 3. Assemble initial graph state
        initial_state: GraphState = {
            "execution_id": execution_id,
            "source_input": {
                "candidate_profile": request.candidate_profile,
                "job_description": request.job_description,
                "company_context": request.company_context,
            },
            "input_hash": input_hash,
            "model_config_key": request.model_config_key,
            "for_result": None,
            "against_result": None,
            "judge_result": None,
            "agent_traces": {},
            "errors": [],
            "started_at": started_at,
            "completed_at": None,
            "duration_ms": 0,
            "workflow_status": WorkflowStatus.RUNNING.value
        }

        # 4. Invoke the state graph
        final_state = await graph.ainvoke(initial_state)

        # 5. Extract and sanitize full evaluation trace
        trace = trace_collector.build_trace_from_state(final_state)

        # 6. Parse agent outputs for top-level response convenience
        for_output = None
        if final_state.get("for_result"):
            try:
                for_output = ArgumentAgentOutput.model_validate(final_state["for_result"])
            except Exception:
                for_output = None

        against_output = None
        if final_state.get("against_result"):
            try:
                against_output = ArgumentAgentOutput.model_validate(final_state["against_result"])
            except Exception:
                against_output = None

        return WorkflowResponse(
            execution_id=execution_id,
            model_config=request.model_config_key,
            status=trace.workflow_status,
            for_agent=for_output,
            against_agent=against_output,
            judge_agent=trace.judge_result,
            trace=trace.model_dump(by_alias=True),
            duration_ms=trace.duration_ms,
            errors=trace.errors
        )

workflow_service = WorkflowService()

