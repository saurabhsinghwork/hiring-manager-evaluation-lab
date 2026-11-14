"""Agent output schemas for Argument Agents (FOR/AGAINST) and the Judge Agent."""
import re
from typing import Any, List, Literal
from pydantic import BaseModel, Field, field_validator

def format_as_markdown_bullets(value: Any) -> str:
    """Coerces any text or list output into formatted markdown bullet points (* Point)."""
    if not value:
        return ""
    if isinstance(value, (list, tuple)):
        lines = []
        for item in value:
            text = str(item).strip()
            if text:
                cleaned = re.sub(r"^(\*|-|•|\d+\.)\s*", "", text).strip()
                if cleaned:
                    lines.append(f"* {cleaned}")
        return "\n".join(lines)

    raw = str(value).strip()
    if not raw or raw in ("N/A", "null", "None"):
        return raw

    # Strip leading prefixes like "Argument:", "Winning Argument:", etc.
    raw = re.sub(r"^(?:Winning\s+)?Argument:\s*", "", raw, flags=re.IGNORECASE).strip()

    # If it already contains multiple lines
    lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
    if len(lines) > 1:
        formatted = []
        for ln in lines:
            cleaned = re.sub(r"^(\*|-|•|\d+\.)\s*", "", ln).strip()
            if cleaned:
                formatted.append(f"* {cleaned}")
        return "\n".join(formatted)

    # If it contains inline bullets like "* Point 1 * Point 2" or "1. Point 1 2. Point 2"
    if re.search(r"(?:^|\s)(?:[*•-]\s|\d+\.\s)", raw):
        parts = re.split(r"(?:^|\s)(?:[*•-]\s|\d+\.\s)", raw)
        bullets = [p.strip() for p in parts if p.strip()]
        if len(bullets) > 1:
            return "\n".join(f"* {b}" for b in bullets)

    # Check for sentence splits
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"\'`])', raw)
    if len(sentences) > 1:
        return "\n".join(f"* {s.strip()}" for s in sentences if s.strip())

    # Check for semicolon-separated clauses
    if ";" in raw:
        clauses = [c.strip() for c in raw.split(";") if c.strip()]
        if len(clauses) > 1:
            return "\n".join(f"* {c}" for c in clauses)

    # Check for compound sentence with major connective clauses
    connective_pattern = r',\s*(?:while|and\s+both|moreover|furthermore|indicating\s+that)\b'
    if re.search(connective_pattern, raw, flags=re.IGNORECASE):
        clauses = re.split(connective_pattern, raw, flags=re.IGNORECASE)
        bullets = [c.strip() for c in clauses if c.strip()]
        if len(bullets) > 1:
            return "\n".join(f"* {b[0].upper() + b[1:] if b else b}" for b in bullets)

    # Single clause or sentence: return with bullet marker
    cleaned = re.sub(r"^(\*|-|•|\d+\.)\s*", "", raw).strip()
    return f"* {cleaned}"

_ROOT_PHRASES = {
    "candidate_profile": "the candidate's profile",
    "job_description": "the job description",
    "company_context": "the company details",
    "derived_signals": "the company details",
}
_ROOT_LABELS = {
    "candidate_profile": "Candidate profile",
    "job_description": "Job description",
    "company_context": "Company details",
    "derived_signals": "Company details",
}
_PATH_RE = re.compile(
    r"`?\b(candidate_profile|job_description|company_context|derived_signals)"
    r"(?:\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])*`?"
)


def humanize_text(text: str) -> str:
    """Replaces internal field paths (e.g. candidate_profile.experiences[0].title) with plain wording."""
    if not isinstance(text, str):
        return text
    out = _PATH_RE.sub(lambda m: _ROOT_PHRASES[m.group(1)], text)
    repeat = re.compile(r"(the (?:candidate's profile|job description|company details))(?:\s*(?:,|and|&)\s*\1)+")
    out = repeat.sub(r"\1", out)
    return re.sub(r"\(\s*\)", "", out)


def humanize_field_label(path: Any) -> str:
    """Friendly label for an evidence source path, without internal field names."""
    match = _PATH_RE.search(str(path or ""))
    return _ROOT_LABELS[match.group(1)] if match else "Source data"


def _coerce_text(value: Any) -> Any:
    """Models sometimes return bullet lists for text fields; coerce into markdown bullet points."""
    return humanize_text(format_as_markdown_bullets(value))


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

