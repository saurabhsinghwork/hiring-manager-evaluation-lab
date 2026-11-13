# ⚖️ Hiring Manager Evaluation Lab

An adversarial multi-agent evaluation platform for assessing whether a candidate's candidate profile represents a plausible hiring manager for a specific job posting.

Built with **FastAPI**, **LangGraph**, **Streamlit**, and **Pydantic**.

---

## 🌟 Architecture & Key Highlights

* **Adversarial Argument Generation (Parallel Execution):**
  * `FOR` Agent constructs the strongest evidence-based case *in favor* of the candidate being the hiring manager.
  * `AGAINST` Agent independently constructs the strongest counter-argument.
  * Both agents execute concurrently in LangGraph and extract verbatim source citations (`source_field` and `exact_value`).
* **Model-Blind Adjudication (`Judge` Agent):**
  * The Judge receives raw source inputs and both arguments, but **zero model or provider identity information**.
  * Renders a strict binary decision (`FOR` or `AGAINST`) with confidence percentage ($0$–$100\%$) and verified reasoning. No ties or insufficient-evidence verdicts are permitted.
* **No Retries & Fail-Fast Semantics:**
  * If either argument agent fails, the Judge is automatically marked `SKIPPED`, the workflow status is set to `FAILED`, and sanitized error details are surfaced without silent retries.
* **Lightweight Local JSON Persistence (No Database):**
  * In-memory session state by default.
  * Reviewers can selectively persist evaluation traces to `data/evaluations/<execution_id>.json` using atomic file replacement (`.tmp` + `os.replace`).
* **Side-by-Side Model Comparison:**
  * Reviewers can select multiple runs and compare agent arguments and Judge verdicts side by side.
  * Includes a SHA-256 canonical input-hash comparison engine that triggers prominent warnings if evaluated inputs differ.

---

## 📁 Repository Layout

```
hiring-manager-evaluation-lab/
├── app/
│   ├── api/
│   │   ├── main.py                  # FastAPI application entrypoint & lifecycle
│   │   ├── dependencies.py          # Dependency injection helpers
│   │   └── routes/
│   │       ├── health.py            # GET /health
│   │       ├── models.py            # GET /api/v1/models
│   │       ├── workflows.py         # POST /api/v1/workflows/run
│   │       └── evaluations.py       # GET, POST /save, DELETE /api/v1/evaluations
│   ├── core/
│   │   ├── config.py                # Pydantic BaseSettings & environment loader
│   │   └── logging.py               # Application-wide structured logging
│   ├── schemas/
│   │   ├── inputs.py                # WorkflowRequest & canonical input hashing
│   │   ├── agents.py                # ArgumentAgentOutput & JudgeOutput contracts
│   │   ├── workflow.py              # WorkflowResponse & status enums
│   │   └── evaluations.py           # EvaluationTrace & AgentTrace telemetry schemas
│   ├── services/
│   │   ├── model_registry.py        # Model configurations & credential resolution
│   │   ├── workflow_service.py      # End-to-end execution coordinator
│   │   ├── trace_collector.py       # Secret redaction & trace packaging
│   │   └── evaluation_store.py      # Atomic local JSON persistence & path safety
│   ├── llm/
│   │   ├── base.py                  # BaseChatAdapter abstract class
│   │   ├── factory.py               # Adapter instantiation factory
│   │   └── providers/
│   │       └── openai_compatible.py # Universal OpenAI-compatible REST adapter
│   ├── graph/
│   │   ├── state.py                 # GraphState TypedDict & merge reducers
│   │   ├── prompts.py               # Adversarial and model-blind prompt templates
│   │   ├── nodes.py                 # Graph node execution handlers
│   │   └── workflow.py              # LangGraph StateGraph topology & join logic
│   └── ui/
│       ├── streamlit_app.py         # Streamlit main shell & sidebar status
│       ├── sample_data.py           # Real-world Strong & Contested scenario presets
│       ├── workflow_tab.py          # Tab 1: JSON editors, model picker, run progress
│       ├── evaluations_tab.py       # Tab 2: Trace inspector, diff view, save/delete
│       └── components/
│           ├── json_editor.py       # JSON editor & pre-flight validator
│           ├── trace_viewer.py      # Telemetry expander for all agent nodes
│           └── diff_view.py         # Side-by-side run comparison & hash check
├── data/
│   ├── evaluations/                 # Persisted JSON evaluations (<execution_id>.json)
│   └── samples/                     # Sample input JSON files for direct testing
├── docs/                            # Complete requirements and architecture specs
├── tests/                           # 29 automated unit and integration tests
├── .env.example                     # Environment template (no secrets)
├── pyproject.toml                   # Python package build configuration
└── README.md
```

---

## 🚀 Quickstart Guide

### 1. Environment Setup
```bash
# Navigate to the project directory
cd C:\Users\Admin\Desktop\hiring-manager-evaluation-lab

# Create and activate virtual environment
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1

# Install project and all dependencies
pip install -e .
pip install pytest pytest-asyncio
```

### 2. Configure Credentials (`.env`)
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Open `.env` and set your API keys:
```env
# ChatGPT Paid / OpenAI API
OPENAI_API_KEY=sk-your-openai-api-key
CHATGPT_MODEL_ID=gpt-4o

# Qwen Model (e.g. DashScope or OpenRouter)
QWEN_API_KEY=your-qwen-key
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_MODEL_ID=qwen-2.5-72b-instruct

# GPT-OSS 120B Model (e.g. local vLLM or Ollama)
GPT_OSS_API_KEY=
GPT_OSS_BASE_URL=http://localhost:8000/v1
GPT_OSS_MODEL_ID=gpt-oss-120b
```
> **Note:** Only models with configured API keys will appear as `enabled` in the UI and API. Unconfigured models are automatically greyed out.

---

### 3. Run the Services

Open two terminal windows:

#### Terminal 1: Backend API (FastAPI)
```bash
.venv\Scripts\uvicorn.exe app.api.main:app --host 127.0.0.1 --port 8000 --reload
```
* Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

#### Terminal 2: Frontend Dashboard (Streamlit)
```bash
.venv\Scripts\streamlit.exe run app/ui/streamlit_app.py --server.port 8501
```
* Open your browser at `http://localhost:8501`.

---

## 🧪 Running Automated Tests

Run the full automated test suite (29 tests covering schemas, contracts, nodes, LangGraph workflow, trace collection, and REST API endpoints):

```bash
.venv\Scripts\pytest.exe tests -v
```

All 29 tests run in under 5 seconds with zero mock shortcuts.

---

## 🛡️ Security, Privacy & Trace Sanitization

1. **Model Blindness:** The Judge prompt receives only raw data and competing arguments. Model IDs and provider names are strictly stripped before the Judge prompt is constructed.
2. **Secret Redaction:** The `TraceCollector` service actively scans and redacts any bearer tokens (`Bearer [REDACTED]`) and API keys (`[REDACTED_KEY]`) before writing to trace dictionaries or local JSON files.
3. **Path Traversal Protection:** All file operations under `data/evaluations/` validate `execution_id` against a strict UUID regex (`^[0-9a-fA-F-]{36}$`), rejecting arbitrary path parameters.
4. **Local Data Persistence:** Files are stored unencrypted in `data/evaluations/`. Restrict operating-system filesystem permissions appropriately for sensitive candidate candidate profiles.
