"""Local JSON evaluation store with atomic file operations and traversal protection."""
import json
import logging
import os
import re
from pathlib import Path
from typing import List, Optional
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.schemas.evaluations import EvaluationTrace, EvaluationSummary
from app.schemas.workflow import WorkflowStatus

logger = logging.getLogger("hiring_eval_lab.store")
UUID_PATTERN = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

class EvaluationStore:
    """Manages file-based evaluation persistence under data/evaluations/."""

    def __init__(self, current_settings: Optional[Settings] = None):
        self.settings = current_settings or settings
        self.data_dir: Path = self.settings.evaluation_data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _validate_execution_id(self, execution_id: str) -> None:
        """Protects against path traversal by enforcing strict UUID format."""
        if not UUID_PATTERN.match(execution_id):
            raise ValueError(f"Invalid execution_id format: '{execution_id}'. Must be a valid UUID.")

    def _get_file_path(self, execution_id: str) -> Path:
        self._validate_execution_id(execution_id)
        return self.data_dir / f"{execution_id}.json"

    def list_evaluations(self) -> List[EvaluationSummary]:
        """Lists metadata summaries for all saved evaluations. Skips corrupted files safely."""
        summaries: List[EvaluationSummary] = []
        if not self.data_dir.exists():
            return summaries

        for file_path in self.data_dir.glob("*.json"):
            if not UUID_PATTERN.match(file_path.stem):
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                decision = None
                conf_pct = None
                if data.get("judge_result"):
                    decision = data["judge_result"].get("decision")
                    conf_pct = data["judge_result"].get("confidence_percentage")

                summaries.append(
                    EvaluationSummary(
                        execution_id=data["execution_id"],
                        created_at=data["created_at"],
                        model_config=data.get("model_config", "unknown"),
                        workflow_status=WorkflowStatus(data.get("workflow_status", "completed")),
                        decision=decision,
                        confidence_percentage=conf_pct,
                        duration_ms=data.get("duration_ms", 0),
                        input_hash=data.get("input_hash", ""),
                        is_saved=True
                    )
                )
            except (json.JSONDecodeError, KeyError, ValidationError) as err:
                logger.warning(f"Skipping unreadable or corrupted evaluation file {file_path.name}: {err}")
            except Exception as err:
                logger.error(f"Unexpected error reading {file_path.name}: {err}")

        # Sort newest first
        summaries.sort(key=lambda x: x.created_at, reverse=True)
        return summaries

    def get_evaluation(self, execution_id: str) -> EvaluationTrace:
        """Retrieves and validates a complete saved evaluation trace."""
        file_path = self._get_file_path(execution_id)
        if not file_path.exists():
            raise FileNotFoundError(f"Evaluation with ID '{execution_id}' does not exist.")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return EvaluationTrace.model_validate(data)

    def save_evaluation(self, trace: EvaluationTrace) -> EvaluationTrace:
        """Atomically saves an evaluation trace to disk."""
        target_path = self._get_file_path(trace.execution_id)
        temp_path = self.data_dir / f"{trace.execution_id}.tmp"

        payload = trace.model_dump(by_alias=True)
        # Write to temporary file, flush to OS buffer, then atomically replace
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, target_path)
        logger.info(f"Persisted evaluation trace to {target_path}")
        return trace

    def delete_evaluation(self, execution_id: str) -> bool:
        """Deletes a saved evaluation trace file."""
        file_path = self._get_file_path(execution_id)
        if not file_path.exists():
            raise FileNotFoundError(f"Evaluation with ID '{execution_id}' does not exist.")

        file_path.unlink()
        logger.info(f"Deleted evaluation trace at {file_path}")
        return True

evaluation_store = EvaluationStore()

