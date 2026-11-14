"""Workflow execution tab for submitting evaluations and viewing decisions."""
import json
from pathlib import Path
import httpx
import streamlit as st
from app.schemas.agents import humanize_field_label
from typing import Dict, Any, List

from app.schemas.agents import format_as_markdown_bullets
from app.ui.components.json_editor import parse_and_validate_json, render_json_input_area

def fetch_model_options(api_url: str) -> List[Dict[str, Any]]:
    """Fetches configured models from FastAPI /api/v1/models."""
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{api_url}/api/v1/models")
            if resp.status_code == 200:
                return resp.json().get("models", [])
            return []
    except Exception:
        return []

def render_workflow_tab(api_status: Dict[str, Any]) -> None:
    """Renders the interactive Workflow tab."""
    api_url = api_status.get("url", "http://127.0.0.1:8000")

    st.markdown("### 1. Configure Evaluation Scenario")
    st.write("Provide the candidate's candidate profile, job posting requisition, and company organizational context.")

    # Quick-load real staging datasets directly from local storage
    datasets_file = Path("data/samples/new_20_real_datasets.json")
    if datasets_file.exists():
        try:
            with open(datasets_file, "r", encoding="utf-8") as f:
                real_datasets = json.load(f)
            ds_options = {
                idx: f"#{d.get('dataset_id', idx+1)}: {d.get('candidate_name')} → {d.get('target_job')} @ {d.get('company')}"
                for idx, d in enumerate(real_datasets)
            }
            c_select, c_btn = st.columns([4, 1])
            with c_select:
                selected_ds_idx = st.selectbox(
                    "⚡ Quick-Load Real Staging Dataset (1 to 20)",
                    options=list(ds_options.keys()),
                    format_func=lambda i: ds_options[i],
                    key="real_dataset_selector"
                )
            with c_btn:
                st.write("")
                st.write("")
                if st.button("📥 Load Dataset", use_container_width=True):
                    chosen = real_datasets[selected_ds_idx]
                    st.session_state["candidate_json_input"] = json.dumps(chosen.get("candidate_profile", {}), indent=2)
                    st.session_state["jd_json_input"] = json.dumps(chosen.get("job_description", {}), indent=2)
                    st.session_state["company_json_input"] = json.dumps(chosen.get("company_context", {}), indent=2)
                    st.rerun()
        except Exception:
            pass

    # Three JSON textareas in 3 side-by-side columns
    col1, col2, col3 = st.columns(3)
    with col1:
        cand_val = st.session_state.get("candidate_json_input", "")
        cand_text = render_json_input_area("candidate_input_area", "👤 Candidate Profile JSON", cand_val, height=280)

    with col2:
        jd_val = st.session_state.get("jd_json_input", "")
        jd_text = render_json_input_area("jd_input_area", "📄 Job Description JSON", jd_val, height=280)

    with col3:
        comp_val = st.session_state.get("company_json_input", "")
        comp_text = render_json_input_area("company_input_area", "🏢 Company Context JSON", comp_val, height=280)

    st.markdown("---")
    st.markdown("### 2. Model Selection & Execution")

    # Fetch models
    models = fetch_model_options(api_url)
    enabled_models = [m for m in models if m.get("enabled", False)]

    model_col1, model_col2 = st.columns([3, 1])
    with model_col1:
        if enabled_models:
            model_options = {m["key"]: f"{m['label']} ({m.get('model_id', m['key'])})" for m in enabled_models}
            selected_model_key = st.selectbox(
                "Select Model Configuration",
                options=list(model_options.keys()),
                format_func=lambda k: model_options[k],
                help="The selected model will be invoked across all three agents (FOR, AGAINST, and Judge)."
            )
        elif models:
            st.warning("⚠️ All models are currently unconfigured. Please add API credentials to `.env` or set environment variables.")
            model_options = {m["key"]: f"❌ {m['label']} (Disabled - Missing API Credentials)" for m in models}
            selected_model_key = st.selectbox("Select Model Configuration", options=list(model_options.keys()), format_func=lambda k: model_options[k], disabled=True)
        else:
            selected_model_key = None
            st.error("Cannot retrieve models from API. Verify backend service is running.")

    with model_col2:
        st.write("")
        st.write("")
        run_disabled = (not api_status.get("connected")) or (not enabled_models) or st.session_state.get("is_running", False)
        run_clicked = st.button("🚀 Run Workflow", type="primary", use_container_width=True, disabled=run_disabled)

    # Execution handling
    if run_clicked:
        # 1. Pre-flight input validations
        v_cand, parsed_cand, err_cand = parse_and_validate_json(cand_text, "Candidate Profile")
        v_jd, parsed_jd, err_jd = parse_and_validate_json(jd_text, "Job Description")
        v_comp, parsed_comp, err_comp = parse_and_validate_json(comp_text, "Company Context")

        if not v_cand:
            st.error(f"❌ Validation Error: {err_cand}")
            return
        if not v_jd:
            st.error(f"❌ Validation Error: {err_jd}")
            return
        if not v_comp:
            st.error(f"❌ Validation Error: {err_comp}")
            return

        payload = {
            "candidate_profile": parsed_cand,
            "job_description": parsed_jd,
            "company_context": parsed_comp,
            "model_config": selected_model_key
        }

        progress_container = st.container()
        with progress_container:
            status_box = st.status("Executing Multi-Agent Adversarial Workflow...", expanded=True)
            with status_box:
                st.write("🔄 **Stage 1:** Launching parallel FOR and AGAINST argument generation agents...")
                st.write("⏳ Waiting for both agents to return grounded evidence citations...")

                try:
                    with httpx.Client(timeout=120.0) as client:
                        resp = client.post(f"{api_url}/api/v1/workflows/run", json=payload)
                        if resp.status_code == 200:
                            data = resp.json()
                            status_box.update(label="✅ Evaluation Workflow Completed Successfully!", state="complete", expanded=False)
                            
                            # Cache in session state
                            if "session_executions" not in st.session_state:
                                st.session_state.session_executions = {}
                            exec_id = data["execution_id"]
                            st.session_state.session_executions[exec_id] = data["trace"]
                            st.session_state["latest_result"] = data
                            st.session_state["selected_eval_id"] = exec_id
                        else:
                            err_detail = resp.text
                            try:
                                err_detail = resp.json().get("detail", resp.text)
                            except Exception:
                                pass
                            status_box.update(label="❌ Workflow Execution Failed", state="error", expanded=True)
                            st.error(f"API Error ({resp.status_code}): {err_detail}")
                            return
                except Exception as exc:
                    status_box.update(label="❌ Network or Server Error", state="error", expanded=True)
                    st.error(f"Failed to communicate with workflow API: {str(exc)}")
                    return

    # Render latest result card if present
    if "latest_result" in st.session_state:
        res = st.session_state["latest_result"]
        judge = res.get("judge_agent")
        
        st.markdown("---")
        st.markdown("### 3. Adjudication Verdict & Results")

        if judge and judge.get("decision"):
            decision = judge["decision"]
            confidence = judge.get("confidence_percentage", 0)
            
            card_col1, card_col2, card_col3 = st.columns([2, 2, 2])
            with card_col1:
                if decision == "FOR":
                    st.success("### Decision: **FOR** (Plausible Hiring Manager)")
                else:
                    st.error("### Decision: **AGAINST** (Not a Plausible Hiring Manager)")
            with card_col2:
                st.metric(
                    label="Model Confidence Estimate",
                    value=f"{confidence}%",
                    help="Model-generated estimate, not a calibrated statistical probability."
                )
            with card_col3:
                st.metric(
                    label="Execution Duration",
                    value=f"{res.get('duration_ms', 0)} ms",
                    help="Total wall-clock duration of parallel agents and sequential Judge."
                )

            st.markdown("#### Winning Argument")
            with st.container(border=True):
                st.markdown(format_as_markdown_bullets(judge.get("winning_argument", "N/A")))

            st.markdown("#### Judge Reasoning & Evidence Verification")
            with st.container(border=True):
                st.markdown(format_as_markdown_bullets(judge.get("reasoning", "N/A")))

            # Argument previews
            with st.expander("🔍 View Opposing Arguments Submitted to Judge", expanded=False):
                arg_col1, arg_col2 = st.columns(2)
                with arg_col1:
                    st.markdown("**🟢 Argument FOR Candidate:**")
                    if res.get("for_agent"):
                        st.markdown(format_as_markdown_bullets(res["for_agent"].get("argument", "N/A")))
                        st.caption(f"Confidence: {res['for_agent'].get('confidence_score', 'N/A')}/10")
                        if res["for_agent"].get("supporting_evidence"):
                            with st.expander("📋 FOR Evidence Items", expanded=False):
                                for ev in res["for_agent"]["supporting_evidence"]:
                                    st.caption(f"• {humanize_field_label(ev.get('source_field'))}: {ev.get('exact_value')}")
                        with st.expander("🧾 Exact Raw FOR Output (JSON)", expanded=False):
                            st.json(res["for_agent"])
                with arg_col2:
                    st.markdown("**🔴 Argument AGAINST Candidate:**")
                    if res.get("against_agent"):
                        st.markdown(format_as_markdown_bullets(res["against_agent"].get("argument", "N/A")))
                        st.caption(f"Confidence: {res['against_agent'].get('confidence_score', 'N/A')}/10")
                        if res["against_agent"].get("supporting_evidence"):
                            with st.expander("📋 AGAINST Evidence Items", expanded=False):
                                for ev in res["against_agent"]["supporting_evidence"]:
                                    st.caption(f"• {humanize_field_label(ev.get('source_field'))}: {ev.get('exact_value')}")
                        with st.expander("🧾 Exact Raw AGAINST Output (JSON)", expanded=False):
                            st.json(res["against_agent"])

            st.success(f"Execution ID: `{res.get('execution_id')}` stored in session. Navigate to the **Evaluation Traces & History** tab to inspect full node traces, compare models, or persist this run to disk.")
        else:
            st.error("Workflow failed before rendering a decision.")
            if res.get("errors"):
                for err in res["errors"]:
                    st.error(f"• {err}")
