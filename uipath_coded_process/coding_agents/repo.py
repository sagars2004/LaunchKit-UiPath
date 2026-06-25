"""Local repository preparation for coding agent analysis."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

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
    re.compile(r"^main\.py$"),
    re.compile(r"^app\.py$"),
    re.compile(r"^server\.py$"),
    re.compile(r"^index\.(js|ts|tsx)$"),
    re.compile(r"^src/main\.(py|js|ts|go|rs)$"),
]
PRIORITY_DIRS = ("/src/", "/app/", "/lib/", "/backend/")
MAX_SOURCE_FILES = 10
MAX_CONTENT_CHARS = 100_000
CHUNK_HEAD_LINES = 200
CHUNK_TAIL_LINES = 50


@dataclass
class RepoFile:
    path: str
    content: str
    size: int = 0


@dataclass
class LocalRepoContext:
    owner: str
    repo: str
    default_branch: str
    file_tree: list[str]
    key_files: list[RepoFile]
    languages: dict[str, int]
    description: str
    stars: int
    forks: int

    def to_dict(self) -> dict:
        return {
            "owner": self.owner,
            "repo": self.repo,
            "default_branch": self.default_branch,
            "file_tree": self.file_tree,
            "key_files": [
                {"path": f.path, "content": f.content, "size": f.size} for f in self.key_files
            ],
            "languages": self.languages,
            "description": self.description,
            "stars": self.stars,
            "forks": self.forks,
        }


def parse_github_url(url: str) -> tuple[str, str]:
    cleaned = url.rstrip("/").replace(".git", "")
    parts = cleaned.split("github.com/")[-1].split("/")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse owner/repo from {url}")
    return parts[0], parts[1]


def _should_skip(path: str) -> bool:
    for part in path.split("/"):
        if part in SKIP_DIRS:
            return True
    return Path(path).suffix.lower() in SKIP_EXTENSIONS


def _truncate_content(content: str) -> str:
    if len(content) <= MAX_CONTENT_CHARS:
        return content
    lines = content.splitlines()
    if len(lines) <= CHUNK_HEAD_LINES + CHUNK_TAIL_LINES:
        return content[:MAX_CONTENT_CHARS]
    head = "\n".join(lines[:CHUNK_HEAD_LINES])
    tail = "\n".join(lines[-CHUNK_TAIL_LINES:])
    return f"{head}\n\n... [truncated] ...\n\n{tail}"


def _score_path(path: str) -> int:
    basename = path.split("/")[-1]
    if basename in ALWAYS_READ:
        return 100
    for pattern in ENTRY_POINT_PATTERNS:
        if pattern.search(basename):
            return 90
    for marker in PRIORITY_DIRS:
        if marker in f"/{path}":
            return 70
    if path.endswith((".py", ".ts", ".tsx", ".js", ".go", ".rs")):
        return 50
    return 10


def collect_repo_context(repo_path: Path, github_url: str) -> LocalRepoContext:
    owner, repo = parse_github_url(github_url)
    file_tree: list[str] = []
    candidates: list[tuple[int, str, Path]] = []

    for path in sorted(repo_path.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_path).as_posix()
        if _should_skip(rel):
            continue
        file_tree.append(rel)
        score = _score_path(rel)
        if score >= 50 or path.name in ALWAYS_READ:
            candidates.append((score, rel, path))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    key_files: list[RepoFile] = []
    for _, rel, path in candidates[:MAX_SOURCE_FILES]:
        try:
            content = _truncate_content(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        key_files.append(RepoFile(path=rel, content=content, size=path.stat().st_size))

    languages: dict[str, int] = {}
    for rel in file_tree:
        ext = Path(rel).suffix.lower()
        if ext:
            languages[ext] = languages.get(ext, 0) + 1

    return LocalRepoContext(
        owner=owner,
        repo=repo,
        default_branch="main",
        file_tree=file_tree,
        key_files=key_files,
        languages=languages,
        description="",
        stars=0,
        forks=0,
    )


def format_key_files(key_files: list[RepoFile]) -> str:
    return "\n\n---\n\n".join(
        f"### {f.path}\n```\n{f.content}\n```" for f in key_files
    )


def clone_repo(github_url: str, work_dir: str | None = None) -> tuple[Path, bool]:
    """Clone repo to a temp or provided directory. Returns (path, should_cleanup)."""
    if work_dir:
        target = Path(work_dir)
        target.mkdir(parents=True, exist_ok=True)
        if any(target.iterdir()):
            return target, False
        subprocess.run(
            ["git", "clone", "--depth", "1", github_url, str(target)],
            check=True,
            capture_output=True,
            text=True,
        )
        return target, False

    tmp = tempfile.mkdtemp(prefix="launchkit-repo-")
    subprocess.run(
        ["git", "clone", "--depth", "1", github_url, tmp],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(tmp), True


def cleanup_repo(path: Path, should_cleanup: bool) -> None:
    if should_cleanup and path.exists():
        shutil.rmtree(path, ignore_errors=True)
