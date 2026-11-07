# Software Requirements Specification — `sanguo`

The pack `sanguo` is the Three Kingdoms world for `lethebar`. This document
states what the pack must do. It does not state how the engine implements
turns, saves, or rendering; those belong to the engine's own specifications.

Requirements use stable IDs. A later version may add requirements; it may not
reuse an ID for a different behaviour.

## 1. Scope

A player starts a run, spends a turn on one action, and sees the four
resources move. The run ends after twenty-four turns, or earlier when the
army can no longer be fed, paid, or trusted.

In scope: the pack's data, its declared interface, its text, its two assets,
and the identity that a save depends on.

Out of scope: the engine, the menu, the save format, and the rules that turn a
pack into a running game.

## 2. Terms

| Term | Meaning |
|---|---|
| Pack | The unit the engine installs: one `manifest.json`, `data/`, `assets/` |
| Run | One play-through, from the entry node to an ending |
| Turn | One action spent, one tick of the world clock |
| Rank | The title the run shows at a given turn |
| Resource | A number the run carries: `grain`, `troops`, `coin`, `standing` |

## 3. Functional requirements

**REQ-001 — The pack identifies itself.**
`packs/sanguo/manifest.json` declares `id` `sanguo`, `version` (currently
`1.0.0`), `specVersion` `2.0.0`, `kind` `bundle`, `protocol` `turn_based@1`,
and `entry` `n1`. The `id` never changes: a save key is `save:<id>:<slot>`.

**REQ-002 — A run lasts twenty-four turns.**
`data/phases.json` declares `turns` `24`. No run is shorter or longer by
configuration.

**REQ-003 — Five ranks appear at five turns.**
At turn 1 `校尉`, at 6 `都尉`, at 11 `偏将军`, at 16 `将军`, at 21 `大将军`.
Between those turns the rank of the previous step stays in force.

**REQ-004 — Four resources, with initial values and bounds.**
`grain` starts at 40 within 0–100; `troops` at 30 within 0–100; `coin` at 12
within 0–60; `standing` at 1 within 0–4 and carries five labels, from
`众叛亲离` at 0 to `号令天下` at 4.

**REQ-005 — A run ends when a resource reaches zero.**
`grain`, `troops` or `standing` falling to 0 or below ends the run, and the
ending states why: grain gone, troops scattered, or the lords turned away.
`coin` is not a failure condition; it can reach 0 and the run continues.

**REQ-006 — Five actions, each with a cost and an effect.**
`farm` costs 1 coin and adds 10 grain; `recruit` costs 5 grain and adds 8
troops; `drill` costs 3 grain and adds 3 troops and 1 standing; `envoys` costs
2 coin and adds 1 standing; `patrol` costs 2 troops and adds 4 grain. Costs
apply before effects.

**REQ-007 — Three standing-driven rules fire during a run.**
From turn 12 on, each tick adds 1 grain. While standing is at least 2, the
relation from `cao` to `shao` moves by -5 per evaluation. While standing is at
least 3, the relation from `liu` to `cao` moves by +5.

**REQ-008 — Three factions carry initial relations.**
`shao` toward `cao` is -20, `cao` toward `shao` is -20, `liu` toward `cao` is
30. A relation at or above 60 reads as an ally; at or below -60, as hostile.

**REQ-009 — The run opens at node `n1`.**
`data/nodes.json` contains one node, `n1`, with its opening text and the two
assets bound to the slots `scene` and `audio`. The node declares no choices;
the actions of REQ-006 are what the player spends a turn on.

**REQ-010 — The narrative surface is declared, not implied.**
The manifest declares the story reads in the third person and densely, names
three characters — 曹操 (魏), 袁绍 (盟主), 吕布 (骁将) — and five arc labels at
turns 1, 6, 11, 16 and 21: `初平元年 · 起兵`, `群雄并起`, `中原逐鹿`,
`三分之势`, `天下归心`.

**REQ-011 — The pack says who it is for and how long it takes.**
`meta.audience` is `adults`, `meta.minutes` is 30, and `meta.pitch` carries one
sentence in `zh-CN` and one in `en`.

**REQ-012 — The pack sits in a named world.**
`collection.id` is `three-kingdoms`, with the display names `三国` and
`Three Kingdoms`. The world id is not the pack id and does not change with
the pack.

**REQ-013 — Every visible Chinese string has an English counterpart.**
`defaultLocale` is `zh-CN` and `locales` lists `en`. `data/i18n/en.json`
covers the entry node's text, the five action labels, the five ranks, the five
standing labels and the three failure reasons. Fonts are the engine's; the
pack ships none.

**REQ-014 — A save written by this pack stays readable.**
`saveSchema` is `1`. The pack may add content within this schema; it may not
change the schema, the `id`, or the `entry` without a new decision record and
a new major version.

**REQ-015 — Two assets, declared with their slots.**
`assets/scene.png` is a texture for the slot `scene`; `assets/theme.wav` is
audio for the slot `audio`. Both are declared in the manifest and inside the
zip at the paths the manifest names.

## 4. Constraints

**REQ-016 — The pack is data, not code.**
Nothing in the zip executes. The engine enforces declared sizes, entry count
and compression ratio before it reads anything.

**REQ-017 — The pack uses only capabilities the engine already provides.**
`render.2d@1`, `text@1`, `ledger@1`, `rules@1`, `phases@1`, `menu@1`,
`relations@1`. A new capability would be an engine change, not a pack change.

**REQ-018 — The pack runs on the engines it declares.**
`engine` is `>=4.7.0 <5.0.0`. Raising the floor is allowed when a newer engine
is genuinely needed; widening the ceiling past a major version is not.

**REQ-019 — The build is reproducible.**
Two builds of the same tree produce the same zip bytes, so a reader can check a
download against the published `sha256`.

## 5. Non-goals

- Turn resolution, save encoding, rendering and menu behaviour.
- Loading a pack from inside the running game.
- The card layer and the strategy layer planned for later versions.

## 6. Acceptance

Every requirement above is checked by one or more cases in the test plan. A
requirement with no case is not accepted, and a case that cites no requirement
is not run.
