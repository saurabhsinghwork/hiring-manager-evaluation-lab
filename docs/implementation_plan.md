# Implementation Plan

## Hiring Manager Evaluation Lab

**Version:** 1.0  

### 1. Build Sequence
- **Step 1: Repository and runtime baseline** (FastAPI /health, Streamlit skeleton, config)
- **Step 2: Define Pydantic contracts** (Inputs, agents, judge, traces)
- **Step 3: Implement model registry and provider abstraction** (Base adapter, OpenAI-compatible, factory)
- **Step 4: Implement agent prompts and nodes** (FOR, AGAINST, model-blind Judge)
- **Step 5: Build LangGraph** (State, parallel branches, barrier join, conditional routing)
- **Step 6: Add trace collection** (Timing, sanitized payloads, status tracking)
- **Step 7: Implement FastAPI endpoints** (Routes for models, workflow run, evaluation CRUD)
- **Step 8: Build Workflow tab** (JSON editors, model picker, run feedback, result cards)
- **Step 9: Build Evaluations tab** (Session vs saved, trace viewer, side-by-side diff, confirmation dialogs)
- **Step 10: Packaging and handover** (Hardening, documentation, sample datasets)
