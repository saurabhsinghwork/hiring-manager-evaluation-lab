"""Workflow execution schemas and statuses."""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.agents import ArgumentAgentOutput, JudgeOutput

class WorkflowStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class WorkflowResponse(BaseModel):
    """Full response model returned after executing a workflow."""
    model_config = ConfigDict(populate_by_name=True)

    execution_id: str = Field(..., description="Unique execution UUID")
    model_config_key: str = Field(..., alias="model_config", description="Model configuration key used")
    status: WorkflowStatus = Field(..., description="Workflow completion status")
    for_agent: Optional[ArgumentAgentOutput] = Field(None, description="Output from the FOR agent")
    against_agent: Optional[ArgumentAgentOutput] = Field(None, description="Output from the AGAINST agent")
    judge_agent: Optional[JudgeOutput] = Field(None, description="Output from the Judge agent")
    trace: Dict[str, Any] = Field(default_factory=dict, description="Full execution trace payload")
    duration_ms: int = Field(default=0, ge=0, description="Total workflow duration in milliseconds")
    errors: List[str] = Field(default_factory=list, description="List of sanitized error messages, if any")
