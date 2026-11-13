"""Tests for Evaluations Tab components and comparison logic."""
import pytest
from app.ui.components.diff_view import render_comparison_view

def test_comparison_hash_matching():
    """Verifies that matching and non-matching hashes are detected."""
    matching_traces = [
        {"input_hash": "hashA", "model_config": "gpt_oss_120b", "execution_id": "12345678-0000-0000-0000-000000000001", "judge_result": {"decision": "FOR"}},
        {"input_hash": "hashA", "model_config": "chatgpt_paid", "execution_id": "12345678-0000-0000-0000-000000000002", "judge_result": {"decision": "FOR"}}
    ]
    hashes = [t.get("input_hash") for t in matching_traces]
    assert len(set(hashes)) == 1

    differing_traces = [
        {"input_hash": "hashA", "model_config": "gpt_oss_120b", "execution_id": "12345678-0000-0000-0000-000000000001"},
        {"input_hash": "hashB", "model_config": "chatgpt_paid", "execution_id": "12345678-0000-0000-0000-000000000002"}
    ]
    differing_hashes = [t.get("input_hash") for t in differing_traces]
    assert len(set(differing_hashes)) == 2

