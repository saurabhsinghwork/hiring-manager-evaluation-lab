# Technical Requirements Document (TRD)

## Hiring Manager Evaluation Lab

**Version:** 1.0  
**Status:** Technical baseline  

---

### 1. Technical Summary
The solution consists of a Streamlit frontend, a FastAPI backend, a LangGraph workflow, provider-specific LLM adapters, and a local JSON evaluation store. LangGraph coordinates two parallel argument-generation nodes followed by a Judge node. A trace collector records the inputs, outputs, model metadata, timings, statuses, and errors for each node.

---

### 2. Proposed Technology Stack
| Layer | Technology | Responsibility |
| :--- | :--- | :--- |
| Language | Python | Application implementation |
| UI | Streamlit | Workflow and Evaluations tabs |
| API | FastAPI | Request validation and workflow endpoints |
| Orchestration | LangGraph | State graph and parallel branches |
| Data validation | Pydantic | Request, agent-output, and response models |
| Model integration | Provider adapters / LangChain chat models | Invoke selected model |
| Persistence | Local JSON files | Save and delete evaluation traces |
| Configuration | Environment variables / secrets | API keys, model IDs, timeouts |
| Packaging | Python project environment | Repeatable runtime |

*No database is required.*

---

### 3. High-Level Runtime Flow
1. Streamlit collects three JSON objects and the selected model configuration.
2. Streamlit sends a request to FastAPI.
3. FastAPI validates the request and resolves the selected model configuration.
4. FastAPI invokes the LangGraph workflow.
5. LangGraph starts the FOR and AGAINST nodes concurrently.
6. Each node invokes the selected model independently and validates its structured response.
7. After both branches complete, LangGraph invokes the Judge node.
8. The Judge receives the source JSON and both arguments. Model identity metadata is excluded from the Judge's prompt payload.
9. The workflow returns a final result and an execution trace.
10. FastAPI returns the response to Streamlit.
11. Streamlit adds the execution to session history. A user may save it to the local JSON store.

---

### 4. LangGraph Design
#### 4.1 Graph Nodes
- `generate_for_argument`: calls selected model with source inputs and FOR instructions.
- `generate_against_argument`: calls selected model with same source inputs and AGAINST instructions.
- `judge_arguments`: receives original inputs and both agent outputs, returns binary decision.

#### 4.2 Graph Edges
Parallel fan-out from start state to FOR and AGAINST nodes. Barrier join when both complete. Judge node runs after join.

#### 4.3 State Contract
- `execution_id`
- `source_input`: `candidate_profile`, `job_description`, `company_context`
- `model_config_key`
- `for_result`, `against_result`, `judge_result`
- `agent_traces`
- `started_at`, `completed_at`, `duration_ms`
- `workflow_status`, `errors`
