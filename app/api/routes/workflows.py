"""Workflow execution endpoints."""
from fastapi import APIRouter, HTTPException, status
from app.schemas.inputs import WorkflowRequest
from app.schemas.workflow import WorkflowResponse
from app.services.workflow_service import workflow_service

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])

@router.post(
    "/run",
    response_model=WorkflowResponse,
    response_model_by_alias=True,
    summary="Execute adversarial hiring manager evaluation workflow"
)
async def run_workflow(request: WorkflowRequest) -> WorkflowResponse:
    """Executes the three-agent evaluation workflow (FOR, AGAINST, Judge) and returns the decision & trace."""
    try:
        response = await workflow_service.execute_workflow(request)
        return response
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow execution failure: {str(exc)}"
        )

