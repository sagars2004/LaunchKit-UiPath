"""LaunchKit Analyze — UiPath coded agent using external coding CLIs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from coding_agents.prompt import build_analysis_prompt, criteria_summary_from_brief
from coding_agents.repo import (
    cleanup_repo,
    clone_repo,
    collect_repo_context,
    format_key_files,
)
from coding_agents.runner import CodingAgentError, CodingAgentRunner
from coding_agents.types import CodingTool

ANALYZE_TIMEOUT_SECONDS = 300.0
CONNECT_TIMEOUT_SECONDS = 30.0


def _client() -> httpx.Client:
    timeout = httpx.Timeout(ANALYZE_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS)
    return httpx.Client(timeout=timeout)


def _warmup(client: httpx.Client, base: str) -> None:
    try:
        client.get(f"{base}/health")
    except httpx.HTTPError:
        pass


def _fetch_run(client: httpx.Client, base: str, run_id: str, api_secret: str) -> dict:
    headers = {"Authorization": f"Bearer {api_secret}"}
    response = client.get(f"{base}/api/v1/runs/{run_id}", headers=headers)
    response.raise_for_status()
    return response.json()["run"]


def _submit_analysis(
    client: httpx.Client,
    base: str,
    run_id: str,
    api_secret: str,
    *,
    code_intelligence: dict,
    repo_context: dict,
    coding_tool: CodingTool,
) -> dict:
    headers = {"Authorization": f"Bearer {api_secret}"}
    payload = {
        "code_intelligence": code_intelligence,
        "repo_context": repo_context,
        "coding_tool": coding_tool,
    }
    response = client.post(
        f"{base}/api/v1/runs/{run_id}/analyze/submit",
        headers=headers,
        json=payload,
    )
    if response.status_code == 422:
        raise CodingAgentError(
            f"API rejected code_intelligence: {response.text}"
        )
    response.raise_for_status()
    return response.json()


@dataclass
class AnalyzeWithCodingAgentIn:
    run_id: str
    api_url: str
    api_secret: str
    coding_tool: str = "cursor"
    repo_path: str = ""
    work_dir: str = ""


@dataclass
class AnalyzeWithCodingAgentOut:
    run_id: str
    status: str
    message: str
    coding_tool: str


def analyze_with_coding_agent(input: AnalyzeWithCodingAgentIn) -> AnalyzeWithCodingAgentOut:
    """Clone repo, invoke a coding CLI, and submit CodeIntelligence to LaunchKit."""
    base = input.api_url.rstrip("/")
    repo_path: Path | None = Path(input.repo_path) if input.repo_path else None
    should_cleanup = False

    with _client() as client:
        _warmup(client, base)
        run = _fetch_run(client, base, input.run_id, input.api_secret)

        if not run.get("hackathon_brief"):
            raise CodingAgentError("Run intel required — POST /runs/{id}/intel first")

        github_url = run["intake"]["github_url"]
        if repo_path is None:
            repo_path, should_cleanup = clone_repo(github_url, input.work_dir or None)

        try:
            context = collect_repo_context(repo_path, github_url)
            prompt = build_analysis_prompt(
                file_tree=context.file_tree,
                key_file_contents=format_key_files(context.key_files),
                hackathon_criteria_summary=criteria_summary_from_brief(run["hackathon_brief"]),
            )

            runner = CodingAgentRunner(timeout_seconds=ANALYZE_TIMEOUT_SECONDS)
            result = runner.analyze_repo(
                tool=input.coding_tool,
                prompt=prompt,
                repo_path=str(repo_path),
            )

            data = _submit_analysis(
                client,
                base,
                input.run_id,
                input.api_secret,
                code_intelligence=result.parsed,
                repo_context=context.to_dict(),
                coding_tool=input.coding_tool,
            )
        finally:
            if repo_path is not None:
                cleanup_repo(repo_path, should_cleanup)

    return AnalyzeWithCodingAgentOut(
        run_id=str(data.get("run_id", input.run_id)),
        status=str(data.get("status", "")),
        message=str(data.get("message", "")),
        coding_tool=str(data.get("coding_tool", input.coding_tool)),
    )
