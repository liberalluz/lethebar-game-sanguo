"""Build a pack directory into a reproducible zip, hash it, and publish it.

A pack reaches a player either compiled into the build or imported by hand. Once a
world repository owns its packs, both stop working: the pack has to travel as an
artifact with a hash an engine can check. This tool is that step.

Reproducibility is the point. Zip records a timestamp per entry and walks the
directory in whatever order the filesystem hands back, so a build fixes both: one
timestamp for every entry and a sorted name list. Two builds of one directory are
then byte-identical, which is what makes a hash worth writing down.

    python infra/tool/release/pack.py build packs/<id> --out dist
    python infra/tool/release/pack.py hash dist/<id>.zip
    python infra/tool/release/pack.py publish dist/<id>.zip --repo o/r --tag pack/<id>/vX.Y.Z

`hash` writes `<id>-<version>.json` next to the zip: the id, the version, the byte
count, the sha256, the specVersion and the engine range, which is what an engine
needs to decide whether it can install the artifact at all.

`publish` is dry by default and only touches the network with `--apply`. An upload
attaches files to a release that already exists, so `publish` creates the release
first when the tag has none: the first publication of any pack would otherwise fail
with `release not found`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

FIXED_TIME = (1980, 1, 1, 0, 0, 0)
MANIFEST = "manifest.json"
BADGE_BEGIN = "<!-- pack-badges:begin -->"
BADGE_END = "<!-- pack-badges:end -->"


def gh() -> str:
    """The GitHub client, overridable so a test can prove the order of calls."""
    return os.environ.get("LETHEBAR_GH", "gh")


def files_of(root: Path) -> list[Path]:
    """Every file of the pack, in a stable order, manifest first."""
    entries: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            entries.append(path.relative_to(root))
    entries.sort(key=lambda item: (item.as_posix() != MANIFEST, item.as_posix()))
    return entries


def build(root: Path, out_dir: Path | None = None) -> Path:
    """Write a zip of `root` and return its path."""
    manifest_path = root / MANIFEST
    if not manifest_path.is_file():
        raise SystemExit(f"{root} carries no {MANIFEST}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pack_id = str(manifest.get("id", "")).strip()
    if pack_id == "":
        raise SystemExit(f"{manifest_path} names no id")

    out_dir = out_dir or Path("dist")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{pack_id}.zip"

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative in files_of(root):
            info = zipfile.ZipInfo(relative.as_posix(), date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (root / relative).read_bytes())
    return target


def digest(target: Path) -> str:
    return hashlib.sha256(target.read_bytes()).hexdigest()


def describe(target: Path) -> dict:
    """The manifest an engine reads before it installs the artifact."""
    with zipfile.ZipFile(target) as archive:
        manifest = json.loads(archive.read(MANIFEST).decode("utf-8"))
    data = target.read_bytes()
    return {
        "id": str(manifest.get("id", "")),
        "version": str(manifest.get("version", "")),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "specVersion": str(manifest.get("specVersion", "")),
        "engine": str(manifest.get("engine", "")),
    }


def write_descriptor(target: Path) -> Path:
    described = describe(target)
    sidecar = target.with_name(f"{described['id']}-{described['version']}.json")
    sidecar.write_text(
        json.dumps(described, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return sidecar


def decode_gh_output(raw: bytes) -> str:
    """Read what `gh` wrote, whatever the console would have called it.

    `gh` writes UTF-8. Decoding it with the Windows code page raises on the first
    byte outside ASCII — a Chinese release body is enough — and the failure lands
    in a reader thread, where it reads as if the tool itself had broken while
    the upload had in fact succeeded. A reply we only print cannot be worth a
    traceback: a byte that is not UTF-8 becomes U+FFFD.
    """
    return raw.decode("utf-8", errors="replace")


def release_exists(repo: str, tag: str) -> bool:
    """Ask GitHub whether the tag already carries a release."""
    probe = [gh(), "release", "view", tag, "--repo", repo]
    completed = subprocess.run(probe, check=False, capture_output=True)
    if completed.returncode != 0:
        reason = decode_gh_output(completed.stderr).strip()
        if reason:
            print(f"gh release view: {reason}", file=sys.stderr)
    return completed.returncode == 0


def create_command(repo: str, tag: str) -> list[str]:
    return [
        gh(),
        "release",
        "create",
        tag,
        "--repo",
        repo,
        "--title",
        tag,
        "--generate-notes",
    ]


def upload_command(target: Path, sidecar: Path, repo: str, tag: str) -> list[str]:
    return [
        gh(),
        "release",
        "upload",
        tag,
        str(target),
        str(sidecar),
        "--repo",
        repo,
        "--clobber",
    ]


def validate(target: Path) -> dict:
    """Refuse a pack that cannot be named, before any command is built."""
    described = describe(target)
    missing = [field for field in ("id", "version") if not described.get(field)]
    if missing:
        raise SystemExit(f"{target} names no {', '.join(missing)}; preflight says the same")
    if described["sha256"] != digest(target):
        raise SystemExit(f"{target} hashed differently twice; refusing to publish")
    return described


def publish_commands(target: Path, repo: str, tag: str, exists: bool) -> list[list[str]]:
    """The commands a publication needs, in the order it needs them.

    The descriptor is written here, so the bytes a player will verify are the bytes
    this run produced. A pack whose manifest carries no id or version cannot be
    named in a descriptor, and is refused rather than published under an empty name.
    """
    validate(target)
    sidecar = write_descriptor(target)
    commands: list[list[str]] = []
    if not exists:
        commands.append(create_command(repo, tag))
    commands.append(upload_command(target, sidecar, repo, tag))
    return commands


def read_manifest(root: Path) -> dict:
    path = root / MANIFEST
    if not path.is_file():
        raise SystemExit(f"{root} carries no {MANIFEST}")
    return json.loads(path.read_text(encoding="utf-8"))


def pack_manifests(root: Path) -> list[tuple[Path, dict]]:
    """Every `packs/<id>/manifest.json`, ordered by directory name."""
    packs = root / "packs"
    if not packs.is_dir():
        raise SystemExit(
            f"{root} has no packs/ directory; a pack repository keeps one "
            "directory per pack under packs/"
        )
    found = [
        (path.parent, read_manifest(path.parent))
        for path in sorted(packs.glob("*/manifest.json"))
    ]
    if not found:
        raise SystemExit(f"no packs/*/manifest.json under {root}")
    return found


def kind_of(manifest: dict) -> str:
    """What the pack is: a bundle, or a layer and the dimension it changes."""
    if str(manifest.get("kind", "bundle")) != "layer":
        return "bundle"
    return f"layer:{manifest.get('layer', '?')}"


def badge_url(label: str, message: str, colour: str) -> str:
    return f"https://img.shields.io/badge/{label}-{quote(message, safe='')}-{colour}"


def repo_badges(packs: list[tuple[Path, dict]]) -> list[str]:
    """The badges a repository can make: the count, and the two shared values."""
    specs = {str(manifest.get("specVersion", "")) for _, manifest in packs}
    engines = {str(manifest.get("engine", "")) for _, manifest in packs}
    spec = specs.pop() if len(specs) == 1 else "mixed"
    engine = engines.pop() if len(engines) == 1 else "mixed"
    return [
        f"![packs]({badge_url('packs', str(len(packs)), '6f42c1')})",
        f"![spec]({badge_url('spec', spec, '007ec6' if spec != 'mixed' else 'lightgrey')})",
        f"![engine]({badge_url('engine', engine, '478cbf' if engine != 'mixed' else 'lightgrey')})",
    ]


def pack_rows(packs: list[tuple[Path, dict]]) -> list[str]:
    """One table row per pack; no badge has to speak for all of them."""
    lines = [
        "| Kind | Pack | Version | Spec | Engine |",
        "| --- | --- | --- | --- | --- |",
    ]
    for _, manifest in packs:
        lines.append(
            "| `{}` | `{}` | `{}` | `{}` | `{}` |".format(
                kind_of(manifest),
                manifest.get("id", "?"),
                manifest.get("version", "?"),
                manifest.get("specVersion", "?"),
                manifest.get("engine", "?"),
            )
        )
    return lines


def block_lines(packs: list[tuple[Path, dict]], fold: bool = False) -> list[str]:
    """The badges, then the table, flat or behind a one-click summary."""
    lines = [*repo_badges(packs), ""]
    if fold:
        lines.extend(
            [
                "<details>",
                f"<summary>Packs ({len(packs)})</summary>",
                "",
                *pack_rows(packs),
                "",
                "</details>",
            ]
        )
    else:
        lines.extend(pack_rows(packs))
    return lines


def badge_block(packs: list[tuple[Path, dict]], fold: bool = False) -> str:
    """The marked block `--write` puts in a file and `--check` compares."""
    return "\n".join([BADGE_BEGIN, *block_lines(packs, fold), BADGE_END])


def marked_block(text: str) -> str:
    start = text.find(BADGE_BEGIN)
    end = text.find(BADGE_END)
    if start < 0 or end < 0 or end < start:
        raise SystemExit(f"{BADGE_BEGIN} and {BADGE_END} are not both in the file")
    return text[start + len(BADGE_BEGIN) : end]


def written_rows(text: str) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5 or cells[0] in {"Kind", "---"}:
            continue
        rows[cells[1]] = cells
    return rows


def check_badges(path: Path, packs: list[tuple[Path, dict]]) -> list[str]:
    """Name every pack and field that does not say what its manifest says."""
    found = marked_block(path.read_text(encoding="utf-8"))
    written = written_rows(found)
    fields = ("Kind", "Pack", "Version", "Spec", "Engine")
    problems: list[str] = []
    ids = {str(manifest.get("id", "?")) for _, manifest in packs}
    for _, manifest in packs:
        pack_id = str(manifest.get("id", "?"))
        want = [
            kind_of(manifest),
            pack_id,
            str(manifest.get("version", "?")),
            str(manifest.get("specVersion", "?")),
            str(manifest.get("engine", "?")),
        ]
        if pack_id not in written:
            problems.append(f"the table has no row for {pack_id}")
            continue
        for name, got, expected in zip(fields, written[pack_id], want):
            if got != expected:
                problems.append(
                    f"the {name} row for {pack_id} says {got}; {MANIFEST} says {expected}"
                )
    for pack_id in written:
        if pack_id not in ids:
            problems.append(f"the table has a row for {pack_id}, which no manifest names")
    folded = "<details>" in found
    if folded:
        summary = re.search(r"<summary>Packs \((\d+)\)</summary>", found)
        if not summary:
            problems.append(
                "the block is folded but carries no <summary>Packs (N)</summary>"
            )
        elif int(summary.group(1)) != len(packs):
            problems.append(
                f"the summary says {summary.group(1)} packs; the manifests are {len(packs)}"
            )
    expected = "\n".join(block_lines(packs, folded))
    if not problems and found.strip() != expected.strip():
        problems.append(
            "the block around the table does not match the manifests (badges or spacing)"
        )
    return problems


def write_badges(
    path: Path, packs: list[tuple[Path, dict]], fold: bool | None = None
) -> None:
    """Replace only the marked block; writing twice is a no-op.

    With no explicit choice, the block keeps the shape it already has: a folded
    table stays folded, so a version bump does not silently unfold it.
    """
    text = path.read_text(encoding="utf-8")
    found = marked_block(text)
    if fold is None:
        fold = "<details>" in found
    start = text.find(BADGE_BEGIN)
    end = text.find(BADGE_END)
    updated = text[:start] + badge_block(packs, fold) + text[end + len(BADGE_END) :]
    if updated != text:
        path.write_text(updated, encoding="utf-8", newline="\n")


@contextmanager
def scratch(tag: str) -> Iterator[Path]:
    """A directory this tool removes itself.

    `tempfile.mkdtemp()` stamps the directory with mode 0o700, which on Windows
    replaces the access control entry it would have inherited: under a
    restricted token the creator cannot write inside it and cannot delete it,
    which is exactly what a self-test must never do. This file travels into
    world repositories on its own, so the helper is inline rather than imported.
    """

    base = Path(__file__).resolve().parents[2] / ".test-tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"fixtures-{tag}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    path.mkdir(exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=False)



def write_fixture(directory: Path) -> Path:
    """Write a pack for the self-test, so the tool needs no shipped story."""
    root = directory / "fixture-pack"
    (root / "data").mkdir(parents=True)
    manifest = {
        "id": "fixture-pack",
        "version": "0.1.0",
        "specVersion": "2.0.0",
        "engine": ">=4.7.0 <5.0.0",
    }
    (root / MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "data" / "nodes.json").write_text(
        '{"n1": {"text": "a fixture pack"}}\n',
        encoding="utf-8",
        newline="\n",
    )
    return root


def self_test() -> int:
    """Assert the properties this tool exists for, without touching the network."""
    problems: list[str] = []
    with (
        scratch("source") as source,
        scratch("first") as first,
        scratch("second") as second,
    ):
        root = write_fixture(Path(source))
        one = build(root, Path(first))
        two = build(root, Path(second))
        if one.read_bytes() != two.read_bytes():
            problems.append("two builds of one directory differ")
        if digest(one) != digest(two):
            problems.append("two builds hash differently")
        described = describe(one)
        for field in ("id", "version", "bytes", "sha256", "specVersion", "engine"):
            if not described.get(field):
                problems.append(f"the descriptor has no {field}")
        if described["sha256"] != digest(one):
            problems.append("the descriptor hash is not the file hash")
        if described["bytes"] != one.stat().st_size:
            problems.append("the descriptor size is not the file size")
        sidecar = write_descriptor(one)
        written = json.loads(sidecar.read_text(encoding="utf-8"))
        if written != described:
            problems.append("the sidecar disagrees with the descriptor")
        command = publish_commands(one, "liberalluz/example", "pack/fixture-pack/v0.1.0", False)
        if len(command) != 2:
            problems.append("a missing release does not produce a create and an upload")
        if command[0][:3] != [gh(), "release", "create"]:
            problems.append("the create command is not the first one")
        if command[1][:3] != [gh(), "release", "upload"]:
            problems.append("the upload command is not second")
        if "--clobber" not in command[1]:
            problems.append("the upload command does not replace an artifact")
        if publish_commands(one, "liberalluz/example", "pack/fixture-pack/v0.1.0", True)[0][:3] != [
            gh(),
            "release",
            "upload",
        ]:
            problems.append("an existing release is created again")
        repo = Path(source) / "repo"
        for pack_id, version, kind, layer, engine in [
            ("example", "0.1.0", "bundle", "", ">=4.7.0 <5.0.0"),
            ("second", "0.2.0", "layer", "mod", ">=4.8.0 <5.0.0"),
        ]:
            directory = repo / "packs" / pack_id
            directory.mkdir(parents=True)
            body = dict(read_manifest(root))
            body.update({"id": pack_id, "version": version, "kind": kind, "engine": engine})
            if layer:
                body["layer"] = layer
                body["target"] = "example"
            else:
                body.pop("layer", None)
                body.pop("target", None)
            (directory / MANIFEST).write_text(
                json.dumps(body), encoding="utf-8", newline="\n"
            )
        packs = pack_manifests(repo)
        block = badge_block(packs)
        if "packs-2-6f42c1" not in block:
            problems.append("the packs badge does not count the packs")
        if "spec-2.0.0" not in block:
            problems.append("the spec badge is not the shared spec")
        if "engine-mixed" not in block:
            problems.append("two engine ranges do not make a mixed badge")
        if "| `layer:mod` | `second` | `0.2.0` |" not in block:
            problems.append("the table does not name a layer row")
        readme = Path(source) / "README.md"
        readme.write_text(
            f"# a repository\n\n{BADGE_BEGIN}\nstale\n{BADGE_END}\n",
            encoding="utf-8",
            newline="\n",
        )
        write_badges(readme, packs)
        if check_badges(readme, packs):
            problems.append("a written README does not check")
        once = readme.read_text(encoding="utf-8")
        write_badges(readme, packs)
        if readme.read_text(encoding="utf-8") != once:
            problems.append("writing the table twice changes the README")
        stale = [(path, dict(body, version="9.9.9")) for path, body in packs]
        if not any("Version row for second" in problem for problem in check_badges(readme, stale)):
            problems.append("a version bump is not caught")
        write_badges(readme, packs, fold=True)
        folded = readme.read_text(encoding="utf-8")
        if "<details>" not in folded or "<summary>Packs (2)</summary>" not in folded:
            problems.append("a folded table is not folded")
        if check_badges(readme, packs):
            problems.append("a folded README does not check")
        write_badges(readme, packs)
        if "<details>" not in readme.read_text(encoding="utf-8"):
            problems.append("a version bump unfolds the table")
        write_badges(readme, packs, fold=False)
        if "<details>" in readme.read_text(encoding="utf-8"):
            problems.append("--flat leaves the table folded")
        if check_badges(readme, packs):
            problems.append("a flat README does not check")
        write_badges(readme, packs, fold=True)
        counted = readme.read_text(encoding="utf-8").replace(
            "<summary>Packs (2)</summary>", "<summary>Packs (9)</summary>"
        )
        readme.write_text(counted, encoding="utf-8", newline="\n")
        if not any("summary" in problem for problem in check_badges(readme, packs)):
            problems.append("a stale pack count is accepted")
        one = repo / "packs" / "example"
        if "packs-1-6f42c1" not in badge_block([(one, read_manifest(one))]):
            problems.append("a single pack is not one row and one badge")
        bare = Path(source) / "bare.md"
        bare.write_text("# no markers\n", encoding="utf-8", newline="\n")
        try:
            write_badges(bare, packs)
        except SystemExit:
            pass
        else:
            problems.append("a file without markers is accepted")
        try:
            pack_manifests(Path(source) / "no-packs")
        except SystemExit:
            pass
        else:
            problems.append("a root without packs/ is accepted")
    if problems:
        for problem in problems:
            print(f"[fail] {problem}")
        return 1
    print("[ok] two builds are identical; the descriptor names the bytes; publish uploads both files")
    print("[ok] the pack table follows the manifests; a stale row is refused")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build, hash and publish a pack.")
    commands = parser.add_subparsers(dest="command", required=True)

    build_parser = commands.add_parser("build", help="build a pack directory into a zip")
    build_parser.add_argument("root")
    build_parser.add_argument("--out", default="dist")

    hash_parser = commands.add_parser("hash", help="name the bytes of a built pack")
    hash_parser.add_argument("zip")

    publish_parser = commands.add_parser("publish", help="upload a pack to a release")
    publish_parser.add_argument("zip")
    publish_parser.add_argument("--repo", required=True)
    publish_parser.add_argument("--tag", required=True)
    publish_parser.add_argument("--apply", action="store_true")

    badge_parser = commands.add_parser(
        "badge", help="write a repository's pack table from packs/*/manifest.json"
    )
    badge_parser.add_argument("root", help="repository root holding packs/")
    badge_parser.add_argument(
        "--write", metavar="FILE", help="replace the marked block in this file"
    )
    badge_parser.add_argument(
        "--check", metavar="FILE", help="exit 1 when a row drifts"
    )
    layout = badge_parser.add_mutually_exclusive_group()
    layout.add_argument(
        "--fold",
        dest="fold",
        action="store_const",
        const=True,
        help="put the table behind <details><summary>Packs (N)</summary>",
    )
    layout.add_argument(
        "--flat",
        dest="fold",
        action="store_const",
        const=False,
        help="keep the table flat (the default shape)",
    )
    badge_parser.set_defaults(fold=None)

    commands.add_parser("self-test", help="assert reproducibility and the descriptor")

    args = parser.parse_args(argv)

    if args.command == "build":
        target = build(Path(args.root), Path(args.out))
        print(f"built {target} sha256:{digest(target)}")
        return 0

    if args.command == "hash":
        target = Path(args.zip)
        if not target.is_file():
            raise SystemExit(f"{target} does not exist")
        sidecar = write_descriptor(target)
        described = describe(target)
        print(f"sha256:{described['sha256']} {described['bytes']} bytes")
        print(f"wrote {sidecar}")
        return 0

    if args.command == "publish":
        target = Path(args.zip)
        if not target.is_file():
            raise SystemExit(f"{target} does not exist")
        if not args.apply:
            for command in publish_commands(target, args.repo, args.tag, False):
                print(" ".join(command))
            print("dry run; pass --apply to create the release and upload")
            return 0
        validate(target)
        exists = release_exists(args.repo, args.tag)
        print(f"release {args.tag} {'exists' if exists else 'is missing'}")
        for command in publish_commands(target, args.repo, args.tag, exists):
            print(" ".join(command))
            code = subprocess.run(command, check=False).returncode
            if code != 0:
                print(f"[fail] {command[2]} exited {code}", file=sys.stderr)
                return code
        return 0

    if args.command == "badge":
        packs = pack_manifests(Path(args.root))
        if args.write and args.check:
            raise SystemExit("pass one of --write or --check, not both")
        if args.write:
            write_badges(Path(args.write), packs, args.fold)
            print(f"wrote the pack table of {args.root} into {args.write}")
            return 0
        if args.check:
            problems = check_badges(Path(args.check), packs)
            for problem in problems:
                print(f"[fail] {problem}")
            if problems:
                return 1
            print(f"[ok] {args.check} says what the manifests under {args.root}/packs say")
            return 0
        print(badge_block(packs))
        return 0

    return self_test()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
