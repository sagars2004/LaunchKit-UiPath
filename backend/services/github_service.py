"""GitHub API client — repo ingestion, README push, traffic stats."""

import asyncio
import logging
import re
from contextlib import suppress
from urllib.parse import urlparse

from github import Github, GithubException

from backend.config import Settings, get_settings
from backend.core.exceptions import GitHubError, ValidationError
from backend.models.intelligence import RepoContext, RepoFile

logger = logging.getLogger("launchkit.github")

SKIP_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    "dist",
    "build",
    ".venv",
    "venv",
}
SKIP_EXTENSIONS = {
    ".lock",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp4",
    ".zip",
    ".tar",
    ".gz",
}
ALWAYS_READ = {
    "README.md",
    "readme.md",
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "Dockerfile",
    ".env.example",
}
ENTRY_POINT_PATTERNS = [
    r"^main\.py$",
    r"^app\.py$",
    r"^server\.py$",
    r"^index\.(js|ts|tsx)$",
    r"^src/main\.(py|js|ts|go|rs)$",
]
PRIORITY_DIRS = ("/src/", "/app/", "/lib/", "/backend/")
MAX_SOURCE_FILES = 10
MAX_CONTENT_CHARS = 100_000
CHUNK_HEAD_LINES = 200
CHUNK_TAIL_LINES = 50


def _parse_github_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise ValidationError("Invalid GitHub URL", f"Cannot parse owner/repo from {url}")
    return parts[0], parts[1].replace(".git", "")


def _should_skip(path: str) -> bool:
    for part in path.split("/"):
        if part in SKIP_DIRS:
            return True
    basename = path.split("/")[-1]
    if basename.endswith(".lock") or basename == "package-lock.json":
        return True
    ext = "." + basename.rsplit(".", 1)[-1] if "." in basename else ""
    return ext.lower() in SKIP_EXTENSIONS


def _is_entry_point(path: str) -> bool:
    filename = path.split("/")[-1]
    return any(re.match(pat, filename) or re.match(pat, path) for pat in ENTRY_POINT_PATTERNS)


def _chunk_content(content: str) -> str:
    lines = content.splitlines()
    if len(lines) <= CHUNK_HEAD_LINES + CHUNK_TAIL_LINES:
        return content
    head = lines[:CHUNK_HEAD_LINES]
    tail = lines[-CHUNK_TAIL_LINES:]
    omitted = len(lines) - CHUNK_HEAD_LINES - CHUNK_TAIL_LINES
    return "\n".join(head) + f"\n\n... [{omitted} lines omitted] ...\n\n" + "\n".join(tail)


class GitHubService:
    """GitHub API wrapper for repo access and publishing."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        token = self.settings.github_token or None
        self._gh = Github(token)

    async def get_repo_context(self, github_url: str) -> RepoContext:
        owner, repo_name = _parse_github_url(github_url)

        def _fetch():
            try:
                repo = self._gh.get_repo(f"{owner}/{repo_name}")
            except GithubException as exc:
                raise GitHubError(
                    f"Cannot access repo {owner}/{repo_name}",
                    str(exc),
                ) from exc

            tree_paths: list[str] = []
            try:
                tree = repo.get_git_tree(repo.default_branch, recursive=True)
                tree_paths = [
                    item.path
                    for item in tree.tree
                    if item.type == "blob" and not _should_skip(item.path)
                ]
            except GithubException:
                contents = repo.get_contents("")
                tree_paths = self._flatten_contents(contents, "")

            selected = self._select_files(tree_paths)
            key_files: list[RepoFile] = []
            total_chars = 0

            for path in selected:
                try:
                    file_content = repo.get_contents(path)
                    if isinstance(file_content, list):
                        continue
                    raw = file_content.decoded_content.decode("utf-8", errors="replace")
                    if total_chars + len(raw) > MAX_CONTENT_CHARS:
                        raw = _chunk_content(raw)
                    total_chars += len(raw)
                    key_files.append(RepoFile(path=path, content=raw, size=len(raw)))
                except (GithubException, UnicodeDecodeError) as exc:
                    logger.warning("Skipping file %s: %s", path, exc)

            languages = {}
            with suppress(GithubException):
                languages = repo.get_languages()

            return RepoContext(
                owner=owner,
                repo=repo_name,
                default_branch=repo.default_branch,
                file_tree=sorted(tree_paths)[:500],
                key_files=key_files,
                languages=languages,
                description=repo.description or "",
                stars=repo.stargazers_count,
                forks=repo.forks_count,
            )

        return await asyncio.to_thread(_fetch)

    def _flatten_contents(self, contents, prefix: str) -> list[str]:
        paths = []
        for item in contents:
            path = f"{prefix}/{item.name}" if prefix else item.name
            if _should_skip(path):
                continue
            if item.type == "dir":
                with suppress(GithubException):
                    paths.extend(self._flatten_contents(item.repo.get_contents(path), path))
            else:
                paths.append(path)
        return paths

    def _select_files(self, paths: list[str]) -> list[str]:
        selected: list[str] = []
        remaining = set(paths)

        for path in paths:
            basename = path.split("/")[-1]
            if basename in ALWAYS_READ or path in ALWAYS_READ:
                selected.append(path)
                remaining.discard(path)

        entry_points = [p for p in paths if _is_entry_point(p)]
        for ep in entry_points:
            if ep not in selected:
                selected.append(ep)
                remaining.discard(ep)

        def priority_key(p: str) -> tuple:
            in_priority = any(d.strip("/") in p.split("/") for d in PRIORITY_DIRS)
            depth = p.count("/")
            return (0 if in_priority else 1, depth, -len(p))

        candidates = sorted(remaining, key=priority_key)
        while len(selected) < MAX_SOURCE_FILES and candidates:
            selected.append(candidates.pop(0))

        return selected[:MAX_SOURCE_FILES]

    async def push_readme(self, github_url: str, content: str, commit_message: str) -> str:
        owner, repo_name = _parse_github_url(github_url)

        def _push():
            try:
                repo = self._gh.get_repo(f"{owner}/{repo_name}")
                try:
                    existing = repo.get_contents("README.md")
                    result = repo.update_file(
                        "README.md",
                        commit_message,
                        content,
                        existing.sha,
                    )
                except GithubException:
                    result = repo.create_file("README.md", commit_message, content)
                return result["commit"].html_url
            except GithubException as exc:
                raise GitHubError("Failed to push README", str(exc)) from exc

        return await asyncio.to_thread(_push)

    async def get_traffic_stats(self, github_url: str) -> dict:
        owner, repo_name = _parse_github_url(github_url)

        def _stats():
            try:
                repo = self._gh.get_repo(f"{owner}/{repo_name}")
                views = repo.get_views_traffic()
                view_count = sum(v.count for v in views.get("views", []))
                return {
                    "stars": repo.stargazers_count,
                    "forks": repo.forks_count,
                    "views_last_14_days": view_count,
                    "clones_last_14_days": sum(
                        c.count for c in repo.get_clones_traffic().get("clones", [])
                    ),
                }
            except GithubException as exc:
                if exc.status == 403:
                    try:
                        repo = self._gh.get_repo(f"{owner}/{repo_name}")
                        return {
                            "stars": repo.stargazers_count,
                            "forks": repo.forks_count,
                            "views_last_14_days": None,
                            "error": "Traffic stats require push access",
                        }
                    except GithubException:
                        pass
                raise GitHubError("Failed to get traffic stats", str(exc)) from exc

        return await asyncio.to_thread(_stats)


def get_github_service(settings: Settings | None = None) -> GitHubService:
    return GitHubService(settings)
