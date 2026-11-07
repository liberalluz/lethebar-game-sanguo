#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Project-local batch execution skeleton.

The tool is deliberately stack-agnostic. It owns a small state machine:

    plan -> approve -> start -> check -> pr -> merge

Checks and PR provider commands come from ``infra/tool/batch/config.json``. The
defaults only do local work; a project can add its own commands without
changing this file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[3]
STATE_DIR = ".batch"
CONFIG_REL = Path("infra") / "tool" / "batch" / "config.json"
SCAFFOLD_REL = Path(".nebula-scaffold.json")
DEFAULT_CONFIG: dict[str, Any] = {
    "base": "main",
    "branch_prefix": "batch/",
    "docs_root": "",
    "scope": {"ignore": [], "generated": []},
    "checks": [],
    "pr_create": [],
    "translate": [],
    "merge": [],
}
ID_RE = re.compile(r"^(?:B[0-9]+[a-z]?|[0-9]{8}-[0-9a-f]{6})$")
DATED_ID_RE = re.compile(r"^[0-9]{8}-[0-9a-f]{6}$")
CARD_ID_RE = re.compile(r"^B[0-9]+[a-z]?$")
CARD_MARKER_RE = re.compile(r"<!--\s*batch-card\s*:\s*v1\s*-->")
CARD_JSON_RE = re.compile(r"```json[ \t]*\r?\n(.*?)\r?\n```", re.DOTALL)
CARD_TYPES = {"feat", "fix", "docs", "test", "refactor", "chore", "ci"}
DOCS_PROCESS = "process"
DOCS_SDP = "sdp.md"
DOCS_BATCHES = "batches"
DOCS_RECORDS = "records"
RECORD_ID_RE = re.compile(r"(?<![A-Za-z0-9])B[0-9]+[a-z]?(?![A-Za-z0-9])")
STAGE_SKILLS = {
    "nebula-project",
    "nebula-bootstrap",
    "nebula-requirements",
    "nebula-design",
    "nebula-verification",
    "nebula-planning",
    "nebula-delivery",
}
SKILL_ROOTS = (
    ".agents/skills",
    ".claude/skills",
    ".codex/skills",
    ".codebuddy/skills",
    ".workbuddy/skills",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def run_git(root: Path, args: Sequence[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def git_required(root: Path) -> None:
    code, _, err = run_git(root, ["rev-parse", "--show-toplevel"])
    if code != 0:
        raise SystemExit(f"not a git repository: {root} ({err})")


def resolve_commit(root: Path, ref: str) -> str:
    """Resolve a branch or tag to the commit it points at, or return ""."""
    code, out, _ = run_git(root, ["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
    return out if code == 0 else ""


def config_path(root: Path) -> Path:
    return root / CONFIG_REL


def load_config(root: Path) -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    config["scope"] = dict(DEFAULT_CONFIG["scope"])
    raw = load_json(config_path(root))
    if raw is not None:
        for key in DEFAULT_CONFIG:
            if key in raw:
                config[key] = raw[key]
    scope = config.get("scope")
    if not isinstance(scope, dict):
        raise SystemExit("config.scope must be an object")
    config["scope"] = dict(DEFAULT_CONFIG["scope"])
    for key in ("ignore", "generated"):
        value = scope.get(key, [])
        if not isinstance(value, list):
            raise SystemExit(f"config.scope.{key} must be a list")
        config["scope"][key] = [str(item) for item in value]
    if not isinstance(config.get("checks"), list):
        raise SystemExit("config.checks must be a list")
    for key in ("pr_create", "translate", "merge"):
        value = config.get(key)
        if value and not isinstance(value, list):
            raise SystemExit(f"config.{key} must be a command array")
    return config


def state_root(root: Path) -> Path:
    return root / STATE_DIR


def batch_dir(root: Path, batch_id: str) -> Path:
    return state_root(root) / batch_id


def active_id(root: Path) -> str | None:
    path = state_root(root) / "active"
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def clear_active(root: Path) -> None:
    path = state_root(root) / "active"
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def set_active(root: Path, batch_id: str) -> None:
    write_text(state_root(root) / "active", batch_id + "\n")


def resolve_id(root: Path, value: str | None) -> str:
    if value:
        if not ID_RE.fullmatch(value):
            raise SystemExit(f"invalid batch id: {value}")
        if not batch_dir(root, value).is_dir():
            raise SystemExit(f"batch not found: {value}")
        return value
    active = active_id(root)
    if active:
        return active
    if not state_root(root).is_dir():
        raise SystemExit("no batch found; run 'plan' first")
    candidates = sorted(
        (path.name for path in state_root(root).iterdir() if path.is_dir()),
        key=batch_sort_key,
    )
    if not candidates:
        raise SystemExit("no batch found; run 'plan' first")
    if len(candidates) > 1:
        raise SystemExit(
            f"multiple batches found ({', '.join(candidates)}); "
            "pass the batch id explicitly"
        )
    return candidates[0]


def batch_sort_key(value: str) -> tuple[int, int, str]:
    match = re.fullmatch(r"B([0-9]+)([a-z]?)", value)
    if match:
        return (0, int(match.group(1)), match.group(2))
    return (1, 0, value)


def branch_slug(value: str, limit: int = 40) -> str:
    """Turn a goal into a branch-name slug; empty when nothing ASCII is left."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:limit].strip("-")


def new_id(root: Path) -> str:
    prefix = datetime.now().strftime("%Y%m%d")
    for _ in range(50):
        candidate = f"{prefix}-{secrets.token_hex(3)}"
        if not batch_dir(root, candidate).exists():
            return candidate
    raise SystemExit("could not allocate a batch id")


def parse_list(values: list[str] | None, default: list[str]) -> list[str]:
    out: list[str] = []
    for value in values or []:
        for item in value.replace(";", ",").split(","):
            item = item.strip()
            if item and item not in out:
                out.append(item)
    return out or default


def card_hash(card: dict[str, Any]) -> str:
    canonical = json.dumps(card, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_card(root: Path, batch_id: str) -> dict[str, Any]:
    card = load_json(batch_dir(root, batch_id) / "card.json")
    if card is None:
        raise SystemExit(f"card not found: {batch_id}")
    return card


def source_relative(root: Path, path: Path) -> str:
    return Path(os.path.relpath(path, root)).as_posix()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def card_source_path(root: Path, card: dict[str, Any]) -> Path | None:
    source = card.get("source")
    if not source:
        return None
    return (root / str(source)).resolve()


def source_is_current(root: Path, card: dict[str, Any]) -> tuple[bool, str]:
    if card.get("legacy"):
        return False, "legacy card is read-only"
    path = card_source_path(root, card)
    if path is None:
        return True, ""
    if not path.is_file():
        return False, f"card source is missing: {card.get('source')}"
    expected = str(card.get("source_sha256", ""))
    if file_sha256(path) != expected:
        return False, "card source changed; re-plan and re-approve"
    return True, ""


def validate_planned_card(card: dict[str, Any], path: Path | None = None) -> None:
    def fail(message: str) -> None:
        raise ValueError(message)

    if not isinstance(card, dict):
        fail("card must be a JSON object")
    if card.get("legacy"):
        fail("legacy cards cannot be planned from a card source")
    required = (
        "id",
        "goal",
        "type",
        "base",
        "size_budget",
        "allowed",
        "acceptance",
        "changelog",
        "skills",
    )
    missing = [key for key in required if key not in card]
    if missing:
        fail(f"missing field(s): {', '.join(missing)}")

    card_id = card.get("id")
    if not isinstance(card_id, str) or not CARD_ID_RE.fullmatch(card_id):
        fail("id must be B followed by digits")
    if path is not None and path.stem != card_id:
        fail(f"card id {card_id} does not match file stem {path.stem}")

    if not isinstance(card.get("goal"), str) or not card["goal"].strip():
        fail("goal must be a non-empty string")
    if card.get("type") not in CARD_TYPES:
        fail("type must be feat, fix, process, or docs")
    base = card.get("base")
    if not isinstance(base, str) or not base.strip() or any(ch.isspace() for ch in base):
        fail("base must be a non-empty branch name")

    budget = card.get("size_budget")
    if type(budget) is not int or budget < 1:
        fail("size_budget must be an integer greater than zero")

    for key, allow_empty in (("allowed", False), ("forbidden", True)):
        if key not in card and key == "forbidden":
            continue
        value = card.get(key)
        if not isinstance(value, list) or (not allow_empty and not value):
            fail(f"{key} must be a non-empty array")
        if not all(isinstance(item, str) and item.strip() for item in value):
            fail(f"{key} must contain non-empty strings")

    for key in ("acceptance", "changelog"):
        value = card.get(key)
        if not isinstance(value, list) or (key == "acceptance" and not value):
            fail(f"{key} must be a non-empty array")
        if not all(isinstance(item, str) and item.strip() for item in value):
            fail(f"{key} must contain non-empty strings")

    skills = card.get("skills")
    if not isinstance(skills, list) or len(skills) > 4:
        fail("skills must be an array with at most four entries")
    for item in skills:
        if not isinstance(item, dict):
            fail("each skill must be an object")
        skill_id = item.get("id")
        if not isinstance(skill_id, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9-]*", skill_id
        ):
            fail("skill id must be lower-case kebab-case")
        if skill_id == "using-agent-skills":
            fail("using-agent-skills is never installable")
        if skill_id in STAGE_SKILLS:
            fail(f"stage skill {skill_id} is not declared in a batch card")
        if not isinstance(item.get("required"), bool):
            fail(f"skill {skill_id}: required must be a boolean")
        if "reason" in item and not isinstance(item["reason"], str):
            fail(f"skill {skill_id}: reason must be a string")


def read_planned_card(path: Path) -> tuple[dict[str, Any], bytes]:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"card is not UTF-8: {exc}") from exc
    marker = CARD_MARKER_RE.search(text)
    if marker is None:
        raise ValueError("missing <!-- batch-card: v1 --> marker")
    block = CARD_JSON_RE.search(text, marker.end())
    if block is None:
        raise ValueError("missing fenced json block after the card marker")
    try:
        card = json.loads(block.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid card JSON: {exc}") from exc
    validate_planned_card(card, path)
    return card, data


def docs_root_from_card(source: Path) -> Path | None:
    """Return the docs root for a card at ``<docs>/process/batches/B<n>.md``."""
    parent = source.parent
    if parent.name == DOCS_BATCHES and parent.parent.name == DOCS_PROCESS:
        return parent.parent.parent
    return None


def configured_docs_root(root: Path, config: dict[str, Any]) -> Path | None:
    value = str(config.get("docs_root", "") or "").strip()
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def sdp_batch_ids(sdp: Path) -> set[str]:
    """Read the ``| Batch |`` table and return the ids it lists."""
    lines = sdp.read_text(encoding="utf-8", errors="replace").splitlines()
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if line.strip().startswith("| Batch |")
        ),
        None,
    )
    if start is None:
        return set()
    ids: set[str] = set()
    for line in lines[start + 1:]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells:
            continue
        ident = cells[0].strip("` ")
        if CARD_ID_RE.fullmatch(ident):
            ids.add(ident)
    return ids


def docs_batch_ids(docs_root: Path, exclude: Path | None = None) -> dict[str, Path]:
    """Map every id already used in the docs repo to the path that uses it."""
    taken: dict[str, Path] = {}
    batches = docs_root / DOCS_PROCESS / DOCS_BATCHES
    if batches.is_dir():
        for path in sorted(batches.glob("B*.md")):
            match = re.fullmatch(r"(B[0-9]+[a-z]?)\.md", path.name)
            if match is None:
                continue
            if exclude is not None and path.resolve() == exclude:
                continue
            taken.setdefault(match.group(1), path)
    records = docs_root / DOCS_RECORDS
    if records.is_dir():
        for path in sorted(records.rglob("*")):
            match = RECORD_ID_RE.search(path.name)
            if match:
                taken.setdefault(match.group(0), path)
    return taken


def next_batch_id(ids: set[str]) -> str:
    highest = 0
    for value in ids:
        match = re.fullmatch(r"B([0-9]+)[a-z]?", value)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"B{highest + 1}"


def duplicate_id_error(
    root: Path, card: dict[str, Any], config: dict[str, Any], batch_id: str
) -> str:
    """Return an error when another card or record already claims this id."""
    source = card_source_path(root, card)
    docs_root = configured_docs_root(root, config)
    if docs_root is None and source is not None:
        docs_root = docs_root_from_card(source)
    if docs_root is None or not docs_root.is_dir():
        return ""
    taken = docs_batch_ids(docs_root, exclude=source)
    if batch_id in taken:
        return f"batch id {batch_id} is already used by {taken[batch_id]}"
    return ""


def read_state(root: Path, batch_id: str) -> dict[str, Any]:
    state = load_json(batch_dir(root, batch_id) / "state.json")
    if state is None:
        raise SystemExit(f"batch not started: {batch_id}")
    return state


def glob_regex(pattern: str) -> re.Pattern[str]:
    i = 0
    out = ""
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile("^" + out + "$")


def matches(path: str, patterns: Sequence[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(glob_regex(pattern).fullmatch(normalized) for pattern in patterns)


def changed_paths(root: Path, base: str, config: dict[str, Any]) -> list[str]:
    paths: set[str] = set()
    for args in (
        ["diff", "--name-only", f"{base}...HEAD"],
        ["diff", "--name-only", "HEAD"],
        ["ls-files", "--others", "--exclude-standard"],
    ):
        code, out, _ = run_git(root, args)
        if code != 0:
            continue
        paths.update(line.strip() for line in out.splitlines() if line.strip())

    ignored = list(DEFAULT_CONFIG["scope"]["ignore"])
    ignored.extend(DEFAULT_CONFIG["scope"]["generated"])
    scope = config.get("scope")
    if isinstance(scope, dict):
        ignored.extend(str(item) for item in scope.get("ignore", []))
        ignored.extend(str(item) for item in scope.get("generated", []))
    ignored.extend([".batch/**", ".batch"])
    return sorted(
        path
        for path in paths
        if not matches(path, ignored) and path != ".batch"
    )


def check_scope(
    root: Path, card: dict[str, Any], base: str, config: dict[str, Any]
) -> tuple[list[str], list[str]]:
    allowed = [str(item) for item in card.get("allowed", [])] or ["**"]
    forbidden = [str(item) for item in card.get("forbidden", [])]
    changed = changed_paths(root, base, config)
    violations: list[str] = []
    for path in changed:
        if matches(path, forbidden):
            violations.append(f"forbidden: {path}")
        elif not matches(path, allowed):
            violations.append(f"out of scope: {path}")
    return changed, violations


def installed_skill(root: Path, skill_id: str) -> Path | None:
    for relative in SKILL_ROOTS:
        path = root / relative / skill_id / "SKILL.md"
        if path.is_file():
            return path
    return None


def check_skills(root: Path, card: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    violations: list[str] = []
    found: dict[str, str] = {}
    for item in card.get("skills", []):
        skill_id = str(item.get("id", ""))
        path = installed_skill(root, skill_id)
        if path is None:
            violations.append(f"skill {skill_id}: not installed in this project")
        else:
            found[skill_id] = source_relative(root, path)
    return violations, found


def diff_stats(
    root: Path, base: str, changed: Sequence[str]
) -> tuple[int, int, int]:
    code, out, err = run_git(root, ["diff", "--numstat", "--no-renames", base])
    if code != 0:
        raise SystemExit(f"could not count batch diff: {err}")
    allowed = set(changed)
    added = 0
    deleted = 0
    binary = 0
    seen: set[str] = set()
    for line in out.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        raw_added, raw_deleted, path = parts
        path = path.replace("\\", "/")
        if path not in allowed:
            continue
        seen.add(path)
        if raw_added == "-" or raw_deleted == "-":
            binary += 1
            continue
        added += int(raw_added)
        deleted += int(raw_deleted)

    for path in changed:
        if path in seen:
            continue
        target = root / path
        if not target.is_file():
            continue
        data = target.read_bytes()
        if b"\0" in data:
            binary += 1
            continue
        added += data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
    return added, deleted, binary


def check_budget(
    root: Path, card: dict[str, Any], base: str, changed: Sequence[str]
) -> tuple[int, int, int, str | None]:
    budget = card.get("size_budget")
    if type(budget) is not int or budget < 1:
        return 0, 0, 0, None
    added, deleted, binary = diff_stats(root, base, changed)
    total = added + deleted
    if total > budget:
        message = f"budget: {total} changed lines exceeds {budget}"
        if binary:
            message += f" ({binary} binary file(s) not counted)"
        return added, deleted, binary, message
    return added, deleted, binary, None


def check_changelog(
    root: Path, card: dict[str, Any], changed: Sequence[str]
) -> tuple[list[str], list[str]]:
    violations: list[str] = []
    warnings: list[str] = []
    card_type = str(card.get("type", ""))
    paths = [str(item) for item in card.get("changelog", [])]
    uses_changelog = (root / "changelog.d").is_dir()
    if card_type in {"feat", "fix"} and uses_changelog and not paths:
        violations.append("changelog: feat/fix must declare at least one fragment")
    if card_type in {"feat", "fix"} and not uses_changelog:
        warnings.append("changelog.d is absent; no fragment was required")

    changed_set = set(changed)
    for raw in paths:
        path = Path(raw)
        normalized = path.as_posix()
        if path.is_absolute() or ".." in path.parts:
            violations.append(f"changelog: path must stay inside the project: {raw}")
            continue
        if not normalized.startswith("changelog.d/"):
            violations.append(f"changelog: fragment must live under changelog.d/: {raw}")
            continue
        target = root / normalized
        if not target.is_file():
            violations.append(f"changelog: missing fragment: {raw}")
            continue
        if normalized not in changed_set:
            violations.append(f"changelog: fragment was not changed by this batch: {raw}")
            continue
        try:
            content = target.read_text(encoding="utf-8").strip()
        except UnicodeDecodeError:
            violations.append(f"changelog: fragment is not UTF-8: {raw}")
            continue
        if not content:
            violations.append(f"changelog: empty fragment: {raw}")
    return violations, warnings


def append_evidence(root: Path, batch_id: str, line: str) -> None:
    path = batch_dir(root, batch_id) / "evidence.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"[{utc_now()}] {line}\n")


def command_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return shlex.split(value)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise SystemExit("command must be a string or an array of strings")


def run_hook(
    root: Path, command: Sequence[str], values: dict[str, str]
) -> tuple[int, str, str]:
    merged = {"pr": "", **values}
    resolved = [
        re.sub(
            r"\{([a-z]+)\}",
            lambda match: str(merged.get(match.group(1), match.group(0))),
            item,
        )
        for item in command
    ]
    proc = subprocess.run(
        resolved,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def run_checks(
    root: Path, batch_id: str, config: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for item in config.get("checks", []):
        if not isinstance(item, dict):
            raise SystemExit("each check must be an object")
        name = str(item.get("name", "")).strip()
        if not name or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise SystemExit(f"invalid check name: {name!r}")
        command = command_list(item.get("command"))
        timeout = int(item.get("timeout", 600))
        raw_cwd = str(item.get("cwd", ".") or ".").strip() or "."
        check_cwd = (root / raw_cwd).resolve()
        try:
            check_cwd.relative_to(root.resolve())
        except ValueError:
            raise SystemExit(f"check {name}: cwd escapes project root: {raw_cwd}")
        try:
            proc = subprocess.run(
                command,
                cwd=check_cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            status = "pass" if proc.returncode == 0 else "fail"
            output = (proc.stdout + proc.stderr).strip()
            code = proc.returncode
        except subprocess.TimeoutExpired:
            status, output, code = "fail", f"timeout after {timeout}s", 124
        log = batch_dir(root, batch_id) / "evidence" / f"{name}.log"
        write_text(log, output + ("\n" if output else ""))
        results[name] = {"status": status, "exit": code, "at": utc_now()}
        append_evidence(root, batch_id, f"check {name}: {status.upper()} (exit {code})")
        print(f"[{status}] check {name}")
        if status == "fail":
            print(output[-2000:], file=sys.stderr)
    return results


def print_status(root: Path, batch_id: str, as_json: bool) -> None:
    card = read_card(root, batch_id)
    state = load_json(batch_dir(root, batch_id) / "state.json") or {}
    status = state.get("status") or ("legacy" if card.get("legacy") else "planned")
    payload = {
        "id": batch_id,
        "goal": card.get("goal"),
        "card_hash": card_hash(card)[:8],
        "status": status,
        "base": state.get("base"),
        "branch": state.get("branch"),
        "checks": state.get("checks", {}),
        "active": active_id(root) == batch_id,
        "legacy": bool(card.get("legacy")),
        "source": card.get("source"),
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"batch:  {batch_id}")
    print(f"goal:   {payload['goal'] or ''}")
    print(f"hash:   {payload['card_hash']}")
    print(f"status: {payload['status']}")
    if payload["base"]:
        print(f"base:   {payload['base']}")
    if payload["branch"]:
        print(f"branch: {payload['branch']}")
    if payload["source"]:
        print(f"source: {payload['source']}")
    if payload["checks"]:
        for name, result in payload["checks"].items():
            print(f"check:  {name} = {result.get('status')}")
    print(f"active: {'yes' if payload['active'] else 'no'}")


def cmd_plan(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    git_required(root)

    if args.source:
        extra = args.goal or args.allowed or args.forbidden or args.exit_criterion
        if extra:
            print(
                "--from cannot be combined with --goal, --allowed, --forbidden, "
                "or --exit-criterion",
                file=sys.stderr,
            )
            return 2
        source = Path(args.source)
        source = source if source.is_absolute() else root / source
        source = source.resolve()
        if not source.is_file():
            print(f"card source not found: {source}", file=sys.stderr)
            return 2
        try:
            card, raw = read_planned_card(source)
        except ValueError as exc:
            print(f"invalid card: {exc}", file=sys.stderr)
            return 2
        batch_id = card["id"]
        if args.id and args.id != batch_id:
            print(f"--id {args.id} does not match card id {batch_id}", file=sys.stderr)
            return 2
        target = batch_dir(root, batch_id)
        if target.exists():
            print(f"batch already exists: {batch_id}", file=sys.stderr)
            return 1
        config = load_config(root)
        docs_root = configured_docs_root(root, config) or docs_root_from_card(source)
        if docs_root is None:
            print(
                "warning: docs repo not found; skipped SDP and duplicate-id checks",
                file=sys.stderr,
            )
        else:
            sdp = docs_root / DOCS_PROCESS / DOCS_SDP
            if not sdp.is_file():
                print(f"SDP not found: {sdp}", file=sys.stderr)
                return 2
            planned = sdp_batch_ids(sdp)
            if not planned:
                print(f"no '| Batch |' table in {sdp}", file=sys.stderr)
                return 2
            if batch_id not in planned:
                print(
                    f"card {batch_id} is not in the SDP batch table: {sdp}",
                    file=sys.stderr,
                )
                return 1
            taken = docs_batch_ids(docs_root, exclude=source)
            if batch_id in taken:
                print(
                    f"batch id {batch_id} is already used by {taken[batch_id]}",
                    file=sys.stderr,
                )
                print(
                    f"next unused id: {next_batch_id(planned | set(taken))}",
                    file=sys.stderr,
                )
                return 1
        snapshot = dict(card)
        snapshot["source"] = source_relative(root, source)
        snapshot["source_sha256"] = hashlib.sha256(raw).hexdigest()
        write_json(target / "card.json", snapshot)
        print(f"planned {batch_id} from {snapshot['source']}")
        print(f"hash: {card_hash(snapshot)[:8]}")
        return 0

    if not args.goal:
        print("plan needs --from or --goal", file=sys.stderr)
        return 2
    if args.id and CARD_ID_RE.fullmatch(args.id):
        print("planned B<n> cards require --from", file=sys.stderr)
        return 2
    batch_id = args.id or new_id(root)
    if not DATED_ID_RE.fullmatch(batch_id):
        print("ad-hoc id must be YYYYMMDD-<6 hex>", file=sys.stderr)
        return 2
    target = batch_dir(root, batch_id)
    if target.exists():
        print(f"batch already exists: {batch_id}", file=sys.stderr)
        return 1
    config = load_config(root)
    card = {
        "id": batch_id,
        "goal": args.goal,
        "type": "process",
        "base": str(config.get("base", "main")),
        "size_budget": 0,
        "allowed": parse_list(args.allowed, ["**"]),
        "forbidden": parse_list(args.forbidden, []),
        "acceptance": parse_list(args.exit_criterion, []),
        "changelog": [],
        "skills": [],
        "ad_hoc": True,
        "created_at": utc_now(),
    }
    write_json(target / "card.json", card)
    print(f"planned {batch_id}")
    print(f"hash: {card_hash(card)[:8]}")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    batch_id = resolve_id(root, args.id)
    card = read_card(root, batch_id)
    if card.get("legacy"):
        print("legacy cards are read-only and cannot be approved", file=sys.stderr)
        return 1
    current, message = source_is_current(root, card)
    if not current:
        print(message, file=sys.stderr)
        return 1
    digest = card_hash(card)
    if args.confirm != digest[:8]:
        print(f"confirm mismatch: expected {digest[:8]}", file=sys.stderr)
        return 1
    approval = {
        "batch": batch_id,
        "card_hash": digest,
        "source_sha256": card.get("source_sha256"),
        "approved_by": args.by,
        "approved_at": utc_now(),
    }
    write_json(batch_dir(root, batch_id) / "approval.json", approval)
    print(f"approved {batch_id}")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    git_required(root)
    batch_id = resolve_id(root, args.id)
    card = read_card(root, batch_id)
    if card.get("legacy"):
        print("legacy cards are read-only and cannot be started", file=sys.stderr)
        return 1
    approval = load_json(batch_dir(root, batch_id) / "approval.json")
    if approval is None or approval.get("card_hash") != card_hash(card):
        print("card is not approved (or approval is stale)", file=sys.stderr)
        return 1
    if approval.get("source_sha256") != card.get("source_sha256"):
        print("card source is not approved (or approval is stale)", file=sys.stderr)
        return 1
    current_source, message = source_is_current(root, card)
    if not current_source:
        print(message, file=sys.stderr)
        return 1
    current = active_id(root)
    if current:
        current_state = read_state(root, current)
        if current_state.get("status") in {"merged", "aborted"}:
            clear_active(root)
            print(
                f"cleared stale active batch {current} "
                f"({current_state.get('status')})"
            )
        else:
            print(f"another batch is active: {current}", file=sys.stderr)
            return 1

    config = load_config(root)
    base_ref = args.base or str(card.get("base") or config.get("base", "main"))
    base = resolve_commit(root, base_ref)
    if not base:
        print(f"base does not resolve to a commit: {base_ref}", file=sys.stderr)
        return 1
    slug = branch_slug(str(card.get("goal", "")))
    default_branch = f"{config.get('branch_prefix', 'batch/')}{batch_id}"
    if slug:
        default_branch = f"{default_branch}-{slug}"
    branch = args.branch or default_branch
    if not args.no_branch:
        code, _, err = run_git(root, ["switch", "-c", branch])
        if code != 0:
            print(f"could not create branch {branch}: {err}", file=sys.stderr)
            return 1

    state = {
        "batch": batch_id,
        "status": "started",
        "base": base,
        "base_ref": base_ref,
        "branch": branch,
        "card_hash": card_hash(card),
        "source_sha256": card.get("source_sha256"),
        "started_at": utc_now(),
        "checks": {},
    }
    write_json(batch_dir(root, batch_id) / "state.json", state)
    set_active(root, batch_id)
    print(f"started {batch_id} on {branch} (base {base})")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    git_required(root)
    batch_id = resolve_id(root, args.id)
    card = read_card(root, batch_id)
    state = read_state(root, batch_id)
    if card.get("legacy"):
        print("legacy cards are read-only and cannot be checked", file=sys.stderr)
        return 1
    approval = load_json(batch_dir(root, batch_id) / "approval.json")
    if approval is None or approval.get("card_hash") != card_hash(card):
        print("card is not approved (or approval is stale)", file=sys.stderr)
        return 1
    current, message = source_is_current(root, card)
    if not current:
        state["status"] = "check_failed"
        state["source_error"] = message
        state["checked_at"] = utc_now()
        write_json(batch_dir(root, batch_id) / "state.json", state)
        append_evidence(root, batch_id, f"source: FAIL ({message})")
        print(message, file=sys.stderr)
        return 1
    config = load_config(root)
    conflict = duplicate_id_error(root, card, config, batch_id)
    if conflict:
        state["status"] = "check_failed"
        state["id_error"] = conflict
        state["checked_at"] = utc_now()
        write_json(batch_dir(root, batch_id) / "state.json", state)
        append_evidence(root, batch_id, f"id: FAIL ({conflict})")
        print(conflict, file=sys.stderr)
        return 1
    base_ref = state.get("base") or str(config.get("base", "main"))
    base = resolve_commit(root, base_ref)
    if not base:
        state["status"] = "check_failed"
        state["base_error"] = f"base does not resolve to a commit: {base_ref}"
        state["checked_at"] = utc_now()
        write_json(batch_dir(root, batch_id) / "state.json", state)
        append_evidence(root, batch_id, f"base: FAIL ({state['base_error']})")
        print(state["base_error"], file=sys.stderr)
        return 1
    state["base"] = base
    state["base_ref"] = state.get("base_ref") or base_ref
    changed, violations = check_scope(root, card, base, config)
    added, deleted, binary, budget_error = check_budget(root, card, base, changed)
    changelog_errors, changelog_warnings = check_changelog(root, card, changed)
    skill_errors, skill_found = check_skills(root, card)
    gate_errors = [*violations, *changelog_errors, *skill_errors]
    if budget_error:
        gate_errors.append(budget_error)

    append_evidence(
        root,
        batch_id,
        f"scope: {'PASS' if not violations else 'FAIL'} ({len(changed)} changed paths)",
    )
    for path in changed:
        append_evidence(root, batch_id, f"changed: {path}")
    for violation in violations:
        append_evidence(root, batch_id, f"scope: {violation}")
    for violation in changelog_errors:
        append_evidence(root, batch_id, violation)
    for warning in changelog_warnings:
        append_evidence(root, batch_id, f"warn: {warning}")
    for violation in skill_errors:
        append_evidence(root, batch_id, violation)
    if budget_error:
        append_evidence(root, batch_id, budget_error)
    for violation in gate_errors:
        print(f"[fail] {violation}", file=sys.stderr)
    for warning in changelog_warnings:
        print(f"[warn] {warning}", file=sys.stderr)

    results = run_checks(root, batch_id, config) if not gate_errors else {}
    passed = not gate_errors and all(
        item.get("status") == "pass" for item in results.values()
    )
    state["status"] = "checked" if passed else "check_failed"
    state["checks"] = results
    state["scope"] = {
        "budget": int(card.get("size_budget", 0)),
        "changed": len(changed),
        "added": added,
        "deleted": deleted,
        "binary": binary,
        "result": "pass" if not budget_error and not violations else "fail",
    }
    state["changelog"] = {
        "declared": [str(item) for item in card.get("changelog", [])],
        "warnings": changelog_warnings,
    }
    state["skills"] = skill_found
    state["checked_at"] = utc_now()
    write_json(batch_dir(root, batch_id) / "state.json", state)
    print(f"scope: {'PASS' if not violations else 'FAIL'} ({len(changed)} paths)")
    print(
        f"budget: {'SKIP' if not card.get('size_budget') else ('FAIL' if budget_error else 'PASS')}"
        f" ({added + deleted} lines)"
    )
    print(f"changelog: {'FAIL' if changelog_errors else 'PASS'}")
    print(f"skills: {'FAIL' if skill_errors else 'PASS'}")
    print(f"result: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


PR_BODY_SOURCE = "pr-body.source.md"
PR_BODY_SECTIONS = (
    "## Summary",
    "## Impact",
    "## Verification",
    "## Risks",
    "## Self-check",
)


def pr_body(root: Path, batch_id: str) -> str | None:
    """Return the hand-written body, or ``None`` when the writer skipped it.

    A generated body is not a substitute: the pull request template asks five
    questions a generator cannot answer, so a missing source file is an error.
    """
    written = batch_dir(root, batch_id) / PR_BODY_SOURCE
    if not written.is_file():
        return None
    text = written.read_text(encoding="utf-8").strip()
    return text or None


def missing_sections(body: str) -> list[str]:
    """Name the sections of the template a body is missing, in template order."""
    positions = []
    for name in PR_BODY_SECTIONS:
        if name not in body:
            positions.append(name)
    return positions


def sections_out_of_order(body: str) -> bool:
    seen = [body.index(name) for name in PR_BODY_SECTIONS if name in body]
    return seen != sorted(seen)


def scaffold_language(root: Path) -> dict[str, Any]:
    """Resolve the language block used for PR body translations.

    Mirrors ``nebula-bootstrap/scripts/language.py``: a ``language`` block wins,
    legacy ``repoLocale``/``docsLocale`` blocks are mapped, and a missing or
    invalid block falls back to zh-CN. PR translations are best effort, so this
    only needs the primary, supported, and external values.
    """
    data = load_json(root / SCAFFOLD_REL) or {}
    block = data.get("language")
    if isinstance(block, dict) and isinstance(block.get("primary"), str):
        primary = block["primary"].strip()
        supported = [
            str(item).strip()
            for item in block.get("supported", [])
            if isinstance(item, str) and item.strip()
        ]
        if primary:
            supported = [primary, *[item for item in supported if item != primary]]
        external = str(block.get("external") or primary).strip()
        return {
            "primary": primary or "zh-CN",
            "supported": supported or ["zh-CN"],
            "external": external if external in supported else (primary or "zh-CN"),
        }
    repo = data.get("repoLocale") if isinstance(data.get("repoLocale"), dict) else {}
    docs = data.get("docsLocale") if isinstance(data.get("docsLocale"), dict) else {}
    primary = str(repo.get("primary") or docs.get("primary") or "zh-CN").strip() or "zh-CN"
    supported: list[str] = []
    for source in (repo.get("supported"), docs.get("supported")):
        for item in source or []:
            value = str(item).strip()
            if value and value not in supported:
                supported.append(value)
    if primary not in supported:
        supported.insert(0, primary)
    external = str(docs.get("external") or primary).strip()
    return {
        "primary": primary,
        "supported": supported,
        "external": external if external in supported else primary,
    }


def pr_translations(
    root: Path,
    batch_id: str,
    body_path: Path,
    digest: str,
    config: dict[str, Any],
    state: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Write PR body translations through ``config.translate``.

    Returns the locales written and the problems found. A missing hook, a hook
    that exits non-zero and a hook that writes nothing are all problems: the
    English body is authoritative, but a reader who cannot get the other
    language is a failure of the hand-over, not a warning.
    """
    language = scaffold_language(root)
    source_locale = language["external"]
    targets = [item for item in language["supported"] if item != source_locale]
    if not targets:
        return [], []
    command = config.get("translate")
    if not command:
        return [], [
            "config.translate is empty; the PR body has no translation "
            "(set LETHEBAR_TRANSLATION_FILE for the offline hook)"
        ]
    card = read_card(root, batch_id)
    directory = batch_dir(root, batch_id)
    translations: list[dict[str, Any]] = []
    problems: list[str] = []
    for locale in targets:
        out = directory / f"pr-body.{locale}.md"
        out.unlink(missing_ok=True)
        code, out_text, err_text = run_hook(
            root,
            command,
            {
                "id": batch_id,
                "title": str(card.get("goal", batch_id)),
                "body": str(body_path),
                "branch": str(state.get("branch", "")),
                "root": str(root),
                "locale": locale,
                "out": str(out),
            },
        )
        if out_text:
            print(out_text)
        if code != 0:
            detail = err_text.strip() or "no message"
            problems.append(f"translation {locale} failed (exit {code}): {detail}")
            continue
        if not out.exists() or not out.read_text(encoding="utf-8").strip():
            problems.append(f"translation {locale}: the hook produced no output")
            continue
        translations.append(
            {
                "locale": locale,
                "file": out.relative_to(root).as_posix(),
                "machine": True,
                "authoritative": False,
            }
        )
    if not translations:
        return [], problems or ["no translation was written"]
    write_json(
        directory / "pr-body.manifest.json",
        {
            "source": body_path.relative_to(root).as_posix(),
            "source_sha256": digest,
            "source_locale": source_locale,
            "generated_at": utc_now(),
            "tool": "batch.py",
            "translations": translations,
        },
    )
    print(f"translations: {', '.join(item['locale'] for item in translations)}")
    return [item["locale"] for item in translations], problems


def redo_translations(root: Path, batch_id: str, state: dict[str, Any]) -> int:
    """Regenerate the PR body translations from the body already on disk.

    ``pr --prepare`` refuses to run once a batch is merged, but a translator
    can be improved afterwards, and the translation is a file in the batch
    directory, not a part of the pull request.
    """
    body_path = root / str(state.get("pr_body") or "")
    if not state.get("pr_body") or not body_path.is_file():
        print(
            "no prepared PR body to translate; run 'pr --prepare' first",
            file=sys.stderr,
        )
        return 1
    digest = hashlib.sha256(body_path.read_bytes()).hexdigest()
    config = load_config(root)
    locales, problems = pr_translations(root, batch_id, body_path, digest, config, state)
    state["pr_translations"] = locales
    write_json(batch_dir(root, batch_id) / "state.json", state)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    return 0


def cmd_pr(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    batch_id = resolve_id(root, args.id)
    state = read_state(root, batch_id)
    if args.translations_only:
        return redo_translations(root, batch_id, state)
    if state.get("status") not in {"checked", "pr_ready"}:
        print("run 'check' successfully before preparing a PR", file=sys.stderr)
        return 1
    card = read_card(root, batch_id)
    if card.get("legacy"):
        print("legacy cards have no PR flow", file=sys.stderr)
        return 1
    approval = load_json(batch_dir(root, batch_id) / "approval.json")
    if approval is None or approval.get("card_hash") != card_hash(card):
        print("card is not approved (or approval is stale)", file=sys.stderr)
        return 1
    current, message = source_is_current(root, card)
    if not current:
        print(message, file=sys.stderr)
        return 1
    body = pr_body(root, batch_id)
    if body is None:
        print(
            f"missing .batch/{batch_id}/{PR_BODY_SOURCE}; write the body first. "
            "The template asks five questions:",
            file=sys.stderr,
        )
        for name in PR_BODY_SECTIONS:
            print(f"  {name}", file=sys.stderr)
        return 1
    missing = missing_sections(body)
    if missing:
        print(
            "the body is missing template sections: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 1
    if sections_out_of_order(body):
        print(
            "the body has the template sections out of order: "
            + " -> ".join(PR_BODY_SECTIONS),
            file=sys.stderr,
        )
        return 1
    body_path = args.body_file or (batch_dir(root, batch_id) / "pr-body.md")
    body_path = body_path if body_path.is_absolute() else root / body_path
    write_text(body_path, body + "\n")
    digest = hashlib.sha256(body_path.read_bytes()).hexdigest()
    print(f"prepared {body_path.relative_to(root)}")
    print(f"body hash: {digest[:8]}")
    state["status"] = "pr_ready"
    state["pr_body"] = str(body_path.relative_to(root))
    state["pr_body_sha256"] = digest
    config = load_config(root)
    locales, problems = pr_translations(
        root, batch_id, body_path, digest, config, state
    )
    state["pr_translations"] = locales
    write_json(batch_dir(root, batch_id) / "state.json", state)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print(
            "the pull request body has no translation; fix the hook or set "
            "LETHEBAR_TRANSLATION_FILE",
            file=sys.stderr,
        )
        return 1

    if not args.create:
        return 0
    if args.confirm != digest[:8]:
        print(f"confirm mismatch: expected {digest[:8]}", file=sys.stderr)
        return 1
    command = config.get("pr_create")
    if not command:
        print("config.pr_create is empty; use --prepare only", file=sys.stderr)
        return 2
    code, out, err = run_hook(
        root,
        command,
        {
            "id": batch_id,
            "title": str(card.get("goal", batch_id)),
            "body": str(body_path),
            "branch": str(state.get("branch", "")),
            "root": str(root),
        },
    )
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    if code != 0:
        return 1
    state["status"] = "pr_created"
    state["pr_output"] = out
    write_json(batch_dir(root, batch_id) / "state.json", state)
    print(f"created PR for {batch_id}")
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    batch_id = resolve_id(root, args.id)
    state = read_state(root, batch_id)
    if not args.yes:
        print("merge requires --yes", file=sys.stderr)
        return 2
    status = state.get("status")
    if args.force and not args.external:
        print("--force is only valid with --external", file=sys.stderr)
        return 2
    if status not in {"checked", "pr_ready", "pr_created"}:
        if not (args.external and status == "check_failed" and args.force):
            if args.external and status == "check_failed":
                print(
                    "batch check failed; an external merge needs "
                    "--force --reason <why the failure is accepted>",
                    file=sys.stderr,
                )
            else:
                print("batch is not checked or PR-ready", file=sys.stderr)
            return 1
        if not args.reason.strip():
            print("--force requires --reason", file=sys.stderr)
            return 2
    config = load_config(root)
    command = config.get("merge")
    if not command:
        if not args.external:
            print(
                "config.merge is empty; merge the PR externally, then rerun "
                "'merge --external --pr <number> --yes'",
                file=sys.stderr,
            )
            return 2
        override = None
        if status == "check_failed":
            override = {
                "from": status,
                "reason": args.reason.strip(),
                "at": utc_now(),
            }
        state["status"] = "merged"
        state["merged_at"] = utc_now()
        state["merge_mode"] = "external"
        state["pr"] = args.pr
        if override is not None:
            state["check_override"] = override
        write_json(batch_dir(root, batch_id) / "state.json", state)
        clear_active(root)
        suffix = " after a forced check failure" if override is not None else ""
        print(f"merged {batch_id} externally (PR {args.pr}){suffix}")
        return 0
    if args.external:
        print(
            "--external is only valid when config.merge is empty",
            file=sys.stderr,
        )
        return 2
    if status != "pr_created":
        print("batch has no created PR", file=sys.stderr)
        return 1
    code, out, err = run_hook(
        root,
        command,
        {
            "id": batch_id,
            "title": batch_id,
            "body": "",
            "branch": str(state.get("branch", "")),
            "root": str(root),
            "pr": args.pr,
        },
    )
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    if code != 0:
        return 1
    state["status"] = "merged"
    state["merged_at"] = utc_now()
    write_json(batch_dir(root, batch_id) / "state.json", state)
    clear_active(root)
    print(f"merged {batch_id}")
    return 0


def cmd_abort(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    batch_id = resolve_id(root, args.id)
    state = read_state(root, batch_id)
    if state.get("status") == "merged":
        print("cannot abort a merged batch", file=sys.stderr)
        return 1
    state["status"] = "aborted"
    state["aborted_at"] = utc_now()
    write_json(batch_dir(root, batch_id) / "state.json", state)
    if active_id(root) == batch_id:
        clear_active(root)
    print(f"aborted {batch_id}")
    return 0


def cmd_adopt(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    source = Path(args.source)
    source = source if source.is_absolute() else root / source
    source = source.resolve()
    if not source.is_file():
        print(f"card source not found: {source}", file=sys.stderr)
        return 2
    batch_id = args.id or source.stem
    if not CARD_ID_RE.fullmatch(batch_id):
        print("legacy id must be B followed by digits", file=sys.stderr)
        return 2
    target = batch_dir(root, batch_id)
    if target.exists():
        print(f"batch already exists: {batch_id}", file=sys.stderr)
        return 1
    snapshot = {
        "id": batch_id,
        "legacy": True,
        "source": source_relative(root, source),
        "source_sha256": file_sha256(source),
    }
    write_json(target / "card.json", snapshot)
    print(f"adopted {batch_id} as read-only legacy")
    print(f"source: {snapshot['source']}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    root_dir = state_root(root)
    if not root_dir.is_dir():
        print("no batches")
        return 0
    for path in sorted(root_dir.iterdir(), key=lambda item: batch_sort_key(item.name)):
        if not path.is_dir():
            continue
        state = load_json(path / "state.json") or {}
        card = load_json(path / "card.json") or {}
        status = state.get("status") or ("legacy" if card.get("legacy") else "planned")
        print(f"{path.name}\t{status}\t{card.get('goal', '')}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    try:
        batch_id = resolve_id(root, args.id)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print_status(root, batch_id, args.json)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="project-local batch execution skeleton")
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="create a batch card")
    plan.add_argument("id", nargs="?")
    plan.add_argument("--from", dest="source", help="plan from an external card")
    plan.add_argument("--goal")
    plan.add_argument("--allowed", action="append")
    plan.add_argument("--forbidden", action="append")
    plan.add_argument("--exit-criterion", action="append")
    plan.set_defaults(func=cmd_plan)

    adopt = sub.add_parser("adopt", help="adopt a legacy card as read-only")
    adopt.add_argument("id", nargs="?")
    adopt.add_argument("--from", dest="source", required=True)
    adopt.set_defaults(func=cmd_adopt)

    approve = sub.add_parser("approve", help="approve a card by hash")
    approve.add_argument("id", nargs="?")
    approve.add_argument("--confirm", required=True)
    approve.add_argument("--by", default="")
    approve.set_defaults(func=cmd_approve)

    start = sub.add_parser("start", help="start an approved batch")
    start.add_argument("id", nargs="?")
    start.add_argument("--base")
    start.add_argument("--branch")
    start.add_argument("--no-branch", action="store_true")
    start.set_defaults(func=cmd_start)

    check = sub.add_parser("check", help="check scope and configured commands")
    check.add_argument("id", nargs="?")
    check.set_defaults(func=cmd_check)

    pr = sub.add_parser("pr", help="prepare or create a PR body")
    pr.add_argument("id", nargs="?")
    pr.add_argument("--prepare", action="store_true")
    pr.add_argument("--create", action="store_true")
    pr.add_argument(
        "--translations-only",
        action="store_true",
        help="redo the PR body translations from the body already on disk",
    )
    pr.add_argument("--body-file", type=Path)
    pr.add_argument("--confirm")
    pr.set_defaults(func=cmd_pr)

    merge = sub.add_parser("merge", help="run the configured merge command")
    merge.add_argument("id", nargs="?")
    merge.add_argument("--pr", required=True)
    merge.add_argument("--yes", action="store_true")
    merge.add_argument(
        "--external",
        action="store_true",
        help="record a manually merged PR; only when config.merge is empty",
    )
    merge.add_argument(
        "--force",
        action="store_true",
        help="with --external, accept a check_failed batch; requires --reason",
    )
    merge.add_argument(
        "--reason",
        default="",
        help="why a check_failed batch is accepted (recorded in state.json)",
    )
    merge.set_defaults(func=cmd_merge)

    abort = sub.add_parser("abort", help="abort an unmerged batch")
    abort.add_argument("id", nargs="?")
    abort.set_defaults(func=cmd_abort)

    listing = sub.add_parser("list", help="list batches")
    listing.set_defaults(func=cmd_list)

    status = sub.add_parser("status", help="show one batch")
    status.add_argument("id", nargs="?")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
