# Product Requirements Document (PRD)

## Hiring Manager Evaluation Lab

**Version:** 1.0  
**Status:** Requirements baseline  
**Product type:** Internal proof-of-concept application  

---

### 1. Product Overview
Hiring Manager Evaluation Lab is an internal application that evaluates whether a supplied candidate profile is a plausible hiring manager for a particular job posting. It accepts three structured JSON inputs—candidate profile, job description (JD), and company context—and runs a three-agent LangGraph workflow.

Two independent argument-generation agents receive the same source inputs. One constructs the strongest evidence-based case **FOR** the match; the other constructs the strongest evidence-based case **AGAINST** the match. A third agent, the **Judge**, receives the original inputs and both arguments, verifies claims against the supplied data, and must select either **FOR** or **AGAINST**.

The application supports interchangeable model configurations and provides an execution-trace interface so a reviewer can inspect what each agent received and returned.

---

### 2. Problem Statement
A hiring-manager match can be difficult to assess from a profile and job description alone. A single-model answer may be one-sided or overlook evidence that weakens its conclusion. The product therefore creates opposing arguments independently and asks a separate Judge to compare them against the same source information.

The application is intended to make the reasoning process inspectable. It does not claim to guarantee unbiased or hallucination-free decisions; it reduces and exposes those risks through evidence-grounded prompts, structured outputs, and trace inspection.

---

### 3. Goals
- Accept candidate profile, JD, and company context as structured JSON.
- Generate independent FOR and AGAINST arguments using separate LLM calls.
- Run both argument agents concurrently.
- Have a Judge evaluate the original input and both arguments.
- Require a binary final decision: FOR or AGAINST.
- Allow a user to select one model configuration for the entire workflow.
- Provide two Streamlit tabs: Workflow and Evaluations.
- Capture inputs, outputs, model identifiers, statuses, and timings for each agent.
- Keep executions in session memory and allow selected evaluations to be saved to and deleted from local JSON files.
- Compare executions run against the same input using different model configurations.

---

### 4. Non-Goals
The initial scope excludes:
- Automated benchmark datasets, test suites, scoring rubrics, and POC performance conclusions.
- LangSmith or another external observability platform.
- A relational or document database.
- User accounts, role-based access control, and multi-user collaboration.
- Automatic retries, self-correction loops, or argument regeneration.
- Web browsing or external research by agents.
- A third outcome such as INSUFFICIENT EVIDENCE.
- A separate validator, critic, or report-writing agent.
- Production-grade distributed execution or job queueing.

---

### 5. Users and Primary Workflow
**Primary user:** Manager or reviewer assessing whether an candidate profile is the correct hiring manager for a job posting.

1. Open the Workflow tab.
2. Enter or paste the candidate profile JSON, JD JSON, and company-context JSON.
3. Select a model configuration: GPT-OSS 120B, Qwen, or the ChatGPT paid model once its exact model/provider is selected.
4. Submit the workflow.
5. The FOR and AGAINST agents run concurrently.
6. The Judge runs after both arguments are available.
7. The final decision and reasoning are displayed.
8. Open Evaluations to inspect the execution trace, compare it with other model runs, and save or delete evaluations.

---

### 6. Functional Requirements
- **FR-01: Structured Inputs:** The system shall accept three separate JSON objects: `candidate_profile`, `job_description`, and `company_context`.
- **FR-02: Model Selection:** The user shall select one model configuration before execution. The selected model shall be used by all three agents for that execution.
- **FR-03: FOR Agent:** Independently produces a short paragraph arguing that the profile is the correct hiring manager, exact supporting values copied from the source inputs, and a confidence score from 0 to 10.
- **FR-04: AGAINST Agent:** Independently produces a short paragraph arguing that the profile is not the correct hiring manager, exact supporting values copied from the source inputs, and a confidence score from 0 to 10. Does not see FOR's response.
- **FR-05: Judge Agent:** Receives original source inputs + complete FOR output + complete AGAINST output. Excludes model/provider identity. Returns only FOR or AGAINST with winning argument, reasoning, and 0-100 confidence percentage.
- **FR-06: Binary Decision:** Judge must always return FOR or AGAINST. No INSUFFICIENT_EVIDENCE outcome.
- **FR-07: No Automatic Retry:** Each agent is invoked once per workflow execution. Failures are recorded and surfaced.
- **FR-08: Workflow Tab:** JSON inputs, model selector, Run Workflow action, execution status, and final Judge result.
- **FR-09: Evaluation Trace:** Inspectable traces showing original inputs, model config, per-agent input/output/status/timing, duration, and errors.
- **FR-10: Model Comparison:** Compare separate executions with equivalent input side by side.
- **FR-11: Save Evaluation:** Persist completed or failed trace to a local JSON file (`<execution_id>.json`).
- **FR-12: Delete Evaluation:** Delete saved evaluation by execution ID after user confirmation.
- **FR-13: Session History:** Executions stored in session memory during current session.

---

### 7. User Interface Requirements
The application shall contain one Streamlit application with two tabs:
1. **Workflow:** input, model selection, run action, final result.
2. **Evaluations:** execution list, trace detail, model comparison, save and delete actions.

---

### 8. Quality and Operational Requirements
- JSON input and output must be validated before being accepted as successful.
- All model calls must use configured timeouts.
- API keys and provider credentials must be read from environment variables, never hard-coded.
- Trace records must identify the exact model and provider used by each agent.
- Local evaluation files must be written atomically.
- Errors must identify the failing stage without exposing secrets.
- Confidence must be labeled as model estimate, not calibrated probability.
