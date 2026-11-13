"""Evaluation persistence endpoints."""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from app.schemas.evaluations import EvaluationSummary, EvaluationTrace
from app.services.evaluation_store import evaluation_store

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])

@router.get("", response_model=List[EvaluationSummary], response_model_by_alias=True, summary="List saved evaluations")
async def list_evaluations() -> List[EvaluationSummary]:
    """Returns summary metadata for all saved evaluations."""
    return evaluation_store.list_evaluations()

@router.get("/{execution_id}", response_model=EvaluationTrace, response_model_by_alias=True, summary="Get evaluation trace")
async def get_evaluation(execution_id: str) -> EvaluationTrace:
    """Retrieves full evaluation trace by unique execution ID."""
    try:
        return evaluation_store.get_evaluation(execution_id)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Evaluation '{execution_id}' not found.")

@router.post("/{execution_id}/save", summary="Persist evaluation trace")
async def save_evaluation(execution_id: str, trace: EvaluationTrace) -> Dict[str, Any]:
    """Persists an in-memory session evaluation trace to local JSON storage."""
    try:
        if trace.execution_id != execution_id:
            raise ValueError(f"Payload execution_id '{trace.execution_id}' does not match URL '{execution_id}'.")
        saved = evaluation_store.save_evaluation(trace)
        return {
            "status": "saved",
            "execution_id": saved.execution_id,
            "message": "Evaluation trace successfully persisted to disk."
        }
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save evaluation: {str(exc)}"
        )

@router.delete("/{execution_id}", summary="Delete saved evaluation")
async def delete_evaluation(execution_id: str) -> Dict[str, Any]:
    """Permanently deletes a saved evaluation file from local storage."""
    try:
        evaluation_store.delete_evaluation(execution_id)
        return {
            "status": "deleted",
            "execution_id": execution_id,
            "message": f"Evaluation '{execution_id}' deleted successfully."
        }
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Evaluation '{execution_id}' not found.")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete evaluation: {str(exc)}"
        )

