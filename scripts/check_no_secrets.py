"""Fail safely when common credential signatures appear in tracked Git content.

The guard deliberately reports only a path, line number and rule name; it
never echoes a possible secret. It complements, rather than replaces, secret
management and GitHub's own secret scanning.
"""

from __future__ import annotations

import argparse
from pathlib import PurePosixPath
import re
import subprocess
import sys
from typing import Iterable


RULES = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "aws-access-key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github-token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "gitlab-token": re.compile(r"glpat-[A-Za-z0-9_-]{20,}"),
    "slack-token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "google-api-key": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "stripe-live-key": re.compile(r"[sr]k_live_[0-9A-Za-z]{16,}"),
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
}
BINARY_SUFFIXES = {".joblib", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".sqlite3", ".woff", ".woff2"}


def _git(*args: str) -> str:
    return subprocess.check_output(("git", *args), text=True, stderr=subprocess.DEVNULL)


def _repository_paths() -> list[str]:
    """Return committed files plus publishable, non-ignored local additions."""

    paths = _git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()
    return [path for path in paths if path]


def _is_binary_path(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() in BINARY_SUFFIXES


def _find_in_lines(path: str, lines: Iterable[str]) -> set[str]:
    findings: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        for name, pattern in RULES.items():
            if pattern.search(line):
                findings.add(f"{path}:{line_number} {name}")
    return findings


def scan_worktree(paths: Iterable[str]) -> set[str]:
    findings: set[str] = set()
    for path in paths:
        if _is_binary_path(path):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as source:
                findings.update(_find_in_lines(path, source))
        except OSError as exc:
            findings.add(f"{path}:0 unreadable-tracked-file ({exc.__class__.__name__})")
    return findings


def scan_history() -> set[str]:
    findings: set[str] = set()
    for revision in _git("rev-list", "--all").splitlines():
        for name, pattern in RULES.items():
            result = subprocess.run(
                ("git", "grep", "-n", "-I", "-E", "--", pattern.pattern, revision),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            for match in result.stdout.splitlines():
                parts = match.split(":", 3)
                if len(parts) >= 3 and parts[2].isdigit():
                    findings.add(f"{parts[1]}:{parts[2]} {name}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true", help="also scan reachable Git history")
    args = parser.parse_args()

    paths = _repository_paths()
    forbidden_env_files = [path for path in paths if PurePosixPath(path).name == ".env"]
    findings = scan_worktree(paths)
    findings.update(f"{path}:0 tracked-env-file" for path in forbidden_env_files)
    if args.history:
        findings.update(scan_history())

    if findings:
        print("Secret guard failed; rotate any exposed credential and remove it from Git history.", file=sys.stderr)
        for finding in sorted(findings):
            print(f"- {finding}", file=sys.stderr)
        return 1
    print("Secret guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
