"""Evaluations management tab for trace inspection, persistence, and comparisons."""
import httpx
import streamlit as st
from typing import Dict, Any, List

from app.ui.components.trace_viewer import render_trace_detail_view
from app.ui.components.diff_view import render_comparison_view

def fetch_saved_evaluations(api_url: str) -> List[Dict[str, Any]]:
    """Fetches saved evaluation summaries from GET /api/v1/evaluations."""
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{api_url}/api/v1/evaluations")
            if resp.status_code == 200:
                return resp.json()
            return []
    except Exception:
        return []

def fetch_single_trace(api_url: str, execution_id: str) -> Dict[str, Any]:
    """Fetches full saved evaluation trace from GET /api/v1/evaluations/{id}."""
    with httpx.Client(timeout=5.0) as client:
        resp = client.get(f"{api_url}/api/v1/evaluations/{execution_id}")
        if resp.status_code == 200:
            return resp.json()
        raise RuntimeError(f"Failed to fetch evaluation {execution_id}: {resp.status_code}")

def save_trace_to_api(api_url: str, trace: Dict[str, Any]) -> bool:
    """Persists a session trace via POST /api/v1/evaluations/{id}/save."""
    exec_id = trace["execution_id"]
    with httpx.Client(timeout=5.0) as client:
        resp = client.post(f"{api_url}/api/v1/evaluations/{exec_id}/save", json=trace)
        return resp.status_code == 200

def delete_trace_from_api(api_url: str, execution_id: str) -> bool:
    """Deletes a saved trace via DELETE /api/v1/evaluations/{id}."""
    with httpx.Client(timeout=5.0) as client:
        resp = client.delete(f"{api_url}/api/v1/evaluations/{execution_id}")
        return resp.status_code == 200

def render_evaluations_tab(api_status: Dict[str, Any]) -> None:
    """Renders the comprehensive Evaluations tab."""
    api_url = api_status.get("url", "http://127.0.0.1:8000")

    # Ensure session state structure
    if "session_executions" not in st.session_state:
        st.session_state.session_executions = {}

    saved_summaries = fetch_saved_evaluations(api_url)
    saved_ids = {s["execution_id"] for s in saved_summaries}

    # Build master list of all available executions
    all_executions: List[Dict[str, Any]] = []

    # 1. Add session executions
    for exec_id, trace in st.session_state.session_executions.items():
        is_saved = exec_id in saved_ids
        judge = trace.get("judge_result") or {}
        all_executions.append({
            "execution_id": exec_id,
            "created_at": trace.get("created_at", "N/A"),
            "model_config": trace.get("model_config", "unknown"),
            "workflow_status": trace.get("workflow_status", "unknown"),
            "decision": judge.get("decision", "N/A"),
            "confidence": judge.get("confidence_percentage", "N/A"),
            "is_saved": is_saved,
            "trace": trace
        })

    # 2. Add saved evaluations not currently in session state
    for summary in saved_summaries:
        s_id = summary["execution_id"]
        if s_id not in st.session_state.session_executions:
            all_executions.append({
                "execution_id": s_id,
                "created_at": summary.get("created_at", "N/A"),
                "model_config": summary.get("model_config", "unknown"),
                "workflow_status": summary.get("workflow_status", "unknown"),
                "decision": summary.get("decision", "N/A"),
                "confidence": summary.get("confidence_percentage", "N/A"),
                "is_saved": True,
                "trace": None  # Load on demand
            })

    if not all_executions:
        st.info("ℹ️ No evaluations recorded yet. Run an evaluation in the **Workflow Execution** tab first.")
        return

    # Radio selector for sub-view
    view_mode = st.radio(
        "Select Mode",
        ["🔍 Single Trace Inspector", "⚖️ Side-by-Side Model Comparison"],
        horizontal=True
    )

    st.markdown("---")

    if view_mode == "🔍 Single Trace Inspector":
        # Formatter for execution selector
        def format_exec_label(item: Dict[str, Any]) -> str:
            tag = "💾 [Saved to Disk]" if item["is_saved"] else "⚡ [Session Only]"
            return f"{tag} | {item['model_config']} | Verdict: {item['decision']} ({item['confidence']}%) | ID: {item['execution_id'][:8]}..."

        # Determine default selection
        default_idx = 0
        selected_id = st.session_state.get("selected_eval_id")
        if selected_id:
            for idx, item in enumerate(all_executions):
                if item["execution_id"] == selected_id:
                    default_idx = idx
                    break

        selected_item = st.selectbox(
            "Select Evaluation Record",
            options=all_executions,
            index=default_idx,
            format_func=format_exec_label
        )

        if selected_item:
            current_id = selected_item["execution_id"]
            # Fetch trace if not already loaded
            trace_data = selected_item["trace"]
            if trace_data is None:
                try:
                    trace_data = fetch_single_trace(api_url, current_id)
                except Exception as exc:
                    st.error(f"Failed to load trace: {exc}")
                    return

            # Actions Bar (Save / Delete)
            act_col1, act_col2, _ = st.columns([1.5, 2, 3])
            with act_col1:
                if not selected_item["is_saved"]:
                    if st.button("💾 Save Trace to Disk", type="primary", use_container_width=True):
                        if save_trace_to_api(api_url, trace_data):
                            st.success("Successfully saved to disk!")
                            st.rerun()
                        else:
                            st.error("Failed to save trace to disk.")
                else:
                    st.success("✅ Persisted on Disk (`data/evaluations/`)")

            with act_col2:
                if selected_item["is_saved"]:
                    with st.popover("🗑️ Delete Saved Evaluation"):
                        st.warning("Are you sure? This will permanently delete the JSON file from disk.")
                        if st.button("Confirm Permanent Deletion", type="primary"):
                            if delete_trace_from_api(api_url, current_id):
                                st.success("Deleted successfully!")
                                st.rerun()
                            else:
                                st.error("Failed to delete.")

            st.markdown("---")
            render_trace_detail_view(trace_data)

    elif view_mode == "⚖️ Side-by-Side Model Comparison":
        st.markdown("### Compare Separate Model Runs")
        st.write("Select two or more completed evaluations to compare their opposing arguments and Judge decisions side by side.")

        def format_comp_label(item: Dict[str, Any]) -> str:
            tag = "[Saved]" if item["is_saved"] else "[Session]"
            return f"{tag} {item['model_config']} - {item['decision']} ({item['execution_id'][:8]}...)"

        selected_items = st.multiselect(
            "Choose 2+ Executions to Compare",
            options=all_executions,
            format_func=format_comp_label,
            default=all_executions[:2] if len(all_executions) >= 2 else all_executions
        )

        loaded_traces: List[Dict[str, Any]] = []
        for item in selected_items:
            t = item["trace"]
            if t is None:
                try:
                    t = fetch_single_trace(api_url, item["execution_id"])
                except Exception as exc:
                    st.error(f"Failed to load trace for comparison: {exc}")
                    continue
            loaded_traces.append(t)

        render_comparison_view(loaded_traces)
