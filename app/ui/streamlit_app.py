"""Streamlit Application Shell for Hiring Manager Evaluation Lab."""
import streamlit as st
import httpx
import os

from app.ui.workflow_tab import render_workflow_tab
from app.ui.evaluations_tab import render_evaluations_tab

# Page configuration
st.set_page_config(
    page_title="Hiring Manager Evaluation Lab",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API endpoint configuration
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

def check_api_health() -> dict:
    """Checks whether the FastAPI backend is running and healthy."""
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{API_URL}/health")
            if resp.status_code == 200:
                return {"connected": True, "data": resp.json(), "url": API_URL}
            return {"connected": False, "error": f"Status code {resp.status_code}", "url": API_URL}
    except Exception as exc:
        return {"connected": False, "error": str(exc), "url": API_URL}

def main() -> None:
    st.title("⚖️ Hiring Manager Evaluation Lab")
    st.caption("Adversarial multi-agent evaluation platform for candidate hiring manager plausibility")

    # Check backend connectivity
    api_status = check_api_health()

    # Sidebar
    with st.sidebar:
        st.subheader("System Status")
        if api_status["connected"]:
            st.success("🟢 API Service Connected")
            st.caption(f"Host: `{API_URL}`")
        else:
            st.error("🔴 API Service Disconnected")
            st.caption(f"Target: `{API_URL}`")
            st.warning("Ensure the FastAPI backend is running:\n`uvicorn app.api.main:app --port 8000`")
        
        st.divider()
        st.markdown("**Version:** `1.0.0 (Baseline)`")
        st.markdown("**Framework:** FastAPI + LangGraph + Streamlit")

    # Main Tabs
    tab1, tab2 = st.tabs(["🚀 Workflow Execution", "📋 Evaluation Traces & History"])

    with tab1:
        render_workflow_tab(api_status)

    with tab2:
        render_evaluations_tab(api_status)

if __name__ == "__main__":
    main()
