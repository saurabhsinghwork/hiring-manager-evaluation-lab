"""Evaluation persistence and trace schemas."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.agents import JudgeOutput
from app.schemas.workflow import WorkflowStatus, AgentStatus

class AgentTrace(BaseModel):
    """Detailed telemetry and I/O trace for a single agent node."""
    model_id: str = Field(..., description="Exact model identifier invoked")
    status: AgentStatus = Field(..., description="Status of this node execution")
    input: Dict[str, Any] = Field(default_factory=dict, description="Sanitized input payload passed to the node")
    output: Optional[Dict[str, Any]] = Field(None, description="Structured output payload produced by the node")
    started_at: str = Field(..., description="ISO-8601 start timestamp")
    completed_at: str = Field(..., description="ISO-8601 completion timestamp")
    duration_ms: int = Field(default=0, ge=0, description="Node execution duration in milliseconds")
    error: Optional[str] = Field(None, description="Sanitized error description if failed")

class EvaluationTrace(BaseModel):
    """Complete evaluation trace persisted to data/evaluations/<execution_id>.json."""
    model_config = ConfigDict(populate_by_name=True)

    execution_id: str = Field(..., description="Unique execution UUID")
    created_at: str = Field(..., description="ISO-8601 workflow creation timestamp")
    completed_at: str = Field(..., description="ISO-8601 workflow completion timestamp")
    source_input: Dict[str, Any] = Field(..., description="Original inputs: candidate_profile, job_description, company_context")
    input_hash: str = Field(..., description="SHA-256 hash of normalized source inputs")
    model_config_key: str = Field(..., alias="model_config", description="Model configuration key used")
    workflow_status: WorkflowStatus = Field(..., description="Overall workflow status")
    agents: Dict[str, AgentTrace] = Field(..., description="Traces per agent ('for', 'against', 'judge')")
    judge_result: Optional[JudgeOutput] = Field(None, description="Final structured verdict from the Judge")
    duration_ms: int = Field(default=0, ge=0, description="Total execution duration in milliseconds")
    errors: List[str] = Field(default_factory=list, description="Sanitized errors recorded during execution")

class EvaluationSummary(BaseModel):
    """Summary item returned by GET /api/v1/evaluations."""
    model_config = ConfigDict(populate_by_name=True)

    execution_id: str
    created_at: str
    model_config_key: str = Field(..., alias="model_config")
    workflow_status: WorkflowStatus
    decision: Optional[str] = None
    confidence_percentage: Optional[int] = None
    duration_ms: int
    input_hash: str
    is_saved: bool = True

class ModelOption(BaseModel):
    """Configured model description for GET /api/v1/models."""
    key: str = Field(..., description="Unique configuration key, e.g. 'gpt_oss_120b'")
    label: str = Field(..., description="Human-readable label for UI display")
    enabled: bool = Field(..., description="Whether this model is configured and ready for execution")
    model_id: Optional[str] = Field(None, description="Exact backend model identifier")

class ModelListResponse(BaseModel):
    """Response envelope for GET /api/v1/models."""
    models: List[ModelOption]
