"""Expandable trace viewer component displaying per-agent execution telemetry."""
import streamlit as st
from app.schemas.agents import humanize_field_label
from typing import Dict, Any
from app.schemas.agents import format_as_markdown_bullets

def agent_model_name(model_id: Any) -> str:
    """Short friendly model name for display (Qwen, GPT-OSS, ...)."""
    text = str(model_id or "").lower()
    if "qwen" in text:
        return "Qwen"
    if "oss" in text:
        return "GPT-OSS"
    return str(model_id) if model_id else "N/A"


def agent_model_of(trace: Dict[str, Any], agent: str) -> str:
    """Friendly model name for one agent ('for', 'against', 'judge') of a trace."""
    return agent_model_name(((trace or {}).get("agents", {}).get(agent) or {}).get("model_id"))


def render_agent_card(title: str, agent_trace: Dict[str, Any], badge_color: str = "blue") -> None:
    """Renders details for an individual agent in an expander."""
    status = agent_trace.get("status", "unknown").upper()
    duration = agent_trace.get("duration_ms", 0)
    model_id = agent_model_name(agent_trace.get("model_id", "N/A"))

    expander_title = f"{title} — Status: {status} | Duration: {duration}ms | Model: {model_id}"
    with st.expander(expander_title, expanded=(status == "COMPLETED")):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.caption(f"**Model:** `{model_id}`")
        with col2:
            st.caption(f"**Execution Time:** `{duration} ms`")
        with col3:
            st.caption(f"**Status:** `{status}`")

        # Output
        output = agent_trace.get("output")
        if output:
            if "argument" in output:
                st.markdown("##### Generated Argument (Markdown)")
                st.markdown(format_as_markdown_bullets(output["argument"]))
                st.caption(f"**Confidence Score:** {output.get('confidence_score', 'N/A')}/10")
                if output.get("supporting_evidence"):
                    st.markdown("##### Supporting Evidence Citations")
                    for ev in output.get("supporting_evidence", []):
                        st.caption(f"• {humanize_field_label(ev.get('source_field'))}: {ev.get('exact_value')}")
            elif "winning_argument" in output:
                st.markdown(f"##### Decision: **{output.get('decision', 'N/A')}** ({output.get('confidence_percentage', 0)}%)")
                st.markdown("##### Winning Argument")
                st.markdown(format_as_markdown_bullets(output.get("winning_argument", "N/A")))
                st.markdown("##### Judge Reasoning")
                st.markdown(format_as_markdown_bullets(output.get("reasoning", "N/A")))

            with st.expander("🧾 Exact Raw Output (JSON)", expanded=False):
                st.json(output)
        elif agent_trace.get("error"):
            st.error(f"Error: {agent_trace['error']}")
        else:
            st.info("No output recorded for this agent.")

        # Sanitized Prompt
        if agent_trace.get("input"):
            with st.expander("🔍 View Raw Sanitized Prompt Sent to Model", expanded=False):
                st.code(agent_trace["input"].get("prompt", "N/A"), language="markdown")

def render_trace_detail_view(trace: Dict[str, Any]) -> None:
    """Renders the complete evaluation trace detail view."""
    st.markdown("#### Execution Trace Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"**Execution ID:** `{trace.get('execution_id')}`")
    with col2:
        st.markdown(f"**Model Config:** `{trace.get('model_config')}`")
    with col3:
        status = trace.get("workflow_status", "unknown").upper()
        if status == "COMPLETED":
            st.success(f"Status: **{status}**")
        else:
            st.error(f"Status: **{status}**")
    with col4:
        st.markdown(f"**Total Duration:** `{trace.get('duration_ms', 0)} ms`")

    # Source inputs viewer
    with st.expander("📦 Original Source Inputs (Candidate Profile, JD, Company Context)", expanded=False):
        st.caption(f"Input Hash (SHA-256): `{trace.get('input_hash', 'N/A')}`")
        st.json(trace.get("source_input", {}))

    st.markdown("---")
    st.markdown("#### Agent Execution Traces")
    
    agents = trace.get("agents", {})
    if "for" in agents:
        render_agent_card("🟢 FOR Argument Agent", agents["for"])
    if "against" in agents:
        render_agent_card("🔴 AGAINST Argument Agent", agents["against"])
    if "judge" in agents:
        render_agent_card("⚖️ Judge Agent (Model-Blind Adjudication)", agents["judge"])

    # Final verdict
    if trace.get("judge_result"):
        with st.expander("🏆 Final Adjudication Verdict", expanded=True):
            st.json(trace["judge_result"])

