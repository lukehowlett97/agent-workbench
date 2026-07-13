"""Validate NVIDIA NIM chat and tool-calling compatibility.

Inputs:
    NVIDIA_API_KEY and optional model/base URL environment variables.

Outputs:
    A JSON summary on stdout and a non-zero exit code if a check fails.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODELS = (
    "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/nemotron-3-super-120b-a12b",
)


@dataclass
class CheckResult:
    """Store the outcome and timing of one model check."""

    model: str
    completion_ok: bool
    tool_call_ok: bool
    latency_seconds: float
    detail: str


def create_client() -> OpenAI:
    """Create an NVIDIA NIM client from environment variables.

    Returns:
        Configured OpenAI-compatible client.

    Raises:
        RuntimeError: If NVIDIA_API_KEY is missing.
    """
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY is required and must not be committed.")

    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("NVIDIA_BASE_URL", DEFAULT_BASE_URL),
        timeout=120.0,
        max_retries=2,
    )


def validate_model(client: OpenAI, model: str) -> CheckResult:
    """Test basic completion and structured tool calling for one model.

    Args:
        client: Configured NVIDIA NIM client.
        model: NVIDIA catalogue model identifier.

    Returns:
        Combined result for the model.
    """
    started = time.monotonic()
    completion_ok = False
    tool_call_ok = False
    details: list[str] = []

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": "Reply with exactly: NIM connection successful",
                }
            ],
            temperature=0,
            max_tokens=64,
        )
        answer = (completion.choices[0].message.content or "").strip()
        completion_ok = "NIM connection successful" in answer
        details.append(f"completion={answer!r}")
    except Exception as exc:  # The report must preserve provider failure context.
        details.append(f"completion_error={type(exc).__name__}: {exc}")

    try:
        tool_response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": "Record a report named smoke-test.md with 3 findings.",
                }
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "write_report",
                        "description": "Write a report to the job output directory.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "filename": {"type": "string"},
                                "finding_count": {"type": "integer"},
                            },
                            "required": ["filename", "finding_count"],
                            "additionalProperties": False,
                        },
                    },
                }
            ],
            tool_choice="required",
            temperature=0,
            max_tokens=256,
        )
        calls = tool_response.choices[0].message.tool_calls or []
        if calls:
            arguments: dict[str, Any] = json.loads(calls[0].function.arguments)
            tool_call_ok = (
                calls[0].function.name == "write_report"
                and arguments.get("filename") == "smoke-test.md"
                and arguments.get("finding_count") == 3
            )
            details.append(f"tool_call={calls[0].function.name}:{arguments}")
        else:
            details.append("tool_call=missing")
    except Exception as exc:
        details.append(f"tool_error={type(exc).__name__}: {exc}")

    return CheckResult(
        model=model,
        completion_ok=completion_ok,
        tool_call_ok=tool_call_ok,
        latency_seconds=round(time.monotonic() - started, 3),
        detail="; ".join(details),
    )


def write_results(results: list[CheckResult], output: Path | None) -> None:
    """Print results and optionally save the same JSON report.

    Args:
        results: Model check results.
        output: Optional report destination.
    """
    payload = {
        "passed": any(
            result.completion_ok and result.tool_call_ok for result in results
        ),
        "results": [asdict(result) for result in results],
    }
    rendered = json.dumps(payload, indent=2)
    print(rendered)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"{rendered}\n", encoding="utf-8")


def main() -> int:
    """Run Stage 0 model validation and return a shell exit code."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help="Model to test; repeat to compare models.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    models = args.models or [
        os.getenv("NVIDIA_PRIMARY_MODEL", DEFAULT_MODELS[0]),
        os.getenv("NVIDIA_COMPARISON_MODEL", DEFAULT_MODELS[1]),
    ]

    try:
        client = create_client()
    except RuntimeError as exc:
        parser.error(str(exc))

    results = [validate_model(client, model) for model in dict.fromkeys(models)]
    write_results(results, args.output)
    return 0 if any(r.completion_ok and r.tool_call_ok for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
