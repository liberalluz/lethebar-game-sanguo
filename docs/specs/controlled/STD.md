# Software Test Design

One row per case. The table is the machine-readable part — `check_verification.py`
reads it, and its second column is the only place coverage is counted from. The
sections after it say how a person repeats each case.

## Cases

| Test | Covers | Exit |
| --- | --- | --- |
| `TC-IDN-001` | REQ-001, REQ-014 | `packs/sanguo/manifest.json` reads `id: sanguo`, `kind: bundle`, `entry: n1`, `protocol: turn_based@1`, `saveSchema: 1` |
| `TC-RUN-001` | REQ-002 | `data/phases.json` declares 24 turns and the status line reports "24" on turn 1 |
| `TC-RUN-002` | REQ-003 | The five rank boundaries in `phases.json` are turns 1, 6, 11, 16, 21 |
| `TC-RUN-003` | REQ-005 | `data/rules.json` ends the run at zero grain, zero troops or zero standing, and does not end it at zero coin |
| `TC-RES-001` | REQ-004 | `data/state.json` starts grain 40, troops 30, coin 12, standing 1, with bounds 0–100, 0–100, 0–60, 0–4 |
| `TC-RES-002` | REQ-006 | `data/actions.json` has five actions, each with a cost and an effect, and the cost applies before the effect |
| `TC-RES-003` | REQ-007 | `data/rules.json` carries the three standing rules: +1 grain per turn from turn 12, −5 cao→shao at standing 2 or more, +5 liu→cao at standing 3 or more |
| `TC-RES-004` | REQ-008 | `data/factions.json` starts shao→cao −20, cao→shao −20, liu→cao 30, with ally at 60 and hostile at −60 |
| `TC-NAR-001` | REQ-009 | `data/nodes.json` opens at `n1`, and turn 1 shows that node's text and its choices |
| `TC-NAR-002` | REQ-010 | The manifest's `content` block declares view, density, cast and arc |
| `TC-NAR-003` | REQ-011 | The manifest's `meta` carries a pitch in both languages, `audience: adults` and `minutes: 30` |
| `TC-NAR-004` | REQ-012 | The manifest's `collection` is `three-kingdoms`, and the shelf lists the pack under that world |
| `TC-NAR-005` | REQ-013 | Every Chinese string a player can see has an English key in `data/i18n/en.json`; the language check reports no missing key |
| `TC-PKG-001` | REQ-015 | The manifest declares two assets, slots `scene` and `audio`, and both files are in the archive |
| `TC-PKG-002` | REQ-016 | `check_pack.py` accepts the archive: no code, only `data/`, `assets/`, `i18n/` and the manifest at the root |
| `TC-PKG-003` | REQ-017 | Every id in `capabilities` is one the engine lists as provided |
| `TC-PKG-004` | REQ-018 | The declared `engine` range contains the engine used in the install case |
| `TC-PKG-005` | REQ-019 | Two builds of the same tree are byte-identical — same sha256, same size in the descriptor |
| `TC-INS-001` | REQ-001, REQ-017, REQ-018 | A person installs `sanguo.zip` in the engine and the pack appears under Three Kingdoms |
| `TC-PLY-001` | REQ-002, REQ-003, REQ-005 | A person plays nine turns: the rank advances at turn 6, no resource reaches zero, and the run does not end early |
| `TC-LAY-001` | REQ-016 | The content layer archive passes `check_pack.py`, declares `kind: layer`, `layer: content`, `target: sanguo` |
| `TC-LAY-002` | REQ-016 | The mod layer archive passes `check_pack.py`, declares `kind: layer`, `layer: mod`, `target: sanguo`, and changes nothing until a player ticks it |
| `TC-REL-001` | REQ-019 | The published asset downloads back with the sha256 and size the descriptor names |

## How to repeat each case

The mechanical cases begin with the same three commands, run from the
repository root at the batch's base commit:

```text
python infra/tool/release/pack.py build packs/<id> --out dist
python infra/checks/check_pack.py dist/<id>.zip
python infra/tool/release/pack.py hash dist/<id>.zip
```

- **Identity, run, resources, narrative** — read the named JSON file and compare
  the fields the exit column lists. These cases assert about data, so no engine
  is involved.
- **Package envelope** — `check_pack.py` prints `the envelope holds` or names the
  entry that broke a rule.
- **Reproducibility** — build into two output directories and compare the two
  `sha256` values; the tool stamps a fixed timestamp and sorts entries, so any
  difference is a real difference.
- **Install and play** — a person downloads the asset from the release page,
  installs it through the engine's own surface, and sends a screenshot. Two
  screenshots close the case: the pack listed after install, and a turn in which
  the numbers moved.
- **Layer cases** — the same envelope check over the layer's own archive, then a
  play case with the layer ticked and one with it left unticked.
- **Release** — download the asset from the release page and compare its sha256
  with the descriptor the release carries.

## Evidence

A command case keeps its output in `.batch/<id>/evidence/<name>.log`. A human
case keeps its screenshots beside the exit record. An exit record cites the case
ids it ran; a record without a case id says `none` and why.
