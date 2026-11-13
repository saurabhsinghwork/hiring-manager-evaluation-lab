"""State definitions and merge reducers for the LangGraph workflow."""
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict, Annotated

def merge_dict_reducer(old: Optional[Dict[str, Any]], new: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merges dictionary updates from parallel execution branches."""
    merged = dict(old or {})
    if new:
        merged.update(new)
    return merged

def merge_list_reducer(old: Optional[List[str]], new: Optional[List[str]]) -> List[str]:
    """Appends lists of errors from parallel execution branches."""
    result = list(old or [])
    if new:
        for item in new:
            if item not in result:
                result.append(item)
    return result

class GraphState(TypedDict):
    """The shared state contract flowing through the LangGraph workflow."""
    execution_id: str
    source_input: Dict[str, Any]
    input_hash: str
    model_config_key: str
    
    # Branch outputs
    for_result: Optional[Dict[str, Any]]
    against_result: Optional[Dict[str, Any]]
    judge_result: Optional[Dict[str, Any]]

    # Telemetry and traces with parallel merge reducers
    agent_traces: Annotated[Dict[str, Any], merge_dict_reducer]
    errors: Annotated[List[str], merge_list_reducer]
    
    # Workflow metadata
    started_at: str
    completed_at: Optional[str]
    duration_ms: int
    workflow_status: str

