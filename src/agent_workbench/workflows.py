"""Named task modes and reusable workflow prompt templates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Workflow:
    """A reviewed workflow exposed by the workbench."""

    id: str
    name: str
    description: str
    min_files: int
    instructions: str


WORKFLOWS = (
    Workflow(
        id="summarise",
        name="Summarise files",
        description="Produce a concise, structured brief with the important points.",
        min_files=1,
        instructions=(
            "Summarise the supplied material. Include an executive summary, key "
            "points, important figures or dates, and uncertainties. Do not invent "
            "facts that are not supported by the files."
        ),
    ),
    Workflow(
        id="extract-actions",
        name="Extract actions",
        description="Turn notes or documents into owners, actions and open questions.",
        min_files=1,
        instructions=(
            "Extract decisions, action items, owners, deadlines, dependencies and "
            "open questions. Use a Markdown table for actions. Mark missing owners "
            "or dates as unassigned rather than guessing."
        ),
    ),
    Workflow(
        id="compare",
        name="Compare documents",
        description="Identify agreement, differences, conflicts and missing coverage.",
        min_files=2,
        instructions=(
            "Compare the supplied files. Explain areas of agreement, material "
            "differences, contradictions and information present in only one file. "
            "Finish with the practical implications of those differences."
        ),
    ),
    Workflow(
        id="data-quality",
        name="Review data quality",
        description="Profile tabular data and flag anomalies or reliability risks.",
        min_files=1,
        instructions=(
            "Review the supplied data for schema, completeness, duplicates, invalid "
            "values, outliers and internal consistency. Quantify findings where "
            "possible and separate observed facts from hypotheses."
        ),
    ),
)

WORKFLOW_BY_ID = {workflow.id: workflow for workflow in WORKFLOWS}
MODES = {"ask", "analyse", "workflow"}


def build_task_prompt(mode: str, workflow_id: str, prompt: str) -> str:
    """Build reviewed agent instructions while preserving the user's prompt."""
    user_prompt = prompt.strip()
    if mode not in MODES:
        raise ValueError("Unknown workbench mode.")

    if mode == "ask":
        return (
            "Answer the user's question directly and concisely. Use attached files "
            "only when they are relevant. If evidence is insufficient, say so.\n\n"
            f"User request:\n{user_prompt}"
        )

    if mode == "analyse":
        return (
            "Investigate the supplied files in response to the user's request. "
            "Ground conclusions in the files, distinguish facts from inference, "
            "and present a useful Markdown report.\n\n"
            f"User request:\n{user_prompt}"
        )

    workflow = WORKFLOW_BY_ID.get(workflow_id)
    if workflow is None:
        raise ValueError("Select a valid workflow.")
    return (
        f"Run the reviewed workflow: {workflow.name}.\n\n"
        f"Workflow instructions:\n{workflow.instructions}\n\n"
        f"User context or emphasis:\n{user_prompt}"
    )


def validate_submission(mode: str, workflow_id: str, file_count: int) -> None:
    """Reject inconsistent mode, workflow and upload combinations."""
    if mode not in MODES:
        raise ValueError("Select Ask, Analyse or Workflow.")
    if mode == "analyse" and file_count < 1:
        raise ValueError("Analyse requires at least one file.")
    if mode != "workflow":
        if workflow_id:
            raise ValueError("A workflow can only be selected in Workflow mode.")
        return

    workflow = WORKFLOW_BY_ID.get(workflow_id)
    if workflow is None:
        raise ValueError("Select a valid workflow.")
    if file_count < workflow.min_files:
        noun = "file" if workflow.min_files == 1 else "files"
        raise ValueError(
            f"{workflow.name} requires at least {workflow.min_files} {noun}."
        )
