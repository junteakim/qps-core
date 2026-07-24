from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

FORBIDDEN_DIRECTORY_NAMES = {
    ".codex_runtime",
    ".memory",
    "_workspace",
    "archive",
    "attachments",
    "emails",
}
SKIP_DIRECTORY_NAMES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".playwright-cli",
    "__pycache__",
    "build",
    "demo-output",
    "dist",
    "output",
}
FORBIDDEN_SUFFIXES = {
    ".db",
    ".doc",
    ".docx",
    ".eml",
    ".key",
    ".msg",
    ".p12",
    ".pdf",
    ".pem",
    ".pfx",
    ".sqlite",
    ".xls",
    ".xlsx",
    ".zip",
}
FORBIDDEN_CONTENT = (
    "Seoul " + "Machinery",
    "@" + "smc12",
    "Galva" + "tek",
    "CO" + "OEC",
    "EX" + "MAR",
    "HD" + "EC",
    "neo4j://" + "smc12",
)
SECRET_PATTERNS = {
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "gcp_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[0-9A-Za-z]{30,}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "discord_token": re.compile(
        r"\b[A-Za-z0-9_-]{24}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{25,}\b"
    ),
    "email_address": re.compile(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        re.IGNORECASE,
    ),
    "private_ipv4": re.compile(
        r"\b(?:10|127)\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"
        r"|\b192\.168\.\d{1,3}\.\d{1,3}\b"
        r"|\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b"
    ),
}
TEXT_SUFFIXES = {
    "",
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".ttl",
    ".txt",
    ".yaml",
    ".yml",
}


def _git_lines(root: Path, *args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return [line for line in result.stdout.splitlines() if line]


def select_release_files(
    root: Path,
    archive: bool,
) -> tuple[list[Path], list[str], int]:
    issues: list[str] = []
    git_directory = root / ".git"
    if git_directory.exists() and not archive:
        tracked = _git_lines(root, "ls-files")
        if not tracked:
            issues.append("git repository has no tracked release payload")
        for ignored in _git_lines(root, "ls-files", "-ci", "--exclude-standard"):
            issues.append(f"tracked file is ignored: {ignored}")
        return [root / item for item in tracked], issues, len(tracked)

    selected: list[Path] = []
    generated_directories: set[Path] = set()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        skipped = next(
            (part for part in relative.parts if part in SKIP_DIRECTORY_NAMES),
            None,
        )
        if skipped:
            if archive:
                generated_directories.add(
                    Path(*relative.parts[: relative.parts.index(skipped) + 1])
                )
            continue
        if path.is_file():
            selected.append(path)
    for directory in sorted(generated_directories):
        issues.append(f"generated directory in archive payload: {directory}")
    return selected, issues, 0


def verify_files(root: Path, files_to_check: list[Path]) -> list[str]:
    issues: list[str] = []
    forbidden_directories: set[Path] = set()
    for path in sorted(files_to_check):
        if not path.is_file():
            issues.append(f"tracked path is not a file: {path.relative_to(root)}")
            continue
        relative = path.relative_to(root)
        for index, part in enumerate(relative.parts[:-1]):
            if part in FORBIDDEN_DIRECTORY_NAMES:
                forbidden_directories.add(Path(*relative.parts[: index + 1]))
        if (
            path.name == ".env" or path.name.startswith(".env.")
        ) and path.name != ".env.example":
            issues.append(f"forbidden environment file: {relative}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            issues.append(f"forbidden file type: {relative}")
        if path.stat().st_size > 1_000_000:
            issues.append(f"file exceeds 1 MB: {relative}")
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in FORBIDDEN_CONTENT:
            if token.lower() in text.lower():
                issues.append(f"forbidden internal token in {relative}: {token}")
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                issues.append(f"secret pattern in {relative}: {name}")
    for directory in sorted(forbidden_directories):
        issues.append(f"forbidden directory: {directory}")
    return issues


def verify(root: Path, archive: bool = False) -> list[str]:
    files_to_check, selection_issues, _ = select_release_files(root, archive)
    return selection_issues + verify_files(root, files_to_check)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path("."))
    parser.add_argument("--archive", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    files_to_check, selection_issues, tracked_count = select_release_files(
        root,
        args.archive,
    )
    issues = selection_issues + verify_files(root, files_to_check)
    if args.archive:
        payload_mode = "archive"
    elif (root / ".git").exists():
        payload_mode = "git-tracked"
    else:
        payload_mode = "working-tree"
    print(
        json.dumps(
            {
                "verdict": "PASS" if not issues else "FAIL",
                "payload_mode": payload_mode,
                "files_checked": len(files_to_check),
                "tracked_files": tracked_count,
                "issues": issues,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
