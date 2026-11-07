# Software Design Description — `sanguo`

How the pack is put together, and why each piece is where it is. Requirements
are cited by ID from the SRS; this document does not restate them.

## 1. Shape

A release is one zip:

```text
sanguo.zip
├── manifest.json
├── data/
│   ├── nodes.json
│   ├── actions.json
│   ├── state.json
│   ├── rules.json
│   ├── phases.json
│   ├── factions.json
│   └── i18n/en.json
└── assets/
    ├── scene.png
    └── theme.wav
```

The engine stages a pack into `app/builtin/<id>.zip` and reads it from there.
Nothing outside the zip is needed at run time: no fonts, no shared files, no
scripts.

## 2. Manifest

`manifest.json` is the interface. The fields this pack sets, and why each one
exists:

| Field | Value | Why |
|---|---|---|
| `id` | `sanguo` | The save key is `save:<id>:<slot>`; renaming orphans saves (REQ-001) |
| `version` | `1.0.0` | The pack's own version, independent of the engine's |
| `specVersion` | `2.0.0` | The manifest format this file is written against |
| `kind` | `bundle` | The whole world is in one package, not spread over layers |
| `requires` | `[]` | No other pack has to be installed first |
| `engine` | `>=4.7.0 <5.0.0` | The range the content was written for (REQ-018) |
| `name` / `names` | `三国` / `Three Kingdoms` | Display name per locale; the `id` never changes |
| `defaultLocale` / `locales` | `zh-CN` / `["en"]` | Chinese is the source, English is the overlay (REQ-013) |
| `protocol` | `turn_based@1` | One turn, one act |
| `capabilities` | seven | What the engine must provide (REQ-017) |
| `mechanics` | five | The subset the menu lists |
| `entry` | `n1` | The node a new run opens at (REQ-009) |
| `saveSchema` | `1` | The save payload shape (REQ-014) |
| `assets` | two entries | Path plus slot, so the engine binds them without guessing (REQ-015) |
| `clock` | `{"per": "turn"}` | The world advances per turn, not per second |
| `collection` | `three-kingdoms` | The menu groups worlds, then packs (REQ-012) |
| `content` | view, density, cast, arc | The narrative surface, declared rather than inferred (REQ-010) |
| `meta` | audience, minutes, pitch | What a store page and a menu entry need (REQ-011) |

`kind` is `bundle` and not `layer` because the pack owns a whole world: it
declares its own state, phases and entry. A layer would instead name what it
edits in another pack, which is what the planned card pack will do.

## 3. Data files

| File | Holds | Read for |
|---|---|---|
| `nodes.json` | The opening node `n1`: text, assets, empty choices | The first screen of a run |
| `actions.json` | Five actions: id, label, hint, costs, effects | What a turn can spend |
| `state.json` | Four resources with `init`, `min`, `max`, optional `labels` | The resource bar and its bounds |
| `rules.json` | Three standing-driven rules with `set` and `relations` | What moves without the player acting |
| `phases.json` | `turns`, `ranks`, `fail` | Run length, rank schedule, endings |
| `factions.json` | Three entities with relations, plus `ally` / `hostile` thresholds | How the three lords read each other |
| `i18n/en.json` | Node overlays under the node id, plus a flat `strings` map | Every English string (REQ-013) |

The split is by *who reads it*, not by theme: the engine needs the turn count
before it needs the node text, and a translator needs only the flat `strings`
map.

## 4. The turn as data

The pack does not implement a turn loop; it declares what a turn can contain.

1. The run opens at `n1` with the four resources at their `init` values.
2. The player picks one action; its `costs` are applied, then its `effects`.
3. The rules in `rules.json` evaluate against the new state.
4. The clock ticks; at turn 12 the grain rule starts adding 1 per tick.
5. `phases.json` decides whether the rank changes and whether a failure
   condition has been reached.

Ordering matters and is written down here because two files interact: an action
that spends grain can push grain to 0, and the failure check reads the value
after the action, not before.

## 5. Localisation

Chinese is the source text in the data files themselves. English is an overlay
in `data/i18n/en.json`:

- node text is keyed by node id (`n1`);
- interface strings are flat keys: `action.<id>`, `rank.<turn>`,
  `resource.standing.<value>`, `failure.<index>`.

A key that is missing falls back to the Chinese source rather than to an empty
string, so a half-translated pack reads as Chinese in the gaps instead of
showing holes. This is why REQ-013 asks for coverage rather than for a
mechanism: the mechanism already tolerates gaps.

## 6. Assets

Two files, both declared in the manifest so the engine binds them by slot:

| Path | Type | Slot | Used for |
|---|---|---|---|
| `assets/scene.png` | texture | `scene` | The background of the entry screen |
| `assets/theme.wav` | audio | `audio` | The theme that plays with the scene |

The scene is also listed inside `nodes.json`, because the entry node names the
assets it shows. The manifest entry is what makes them part of the pack; the
node entry is what makes them visible at that moment.

## 7. Build and release

- `infra/tool/release/pack.py build packs/sanguo` sorts entries, pins
  timestamps and puts `manifest.json` first, so two builds are byte-identical
  (REQ-019).
- `pack.py hash` writes `sanguo-1.0.0.json` with `id`, `version`, `bytes`,
  `sha256`, `specVersion` and `engine`.
- The tag is `pack/sanguo/v1.0.0`; the release carries the zip and the
  descriptor. The tag is not moved after publication.

## 8. Known limits

These are true of 1.0.0 and are recorded here rather than fixed silently:

- Faction labels in `factions.json` and the arc labels in `content.arc` are
  Chinese only; they are not covered by `data/i18n/en.json`. The SRS declares
  them as narrative surface (REQ-010) but does not yet require an English
  counterpart.
- `meta.minutes` is declared but the menu does not read it yet.
- `meta.audience` is validated by the engine but nothing filters on it.
- A pack cannot be installed from inside the running game; the zip is placed by
  the tooling that stages `app/builtin/`.

## 9. Why not

- **Not a layer.** The card pack planned for later is a layer because it edits
  a world that already exists. This pack is the world itself.
- **No code.** Anything that needed code would be an engine change; the pack
  stays data (REQ-016).
- **No fonts.** The engine provides them; shipping a font would both bloat the
  pack and take on a licence obligation for no gain.
- **No second changelog.** Fragments in `changelog.d/` are consumed at release;
  a `CHANGELOG.md` alongside them would drift.
