"""Model configuration catalog endpoints."""
from fastapi import APIRouter
from app.schemas.evaluations import ModelListResponse
from app.services.model_registry import model_registry

router = APIRouter(prefix="/api/v1", tags=["models"])

@router.get("/models", response_model=ModelListResponse, summary="List available model configurations")
async def get_models() -> ModelListResponse:
    """Returns list of configured model options and availability status without exposing credentials."""
    return ModelListResponse(models=model_registry.list_options())

