"""LangGraph workflow assembly with parallel branches, barrier join, and failure handling."""
import time
from datetime import datetime, timezone
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END

from app.graph.state import GraphState
from app.graph.nodes import generate_for_node, generate_against_node, judge_node
from app.llm.base import BaseChatAdapter
from app.schemas.workflow import WorkflowStatus, AgentStatus

def _get_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def build_evaluation_graph(adapter: BaseChatAdapter):
    r"""Builds and compiles the adversarial evaluation LangGraph.
    
    Workflow Topology:
              START
             /     \
      [FOR Node]  [AGAINST Node]   (Parallel concurrent execution)
             \     /
          [Barrier Join]
                 |
        (Both Succeeded?)
           /           \
        YES             NO
         |               |
    [Judge Node]   [Skip Judge & Mark Failed]
         \               /
          [Finalize Trace]
                 |
                END
    """
    builder = StateGraph(GraphState)

    # Node 1: FOR argument agent
    async def for_agent_step(state: GraphState) -> Dict[str, Any]:
        return await generate_for_node(state, adapter)

    # Node 2: AGAINST argument agent
    async def against_agent_step(state: GraphState) -> Dict[str, Any]:
        return await generate_against_node(state, adapter)

    # Node 3: Barrier Join Evaluator
    async def join_step(state: GraphState) -> Dict[str, Any]:
        # Barrier join synchronization point.
        for_res = state.get("for_result")
        against_res = state.get("against_result")
        
        # If either branch failed, record skipped trace for Judge immediately
        if not for_res or not against_res:
            skip_msg = "Judge skipped because one or both argument agents failed."
            now = _get_iso_now()
            skipped_trace = {
                "model_id": adapter.model_id,
                "status": AgentStatus.SKIPPED,
                "input": {},
                "output": None,
                "started_at": now,
                "completed_at": now,
                "duration_ms": 0,
                "error": skip_msg
            }
            return {
                "agent_traces": {"judge": skipped_trace},
                "workflow_status": WorkflowStatus.FAILED,
                "errors": [skip_msg]
            }
        return {}

    # Node 4: Judge Agent
    async def judge_agent_step(state: GraphState) -> Dict[str, Any]:
        return await judge_node(state, adapter)

    # Node 5: Finalize Workflow Status and Overall Timing
    async def finalize_step(state: GraphState) -> Dict[str, Any]:
        completed_at = _get_iso_now()
        start_ts = state.get("started_at", completed_at)
        
        # Calculate total workflow duration
        try:
            start_dt = datetime.fromisoformat(start_ts)
            end_dt = datetime.fromisoformat(completed_at)
            duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
        except Exception:
            duration_ms = 0

        # Determine final workflow status
        judge_res = state.get("judge_result")
        if judge_res is not None:
            status = WorkflowStatus.COMPLETED
        else:
            status = WorkflowStatus.FAILED

        return {
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "workflow_status": status
        }

    # Conditional router after barrier join
    def route_after_join(state: GraphState) -> Literal["judge_agent_step", "finalize_step"]:
        if state.get("for_result") and state.get("against_result"):
            return "judge_agent_step"
        return "finalize_step"

    # Register all nodes
    builder.add_node("for_agent_step", for_agent_step)
    builder.add_node("against_agent_step", against_agent_step)
    builder.add_node("join_step", join_step)
    builder.add_node("judge_agent_step", judge_agent_step)
    builder.add_node("finalize_step", finalize_step)

    # Parallel fan-out from START
    builder.add_edge(START, "for_agent_step")
    builder.add_edge(START, "against_agent_step")

    # Barrier join: wait for both parallel branches
    builder.add_edge("for_agent_step", "join_step")
    builder.add_edge("against_agent_step", "join_step")

    # Conditional routing after join
    builder.add_conditional_edges(
        "join_step",
        route_after_join,
        {
            "judge_agent_step": "judge_agent_step",
            "finalize_step": "finalize_step"
        }
    )

    # Judge leads to finalize
    builder.add_edge("judge_agent_step", "finalize_step")
    
    # Finalize leads to END
    builder.add_edge("finalize_step", END)

    return builder.compile()
