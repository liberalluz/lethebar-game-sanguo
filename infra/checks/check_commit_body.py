#!/usr/bin/env python3
"""Fail when a new commit does not say why it exists or which batch it serves.

Two lines are required in every commit body this branch adds:

    Why: <one or more lines explaining the reason for the change>
    Batch: B<n>   (or: Batch: none)

The check looks at `base..HEAD`, so merged history is never rewritten by it: a
commit that is already on `main` is not examined. The subject line is not
checked again here; `docs/specs/git-conventions.md` §2 covers its shape and the
review covers its quality.

`Why:` must be followed by non-empty text, either on the same line or in the
lines up to the next `Key:` line. `Batch:` accepts `B<n>`, `B<n><letter>`
(`B5a`) or `none`.

The body is plain text. A commit message is never rendered, so backticks and
bold markers reach the reader as characters — `0bf59cd` carried ten backticks
until it was amended. Markdown is therefore refused here, with the reason in
`docs/specs/git-conventions.md` §2.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SEPARATOR = "\x1f"
BATCH_VALUE = re.compile(r"^(B\d+[a-z]?|none)$")
FENCE = re.compile(r"^```")
BACKTICK = re.compile(r"`")
BOLD = re.compile(r"\*\*[^*]+\*\*")
UNDERSCORE = re.compile(r"(?<![A-Za-z0-9_])__[^_]+__(?![A-Za-z0-9_])")


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or " ".join(args))
    return result.stdout


def base_ref() -> str | None:
    for candidate in ("origin/main", "main"):
        try:
            git("rev-parse", "--verify", "--quiet", candidate)
        except RuntimeError:
            continue
        return candidate
    return None


def field(body: str, name: str) -> str:
    """Return the text that follows `Name:` up to the next `Key:` line."""
    lines = body.splitlines()
    collected: list[str] = []
    inside = False
    in_fence = False
    for line in lines:
        if FENCE.match(line):
            in_fence = not in_fence
        if not in_fence and re.match(rf"^{name}:\s?", line):
            inside = True
            collected.append(line.split(":", 1)[1].strip())
            continue
        if inside:
            if not in_fence and re.match(r"^[A-Za-z][A-Za-z-]*:", line):
                break
            collected.append(line.strip())
    return " ".join(part for part in collected if part).strip()


def _markdown(body: str, kind: str) -> bool:
    """True when the body uses that markdown marker outside a fenced block.

    A fenced block is data — a pasted log or a diff — and is left alone; the
    prose around it is what a reader takes as the reason for the commit.
    """
    outside: list[str] = []
    in_fence = False
    for line in body.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            outside.append(line)
    prose = "\n".join(outside)
    if kind == "backtick":
        return bool(BACKTICK.search(prose))
    if kind == "bold":
        return bool(BOLD.search(prose))
    return bool(UNDERSCORE.search(prose))


def inspect(sha: str, body: str) -> list[str]:
    """Every problem with one commit message, in the wording the gate uses."""
    details: list[str] = []
    subject = body.splitlines()[0] if body.splitlines() else ""
    if not field(body, "Why"):
        details.append(f"{sha[:8]} {subject}: missing 'Why:'")
    batch = field(body, "Batch")
    if not batch:
        details.append(
            f"{sha[:8]} {subject}: missing 'Batch:' (write 'Batch: none' when there is no card)"
        )
    elif not BATCH_VALUE.match(batch.split()[0]):
        details.append(f"{sha[:8]} {subject}: 'Batch: {batch}' should be B<n>, B<n><letter>, or none")
    for mark in ("backtick", "bold", "underscore-bold"):
        if _markdown(body, mark):
            details.append(
                f"{sha[:8]} {subject}: the body carries {mark} markup; a commit message is plain text"
            )
    return details


def check_one(ref: str) -> int:
    """Judge one commit, whatever branch it sits on.

    The range mode below can only see `origin/main..HEAD`, so a message that a
    squash merge created is invisible to it: the commit lands on the default
    branch and no branch is ahead of it. That is how `63862c7` carried ten
    backticks and an 880-character line while every gate stayed green.
    """
    try:
        sha = git("rev-parse", ref).strip()
        body = git("show", "-s", "--format=%B", sha)
    except RuntimeError as error:
        print(f"[commit-body] cannot read {ref}: {error}")
        return 1
    problems = inspect(sha, body)
    if problems:
        for problem in problems:
            print(f"[commit-body] {problem}")
        print("[commit-body] see docs/specs/git-conventions.md §2")
        return 1
    print(f"[commit-body] {sha[:8]} carries Why: and Batch:")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the message of a commit.")
    parser.add_argument(
        "--ref",
        help="judge this commit alone, for example origin/main after a squash merge",
    )
    args = parser.parse_args(argv)
    if args.ref:
        return check_one(args.ref)

    base = base_ref()
    if base is None:
        print("[commit-body] no main branch to compare against; nothing to check")
        return 0

    try:
        raw = git("log", f"--format=%H{SEPARATOR}%B{SEPARATOR}", f"{base}..HEAD")
    except RuntimeError as error:
        print(f"[commit-body] cannot read history: {error}")
        return 1

    entries = [chunk for chunk in raw.split(SEPARATOR) if chunk.strip()]
    commits: list[tuple[str, str]] = []
    for index in range(0, len(entries) - 1, 2):
        commits.append((entries[index].strip(), entries[index + 1]))

    if not commits:
        print(f"[commit-body] no new commit against {base}; nothing to check")
        return 0

    problems: list[str] = []
    for sha, body in commits:
        problems.extend(inspect(sha, body))

    if problems:
        for problem in problems:
            print(f"[commit-body] {problem}")
        print("[commit-body] see docs/specs/git-conventions.md §2")
        return 1

    print(f"[commit-body] {len(commits)} commit(s) carry Why: and Batch:")
    return 0


if __name__ == "__main__":
    sys.exit(main())
