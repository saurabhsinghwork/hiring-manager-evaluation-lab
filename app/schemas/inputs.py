"""Input contracts and validation schemas."""
from typing import Any, Dict
import hashlib
import json
from pydantic import BaseModel, Field, field_validator, ConfigDict

class WorkflowRequest(BaseModel):
    """Workflow execution request payload."""
    model_config = ConfigDict(populate_by_name=True)

    candidate_profile: Dict[str, Any] = Field(
        ...,
        description="Structured candidate candidate profile object"
    )
    job_description: Dict[str, Any] = Field(
        ...,
        description="Structured job posting / requisition object"
    )
    company_context: Dict[str, Any] = Field(
        ...,
        description="Structured company background and team context object"
    )
    model_config_key: str = Field(
        ...,
        alias="model_config",
        description="Target model configuration identifier, e.g. 'gpt_oss_120b'"
    )

    @property
    def model_config_name(self) -> str:
        """Helper to get configured model key."""
        return self.model_config_key

    @field_validator("candidate_profile", "job_description", "company_context")
    @classmethod
    def validate_non_empty_object(cls, value: Dict[str, Any], info) -> Dict[str, Any]:
        """Ensures input dictionaries are non-empty objects."""
        if not isinstance(value, dict):
            raise ValueError(f"{info.field_name} must be a JSON object")
        if not value:
            raise ValueError(f"{info.field_name} cannot be an empty object")
        return value

    @field_validator("model_config_key")
    @classmethod
    def validate_model_config_non_empty(cls, value: str) -> str:
        """Validates that model configuration key is non-empty string."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("model_config cannot be empty")
        return stripped

    def compute_input_hash(self) -> str:
        """Computes a stable, canonical SHA-256 hash of normalized source inputs.
        
        Used for like-for-like model output comparison and discrepancy alerts.
        """
        normalized_payload = {
            "candidate_profile": self.candidate_profile,
            "job_description": self.job_description,
            "company_context": self.company_context
        }
        serialized = json.dumps(normalized_payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
