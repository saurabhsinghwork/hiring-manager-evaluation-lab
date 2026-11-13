"""Agent output schemas for Argument Agents (FOR/AGAINST) and the Judge Agent."""
from typing import Any, List, Literal
from pydantic import BaseModel, Field, field_validator

def _coerce_text(value: Any) -> Any:
    """Models sometimes return bullet lists for text fields; join them into one markdown string."""
    if isinstance(value, (list, tuple)):
        lines = []
        for item in value:
            text = str(item).strip()
            if text:
                lines.append(text if text[:1] in "*-" else f"* {text}")
        return "\n".join(lines)
    return value


class EvidenceItem(BaseModel):
    """An exact piece of supporting evidence extracted verbatim from the inputs."""
    source_field: str = Field(
        ...,
        description="Path or field reference identifying origin (e.g. 'candidate_profile.title', 'job_description.requirements[0]')"
    )
    exact_value: str = Field(
        ...,
        description="Exact value copied verbatim from the source inputs without fabrication"
    )

    @field_validator("source_field", "exact_value")
    @classmethod
    def validate_non_empty(cls, value: str, info) -> str:
        stripped = str(value).strip()
        if not stripped:
            raise ValueError(f"{info.field_name} must not be empty")
        return stripped

class ArgumentAgentOutput(BaseModel):
    """Output contract for both FOR and AGAINST argument generation agents."""
    argument: str = Field(
        ...,
        description="Structured markdown bullet points (* Point 1\n* Point 2) arguing for or against the candidate as hiring manager"
    )
    supporting_evidence: List[EvidenceItem] = Field(
        ...,
        min_length=1,
        description="List of exact supporting values copied from the source inputs"
    )
    confidence_score: int = Field(
        ...,
        ge=0,
        le=10,
        description="Confidence score from 0 to 10"
    )

    @field_validator("argument", mode="before")
    @classmethod
    def coerce_argument(cls, value: Any) -> Any:
        return _coerce_text(value)

    @field_validator("argument")
    @classmethod
    def validate_argument_not_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("argument cannot be empty")
        return stripped

class JudgeOutput(BaseModel):
    """Output contract for the Judge Agent."""
    decision: Literal["FOR", "AGAINST"] = Field(
        ...,
        description="Binary decision: must be either 'FOR' or 'AGAINST'. Ties or insufficient evidence are disallowed."
    )
    winning_argument: str = Field(
        ...,
        description="The winning argument text grounded in the submitted arguments, formatted as markdown bullet points"
    )
    reasoning: str = Field(
        ...,
        description="Evidence-based explanation for the decision formatted as structured markdown bullet points (* Point 1\n* Point 2)"
    )
    confidence_percentage: int = Field(
        ...,
        ge=0,
        le=100,
        description="Confidence percentage from 0 to 100"
    )

    @field_validator("winning_argument", "reasoning", mode="before")
    @classmethod
    def coerce_text(cls, value: Any) -> Any:
        return _coerce_text(value)

    @field_validator("winning_argument", "reasoning")
    @classmethod
    def validate_text_not_empty(cls, value: str, info) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{info.field_name} cannot be empty")
        return stripped

