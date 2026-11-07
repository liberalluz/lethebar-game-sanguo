"""Say what a pack repository is missing before it publishes, one item at a time.

A pack repository holds data, and the tools that turn that data into something a
player can install live in the engine. So the first publication is where an author
finds out what the repository never had: a manifest without an id, a version that
does not match the tag, an artifact that was never built, a release that was never
created, an asset a browser cannot reach.

Each of those is a separate item here, numbered, each saying what is missing and the
command that fixes it. The last item fetches the published asset over the real
network, because a release that answers 404 or omits CORS headers looks fine from a
terminal and fails from a browser.

    python infra/tool/release/preflight.py --pack packs/sanguo --repo o/world \
        --tag pack/sanguo/v1.0.0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

MANIFEST = "manifest.json"
TOTAL = 6


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_manifest(root: Path) -> dict:
    return json.loads((root / MANIFEST).read_text(encoding="utf-8"))


def release_exists(repo: str, tag: str) -> bool:
    client = os.environ.get("LETHEBAR_GH", "gh")
    probe = [client, "release", "view", tag, "--repo", repo]
    return subprocess.run(
            probe, check=False, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        ).returncode == 0


def reachable(url: str) -> tuple[bool, str]:
    """Fetch the first bytes of the asset and report what the far side said."""
    request = urllib.request.Request(url, method="GET", headers={"Range": "bytes=0-1023"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read(1024)
            allow = response.headers.get("Access-Control-Allow-Origin", "")
            status = response.status
    except urllib.error.HTTPError as error:
        return False, f"HTTP {error.code}"
    except Exception as error:  # noqa: BLE001 - the message is the report
        return False, str(error)
    if allow:
        return True, f"HTTP {status}, CORS allow-origin {allow}"
    return True, f"HTTP {status}, no CORS allow-origin header"


def preflight(root: Path, repo: str, tag: str, dist: Path, asset_url: str) -> int:
    failures = 0
    manifest: dict = {}

    def report(number: int, title: str, ok: bool, detail: str, command: str = "") -> None:
        nonlocal failures
        mark = "ok" if ok else "missing"
        print(f"[{number}/{TOTAL}] {title} - {mark}: {detail}")
        if not ok:
            failures += 1
            if command:
                print(f"      run: {command}")

    # 1. the manifest exists and names a pack
    manifest_path = root / MANIFEST
    if manifest_path.is_file():
        try:
            manifest = read_manifest(root)
        except json.JSONDecodeError as error:
            report(1, "manifest", False, f"{manifest_path} is not JSON: {error}")
        else:
            pack_id = str(manifest.get("id", "")).strip()
            report(
                1,
                "manifest",
                pack_id != "",
                f"{MANIFEST} names {pack_id}" if pack_id else f"{MANIFEST} carries no id",
                f"edit {manifest_path} and give it an id",
            )
    else:
        report(1, "manifest", False, f"{manifest_path} does not exist", f"create {manifest_path}")

    # 2. the manifest carries what a release needs
    pack_id = str(manifest.get("id", "")).strip()
    version = str(manifest.get("version", "")).strip()
    fields = [name for name in ("version", "specVersion", "engine") if not manifest.get(name)]
    report(
        2,
        "version and contract",
        not fields,
        f"version {version}, specVersion {manifest.get('specVersion')}, engine {manifest.get('engine')}"
        if not fields
        else f"{MANIFEST} carries no {', '.join(fields)}",
        f"edit {manifest_path} and fill in {', '.join(fields) or 'the missing fields'}",
    )

    # 3. the artifact was built
    artifact = dist / f"{pack_id}.zip"
    report(
        3,
        "artifact",
        artifact.is_file(),
        f"{artifact} ({artifact.stat().st_size} bytes)" if artifact.is_file() else f"{artifact} does not exist",
        f"python infra/tool/release/pack.py build {root} --out {dist}",
    )

    # 4. the descriptor names the bytes that were built
    sidecar = dist / f"{pack_id}-{version}.json"
    detail = f"{sidecar} does not exist"
    ok = False
    if sidecar.is_file() and artifact.is_file():
        try:
            described = json.loads(sidecar.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            detail = f"{sidecar} is not JSON: {error}"
        else:
            actual = sha256_of(artifact)
            ok = described.get("sha256") == actual and described.get("bytes") == artifact.stat().st_size
            detail = (
                f"{sidecar} names sha256 {described.get('sha256')}"
                if ok
                else f"{sidecar} says sha256 {described.get('sha256')}, the artifact hashes to {actual}"
            )
    report(4, "descriptor", ok, detail, f"python infra/tool/release/pack.py hash {artifact}")

    # 5. the release exists
    report(
        5,
        "release",
        release_exists(repo, tag),
        f"{repo} has a release for {tag}" if release_exists(repo, tag) else f"{repo} has no release for {tag}",
        f"gh release create {tag} --repo {repo} --title {tag} --generate-notes",
    )

    # 6. a browser can reach the asset
    url = asset_url or f"https://github.com/{repo}/releases/download/{tag}/{pack_id}.zip"
    ok, detail = reachable(url)
    report(6, "asset over the network", ok, f"{url} answered {detail}", f"gh release upload {tag} {artifact} --repo {repo}")

    print(f"preflight: {TOTAL - failures}/{TOTAL} item(s) ready")
    return 0 if failures == 0 else 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Say what a pack repository is missing.")
    parser.add_argument("--pack", required=True, help="the pack directory that holds manifest.json")
    parser.add_argument("--repo", required=True, help="owner/name of the repository that publishes it")
    parser.add_argument("--tag", required=True, help="the tag the release carries, pack/<id>/vX.Y.Z")
    parser.add_argument("--dist", default="dist", help="where the artifact and descriptor live")
    parser.add_argument("--asset-url", default="", help="fetch this instead of the release URL")
    args = parser.parse_args(argv)
    return preflight(Path(args.pack), args.repo, args.tag, Path(args.dist), args.asset_url)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
