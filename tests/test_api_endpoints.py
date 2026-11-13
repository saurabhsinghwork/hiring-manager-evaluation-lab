"""Integration tests for all FastAPI endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport
import uuid
from datetime import datetime, timezone

from app.api.main import app
from app.services.model_registry import ModelRegistry
from app.services.workflow_service import WorkflowService
from app.llm.base import BaseChatAdapter
from app.schemas.agents import ArgumentAgentOutput, EvidenceItem, JudgeOutput

class MockEndpointAdapter(BaseChatAdapter):
    def __init__(self):
        super().__init__(model_id="test-endpoint-model", provider_name="test_provider")

    async def generate_structured(self, prompt: str, system_prompt: str, response_model):
        if response_model == ArgumentAgentOutput:
            return ArgumentAgentOutput(
                argument="Candidate has direct hiring manager alignment.",
                supporting_evidence=[
                    EvidenceItem(source_field="candidate_profile.title", exact_value="Engineering Manager")
                ],
                confidence_score=9
            )
        elif response_model == JudgeOutput:
            return JudgeOutput(
                decision="FOR",
                winning_argument="Candidate has direct hiring manager alignment.",
                reasoning="Evidence clearly verifies the candidate's hiring management responsibility.",
                confidence_percentage=90
            )
        raise ValueError(f"Unknown model {response_model}")

@pytest.mark.asyncio
async def test_api_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_api_models_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        keys = [m["key"] for m in data["models"]]
        assert "gpt_oss_120b" in keys
        assert "qwen" in keys
        assert "chatgpt_paid" in keys

@pytest.mark.asyncio
async def test_api_workflow_run_endpoint(monkeypatch):
    # Patch registry in workflow_service to return our MockEndpointAdapter
    mock_adapter = MockEndpointAdapter()
    monkeypatch.setattr("app.services.workflow_service.workflow_service.registry.get_adapter", lambda key: mock_adapter)

    payload = {
        "candidate_profile": {"name": "Alex", "title": "Engineering Manager"},
        "job_description": {"title": "Software Engineer", "team": "Core Platform"},
        "company_context": {"size": "Large"},
        "model_config": "chatgpt_paid"
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/workflows/run", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["judge_agent"]["decision"] == "FOR"
        assert data["judge_agent"]["confidence_percentage"] == 90
        assert "trace" in data
        assert data["trace"]["workflow_status"] == "completed"

@pytest.mark.asyncio
async def test_api_evaluations_crud_and_traversal_protection(tmp_path, monkeypatch):
    # Point evaluation store to isolated tmp_path
    from app.services.evaluation_store import evaluation_store
    monkeypatch.setattr(evaluation_store, "data_dir", tmp_path)

    exec_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    trace_payload = {
        "execution_id": exec_id,
        "created_at": now_iso,
        "completed_at": now_iso,
        "source_input": {"candidate_profile": {"name": "Test"}},
        "input_hash": "testhash123",
        "model_config": "chatgpt_paid",
        "workflow_status": "completed",
        "agents": {
            "for": {
                "model_id": "test-model",
                "status": "completed",
                "input": {},
                "output": {"argument": "Test"},
                "started_at": now_iso,
                "completed_at": now_iso,
                "duration_ms": 100
            },
            "against": {
                "model_id": "test-model",
                "status": "completed",
                "input": {},
                "output": {"argument": "Test"},
                "started_at": now_iso,
                "completed_at": now_iso,
                "duration_ms": 100
            },
            "judge": {
                "model_id": "test-model",
                "status": "completed",
                "input": {},
                "output": {"decision": "FOR"},
                "started_at": now_iso,
                "completed_at": now_iso,
                "duration_ms": 100
            }
        },
        "judge_result": {
            "decision": "FOR",
            "winning_argument": "Candidate is hiring manager",
            "reasoning": "Direct evidence verified",
            "confidence_percentage": 92
        },
        "duration_ms": 300,
        "errors": []
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Path traversal defense
        bad_resp = await client.get("/api/v1/evaluations/../../etc/passwd")
        assert bad_resp.status_code in [400, 404]

        # 2. Save evaluation
        save_resp = await client.post(f"/api/v1/evaluations/{exec_id}/save", json=trace_payload)
        assert save_resp.status_code == 200
        assert save_resp.json()["status"] == "saved"

        # 3. List evaluations
        list_resp = await client.get("/api/v1/evaluations")
        assert list_resp.status_code == 200
        saved_list = list_resp.json()
        assert len(saved_list) == 1
        assert saved_list[0]["execution_id"] == exec_id
        assert saved_list[0]["decision"] == "FOR"

        # 4. Get single evaluation
        get_resp = await client.get(f"/api/v1/evaluations/{exec_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["execution_id"] == exec_id

        # 5. Delete evaluation
        del_resp = await client.delete(f"/api/v1/evaluations/{exec_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

        # 6. Verify 404 after deletion
        get_again = await client.get(f"/api/v1/evaluations/{exec_id}")
        assert get_again.status_code == 404

