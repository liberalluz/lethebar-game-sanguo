"""Scratch directories a check makes and removes itself.

`tempfile.mkdtemp()` creates its directory with mode ``0o700``. On Windows that
replaces the access control entry the new directory would inherit instead of
widening it, so under a restricted token the creator cannot write inside the
directory it just made, and the directory can never be removed: the self-test
dies with ``PermissionError: [WinError 5]`` and leaves a corpse behind.

A plain ``mkdir`` inherits what the parent has, so a directory made here is
writable by whoever made it, in every token. The directory also lives inside
the checkout rather than in the system temporary directory, because that one
can be read-only for a sandboxed runner.
"""

from __future__ import annotations

import os
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = ROOT / ".test-tmp"

# Everything a removable fixture has ever been called. The guard looks for both
# so a leftover from an older run is reported, not just one this module made.
LEFTOVER_PREFIXES = ("fixtures-", "lethebar-pack-", "guide-")


@contextmanager
def fixture_dir(tag: str) -> Iterator[Path]:
    """Yield an empty directory under `.test-tmp` and remove it on the way out."""

    SCRATCH.mkdir(parents=True, exist_ok=True)
    path = SCRATCH / f"fixtures-{tag}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    path.mkdir(exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=False)


def leftovers() -> list[str]:
    """Names of fixture directories still sitting in `.test-tmp`."""

    if not SCRATCH.is_dir():
        return []
    return sorted(
        entry.name
        for entry in SCRATCH.iterdir()
        if entry.is_dir() and entry.name.startswith(LEFTOVER_PREFIXES)
    )
