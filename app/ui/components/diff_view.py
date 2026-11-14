"""Side-by-side comparison view across multiple evaluation runs with synchronized row alignment."""
import streamlit as st
from app.schemas.agents import humanize_field_label
from typing import List, Dict, Any
from app.schemas.agents import format_as_markdown_bullets

def render_comparison_view(traces: List[Dict[str, Any]]) -> None:
    """Renders side-by-side comparative analysis of 2 or more executions with strictly aligned headings."""
    if len(traces) < 2:
        st.info("Select at least 2 completed evaluations to compare model outputs.")
        return

    # Check input hash consistency
    hashes = [t.get("input_hash", "") for t in traces]
    all_identical = len(set(hashes)) == 1

    if all_identical:
        st.success("✅ **Identical Source Inputs:** All selected runs evaluated the exact same Candidate Profile, JD, and Company Context.")
    else:
        st.warning(
            "⚠️ **Input Discrepancy Warning:** The selected runs were evaluated against different source inputs! "
            "Model outputs cannot be compared on a strictly fair basis."
        )

    n_runs = len(traces)

    # 1. Aligned Row: Run Metadata Header
    hdr_cols = st.columns(n_runs)
    for idx, (col, trace) in enumerate(zip(hdr_cols, traces)):
        with col:
            st.markdown(f"### Run {idx + 1}")
            st.markdown(f"**Model:** `{trace.get('model_config')}`")
            st.caption(f"ID: `{trace.get('execution_id')[:8]}...` | Time: `{trace.get('duration_ms', 0)} ms`")

    # 2. Aligned Row: Decision Badges
    dec_cols = st.columns(n_runs)
    for col, trace in zip(dec_cols, traces):
        with col:
            judge = trace.get("judge_result") or {}
            decision = judge.get("decision", "N/A")
            conf = judge.get("confidence_percentage", 0)

            if decision == "FOR":
                st.success(f"**Decision: FOR** ({conf}%)")
            elif decision == "AGAINST":
                st.error(f"**Decision: AGAINST** ({conf}%)")
            else:
                st.warning("Decision: Incomplete / Failed")

    st.write("")

    # 3. Aligned Row: Heading "Winning Argument:"
    win_hdr_cols = st.columns(n_runs)
    for col in win_hdr_cols:
        with col:
            st.markdown("**Winning Argument:**")

    # 4. Aligned Row: Winning Argument Content (Fixed Equal-Height Box)
    win_body_cols = st.columns(n_runs)
    for col, trace in zip(win_body_cols, traces):
        with col:
            judge = trace.get("judge_result") or {}
            win_arg = judge.get("winning_argument", "N/A")
            with st.container(height=180, border=True):
                st.markdown(format_as_markdown_bullets(win_arg))

    st.write("")

    # 5. Aligned Row: Expander "▾ Judge Reasoning" (starts at exact same vertical line)
    reason_cols = st.columns(n_runs)
    for col, trace in zip(reason_cols, traces):
        with col:
            judge = trace.get("judge_result") or {}
            reasoning = judge.get("reasoning", "N/A")
            with st.expander("▾ Judge Reasoning", expanded=True):
                with st.container(height=260, border=False):
                    st.markdown(format_as_markdown_bullets(reasoning))

    st.write("")

    # 6. Aligned Row: Expander "▾ Opposing Agent Arguments" (starts at exact same vertical line)
    opp_cols = st.columns(n_runs)
    for col, trace in zip(opp_cols, traces):
        with col:
            agents = trace.get("agents", {})
            for_out = agents.get("for", {}).get("output") or {}
            against_out = agents.get("against", {}).get("output") or {}

            with st.expander("▾ Opposing Agent Arguments", expanded=False):
                with st.container(height=380, border=False):
                    st.markdown("**🟢 FOR Agent Argument:**")
                    st.markdown(format_as_markdown_bullets(for_out.get("argument", "N/A")))
                    st.caption(f"Confidence: {for_out.get('confidence_score', 'N/A')}/10")

                    if for_out.get("supporting_evidence"):
                        with st.expander("🔍 FOR Supporting Evidence", expanded=False):
                            for ev in for_out.get("supporting_evidence", []):
                                st.caption(f"• {humanize_field_label(ev.get('source_field'))}: {ev.get('exact_value')}")

                    with st.expander("🧾 Exact Raw FOR Output (JSON)", expanded=False):
                        if for_out:
                            st.json(for_out)
                        else:
                            st.caption("No output generated or agent failed.")

                    st.divider()

                    st.markdown("**🔴 AGAINST Agent Argument:**")
                    st.markdown(format_as_markdown_bullets(against_out.get("argument", "N/A")))
                    st.caption(f"Confidence: {against_out.get('confidence_score', 'N/A')}/10")

                    if against_out.get("supporting_evidence"):
                        with st.expander("🔍 AGAINST Supporting Evidence", expanded=False):
                            for ev in against_out.get("supporting_evidence", []):
                                st.caption(f"• {humanize_field_label(ev.get('source_field'))}: {ev.get('exact_value')}")

                    with st.expander("🧾 Exact Raw AGAINST Output (JSON)", expanded=False):
                        if against_out:
                            st.json(against_out)
                        else:
                            st.caption("No output generated or agent failed.")
