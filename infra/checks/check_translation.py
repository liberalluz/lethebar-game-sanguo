"""Refuse a batch whose prepared pull request body has no current translation.

``pr --prepare`` writes ``.batch/<id>/pr-body.<locale>.md`` plus a manifest that
holds the sha256 of the body it translated. Comparing the two turns the gate red
when a body is edited without preparing it again; a batch with no prepared body
has nothing to translate and passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

BATCH_BRANCH = re.compile(r"^batch/(?P<id>B\d{1,3})(?:-|$)")
BATCH_DIR = re.compile(r"^B\d{1,3}$")


def current_branch(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def target_locales(root: Path) -> list[str]:
    scaffold = json.loads((root / ".nebula-scaffold.json").read_text(encoding="utf-8"))
    language = scaffold.get("language") or {}
    external = str(language.get("external", "")).strip()
    return [
        str(item)
        for item in language.get("supported", [])
        if str(item).strip() and str(item) != external
    ]


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="check pull request body translations")
    parser.add_argument("--root", default=".", help="repository root")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    branch = current_branch(root)
    match = BATCH_BRANCH.match(branch)
    batch_id = match.group("id") if match else ""
    if not batch_id:
        print(f"[translation] {branch or 'this branch'} is not a batch branch; nothing to check")
        return 0
    if not BATCH_DIR.fullmatch(batch_id):
        print(f"[translation] unrecognised batch id {batch_id!r}; nothing to check")
        return 0

    locales = target_locales(root)
    if not locales:
        print("[translation] the language block declares no target locale; nothing to check")
        return 0
    directory = root / ".batch" / batch_id
    manifest_path = directory / "pr-body.manifest.json"
    if not manifest_path.is_file():
        if not (directory / "pr-body.md").is_file():
            print(f"[translation] {batch_id} has no prepared body yet; nothing to translate")
            return 0
        return fail(
            f"[translation] {batch_id} has a prepared body but no translation; "
            "set DEEPSEEK_API_KEY and run batch.py pr --prepare again"
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = str(manifest.get("source", "")).strip()
    if not source:
        return fail("[translation] the manifest names no source body")
    body = root / source
    if not body.is_file():
        return fail(f"[translation] the manifest points at {source}, which does not exist")
    if str(manifest.get("source_sha256", "")).strip() != hashlib.sha256(body.read_bytes()).hexdigest():
        return fail(
            f"[translation] the body changed after the last prepare ({source}); "
            "run batch.py pr --prepare again"
        )

    listed = {
        str(item.get("locale", "")).strip(): str(item.get("file", "")).strip()
        for item in manifest.get("translations", [])
        if isinstance(item, dict)
    }
    problems = []
    for locale in locales:
        relative = listed.get(locale, "")
        if not relative:
            problems.append(f"{locale}: the manifest lists no translation")
            continue
        path = root / relative
        if not path.is_file():
            problems.append(f"{locale}: the manifest lists {relative}, which does not exist")
        elif not path.read_text(encoding="utf-8").strip():
            problems.append(f"{locale}: {relative} is empty")
    if problems:
        for problem in problems:
            print(f"[translation] {problem}", file=sys.stderr)
        return 1
    print(f"[translation] {batch_id} carries a current translation for {', '.join(locales)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
