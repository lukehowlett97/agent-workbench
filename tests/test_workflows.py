"""Tests for reviewed workbench modes and workflows."""

import pytest

from agent_workbench.workflows import build_task_prompt, validate_submission


def test_ask_builds_direct_task_without_files() -> None:
    validate_submission("ask", "", 0)

    task = build_task_prompt("ask", "", "What is in this report?")

    assert "Answer the user's question directly" in task
    assert "What is in this report?" in task


def test_analysis_requires_a_file() -> None:
    with pytest.raises(ValueError, match="at least one file"):
        validate_submission("analyse", "", 0)


def test_compare_requires_two_files() -> None:
    with pytest.raises(ValueError, match="at least 2 files"):
        validate_submission("workflow", "compare", 1)

    validate_submission("workflow", "compare", 2)
    task = build_task_prompt("workflow", "compare", "Focus on cost")

    assert "Compare documents" in task
    assert "contradictions" in task
    assert "Focus on cost" in task


def test_unknown_workflow_is_rejected() -> None:
    with pytest.raises(ValueError, match="valid workflow"):
        validate_submission("workflow", "made-up", 1)
