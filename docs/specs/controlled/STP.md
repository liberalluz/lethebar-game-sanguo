# Software Test Plan

What this repository tests, how, and what it leaves to another repository.
`SRS.md` says what the packs must do; `SDD.md` says how they are built; this
plan says how a claim in either gets checked.

## Scope

In scope: the packages under `packs/` — their manifests, their data, the
archive the build produces, and what a person sees after installing it in the
engine.

Out of scope: the engine itself. Turn order, save format, layer merging and the
menu are the engine's behaviour, with its own test suite in `lethebar`. A case
here may say "install it in an engine checkout and look", but it never asserts
about engine code.

## Levels

| Level | Question it answers | How it runs |
| --- | --- | --- |
| Static | Does the archive have the shape the engine accepts? | `check_pack.py` over a built zip |
| Data | Do the numbers in the JSON match the SRS? | Read the file, compare a field |
| Build | Would two people get the same bytes? | Build twice, compare sha256 |
| Install | Does the engine take this package? | A person installs it |
| Play | Does it play the way the SRS says? | A person plays turns |

The first three are mechanical and repeatable by anyone with the repository.
The last two are human and produce a screenshot; that is deliberate — the
engine's own suite proves the engine works, not that this package tells the
story it advertises.

## Environments

- Engine: a checkout at the commit named in the batch record, run with Godot
  4.7.2 or served as the web build the engine ships.
- Build: Python 3.14, repository checked out at the batch's base commit.
- Install: a browser with the engine's "install from zip" surface, or the
  desktop build's package list.

## Entry and exit

A case may only run once the pack's bytes are frozen for that batch — the build
that a release will ship, not a working tree. A case passes when its exit
column in `STD.md` holds, and the evidence is a command output kept in the batch
directory or a screenshot kept in the record.

The suite exits when every `REQ-` in `SRS.md` is covered by at least one case
and no case is left `TBD`. Coverage is checked, not trusted:
`check_verification.py docs/specs/controlled/SRS.md docs/specs/controlled/STD.md`.

## Test areas

| Area | Prefix | Covers |
| --- | --- | --- |
| Identity | `TC-IDN-` | the manifest fields a save and a shelf depend on |
| Run | `TC-RUN-` | turns, ranks, the end conditions |
| Resources | `TC-RES-` | starting values, bounds, actions, standing rules, relations |
| Narrative | `TC-NAR-` | entry node, content block, meta, collection, translation |
| Package | `TC-PKG-` | assets, envelope, capabilities, engine range, reproducibility |
| Install | `TC-INS-` | a person installs the archive |
| Play | `TC-PLY-` | a person plays and the numbers move as specified |
| Layer | `TC-LAY-` | a layer archive keeps the same envelope and declares its target |
| Release | `TC-REL-` | the published asset is the built asset |

## What is deliberately not tested

- The engine's turn order, save format and layer merge semantics. They are
  covered by `lethebar`'s suite; repeating them here would test the other
  repository.
- Localisation rendering, fonts and layout. The engine draws; a case only says
  the strings exist.
- Load and size beyond the envelope. `check_pack.py` enforces the limits the
  engine enforces; a case does not measure timing.

## Traceability

`SDD.md` names, for each requirement, the file that carries it. `STD.md` names,
for each case, the requirements it covers and how to repeat it. A batch's exit
record cites the cases it ran; a baseline freezes the documents, not the runs.
