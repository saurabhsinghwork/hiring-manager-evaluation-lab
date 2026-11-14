# Functional and Interface Specifications

## Hiring Manager Evaluation Lab

**Version:** 1.0  

---

### 1. Input Contract
```json
{
  "candidate_profile": { "example_field": "example value" },
  "job_description": { "example_field": "example value" },
  "company_context": { "example_field": "example value" },
  "model_config": "gpt_oss_120b"
}
```

### 2. Argument Agent Output Schema
```json
{
  "argument": "Short paragraph.",
  "supporting_evidence": [
    {
      "source_field": "candidate_profile.example_field",
      "exact_value": "Exact supplied value"
    }
  ],
  "confidence_score": 7
}
```

### 3. Judge Agent Output Schema
```json
{
  "decision": "FOR",
  "winning_argument": "The winning argument text.",
  "reasoning": "Evidence-based explanation for the decision.",
  "confidence_percentage": 82
}
```

### 4. API Endpoints
- `GET /health`: Health check
- `GET /api/v1/models`: List configured model options and availability
- `POST /api/v1/workflows/run`: Execute one workflow run
- `GET /api/v1/evaluations`: List saved evaluations
- `GET /api/v1/evaluations/{execution_id}`: Retrieve saved evaluation trace
- `POST /api/v1/evaluations/{execution_id}/save`: Persist evaluation trace
- `DELETE /api/v1/evaluations/{execution_id}`: Delete saved evaluation

### 5. Hiring-Responsibility Doctrine and Derived Signals
All three agents share `HIRING_MANAGER_DOCTRINE` (`app/graph/prompts.py`). The decision question is whether the person is **responsible for hiring for this specific opening** (direct line manager, owning leader, or a founder/executive who personally hires). Seniority, referral ability, and interview involvement never establish responsibility.

- **Gates:** current employment at the hiring entity; function/team scope containing the opening; reach for the company's size.
- **Company-size tiers** (`app/graph/signals.py`): MICRO ≤10, SMALL 11–50, GROWTH 51–200, MID_SIZE 201–1,000, LARGE 1,001–10,000, ENTERPRISE 10,001+, or UNKNOWN. The tier sets how many levels above the opening a person can sit and still plausibly own the hire (unlimited at MICRO, +1 at ENTERPRISE).
- **Title decoding:** people-management status plus a normalized level band (B1–B8), calibrated by sector (e.g. a bank "Vice President" is a mid-career rank, not a function head).
- **Evidence ladder:** E1 explicit (reporting_to / hiring policy, rare and never required) → E3 structural (the normal basis) → E5 none. Missing information is never proof in either direction. At MICRO–MID_SIZE the founder, C-level or head of the owning function is always in reach; a different engineering sub-specialty is not a function mismatch.
- **Derived signals:** `format_argument_agent_prompt` and `format_judge_prompt` append a `DERIVED CONTEXT SIGNALS` block (size tier, sector, employer-name match, title keyword hints, explicit reporting/policy fields). These are hints; the source JSON always wins.
- **Output contract:** prompts do not define their own JSON shapes. Section 2 and 3 schemas above are authoritative; the structured reasoning labels (Pathway, Employment, Function fit, Title decoded, Company-size reach, Ownership evidence, Decisive factor, Unknowns and flip conditions) live inside `argument` / `reasoning`.
