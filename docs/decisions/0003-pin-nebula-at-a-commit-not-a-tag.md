# ADR-0003 · Pin Nebula at a commit, not a tag

**Status:** accepted, 2026-11-08.

## Context

`AGENTS.md` in the Nebula repository says a project pins a version instead of
following `main`, and `.nebula-skills.json` is where the pin lives. The upstream
tree has exactly one tag, `v0.3.0` (`05795e5`, 2026-11-06), and nineteen commits
after it. We installed from the upstream checkout, so our pin reads
`v0.3.0-19-g51742b8` — `git describe` output, which is a tag plus a distance,
not a tag.

The tempting reading is that we should go back to `v0.3.0`. It does not survive
contact with the tools. The `v0.3.0` tree's `batch.py` is 1570 lines and has no
`--body-from`, no `pause`, no `resume`, no `release_checks`, no
`--allow-over-budget`, and `v0.3.0` has no `data` stack at all. Pinning to it
would undo the batch tool the engine runs (B6) and the scaffold we now depend on
(the `data` component that produced `shared/` and `packs/`).

The installer offers no `--ref` or `--tag` switch: `install.py` computes the
version with `git describe --tags --always --dirty` and writes that string. A
pin can only be chosen by checking out a different commit in the source and
reinstalling.

## Decision

We pin `51742b8`, the upstream HEAD at the time of writing, and we record that
the pin is a **commit**, not a tag. The pin stays where the installer wrote it;
we do not hand-edit `.nebula-skills.json`, because a hand-edited pin would claim
a version the installed files do not come from.

Reinstalling follows the same rule: `install.py --agent dsh --scope project
--workspace . --force`. Without `--force` the installer only rewrites the
manifest version and leaves every file alone, which produces exactly the lie
this ADR is trying to avoid.

## What changes this decision

The day upstream publishes a tag whose tree we actually use, we reinstall from
that tag and the pin becomes the tag name. The condition is not "a tag exists"
— `v0.3.0` exists — but "the tagged tree carries the tools this repository
runs". Until then, the commit is the honest pin.

Two consequences to keep in mind:

- A commit pin is invisible to a reader who only sees `v0.3.0-19-g51742b8`. The
  batch records name the commit in prose where it matters (B13 swapped
  `batch.py` from that tree).
- When upstream publishes a tag we want, the switch is a reinstall and a new
  batch, not an edit in place: the tools changed, so the gate that accepted
  them last time has to look again.
