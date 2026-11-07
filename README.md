# lethebar-game-sanguo

English · [简体中文](README.zh-CN.md)

> The Three Kingdoms world for Lethebar: its story, its numbers, its art.
> The rules that play it stay in the engine; this repository only carries what
> the world is.

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Pack](https://img.shields.io/badge/pack-sanguo-c0392b.svg)](packs/sanguo/manifest.json)
[![Engine](https://img.shields.io/badge/engine-%3E%3D4.7.0%20%3C5.0.0-478cbf.svg)](https://github.com/liberalluz/lethebar)

## Status

**`pack/sanguo/v1.0.0` is released.** A run is 24 turns long. It opens at the
first call to arms and ends at the fifth rank; three resources decide whether it
ends early — grain, troops and standing, any one of them at zero.

Known limits, all of them the engine's and none of them fixed here: faction names
and arc stage names are Chinese text that does not follow the interface language;
a pack's stated length is collected but not yet shown in the menu; the audience
is validated but nothing filters on it; pictures and sound are drawn into one
band and one portrait column, and only from PNG, JPEG and WAV.

## What it is

- **A world, not an engine.** `data/` says what happens, `assets/` says what it
  looks like and sounds like, `manifest.json` says how the two are packed. The
  turn loop, the rank ladder and the fail conditions are the engine's
  `app/core`; a world that needed to change them would be asking for an engine
  change, not a pack change.
- **One pack, one id.** `sanguo` is the pack id and it never changes: saves are
  keyed `save:sanguo:<slot>`, so renaming it would orphan every player's save.
- **A bundle, not a layer.** All six layers — data, text, art, numbers, menu
  entry, narrative declaration — ship in this one package. A later pack
  (`sanguo-cards`, v0.7.0, still unwritten) will stack on top as a `layer`;
  nothing in this one has to move for that to work.
- **Data a reader can diff.** Every file is plain JSON or a single asset. A
  balance change is a one-line diff, reviewable without running the game.

## Install

The release carries two files: `sanguo.zip` and `sanguo-1.0.0.json`. A build
stages the zip into the engine's `app/builtin/`, which is the only place the
loader reads a package from; the descriptor is what a player hashes the zip
against. Verify before staging:

```bash
sha256sum sanguo.zip
```

The descriptor carries the same value in `sha256`; the two check each other.

Installing a pack from inside the game is not part of this release. The engine
ships its own packs, and this one reaches a build through staging.

## What's in the pack

| Path | Holds |
|---|---|
| `manifest.json` | `id`, `version`, `specVersion`, `engine`, `protocol`, `capabilities`, `entry`, `saveSchema`, `assets`, `meta`, `content` |
| `data/nodes.json` | The scenes a turn can open |
| `data/actions.json` | What a player can do, and what each choice costs |
| `data/state.json` | The four resources and their starting values |
| `data/rules.json` | What a choice is allowed to change |
| `data/phases.json` | 24 turns, five ranks at turns 1 / 6 / 11 / 16 / 21, three fail conditions |
| `data/factions.json` | The three houses that carry the run |
| `data/i18n/en.json` | The English overlay for every visible Chinese string |
| `assets/scene.png` | The scene band |
| `assets/theme.wav` | The theme |

The manifest declares `protocol: turn_based@1` — one turn does one thing — and
seven capabilities (`render.2d@1`, `text@1`, `ledger@1`, `rules@1`, `phases@1`,
`menu@1`, `relations@1`). It declares no new capability; a pack that needed one
would be asking the engine to grow it first.

## The world

Third person, dense, three names on screen: Cao Cao of Wei, Yuan Shao the
coalition's leader, and Lü Bu the spearman. The arc has five stages —
初平元年 · 起兵, 群雄并起, 中原逐鹿, 三分之势, 天下归心 — and the line under the
text changes as the run crosses each one. Faction names and stage names are
package text, in Chinese, and do not follow the reader's language yet.

## Commands

| Command | What it does |
|---|---|
| `python infra/tool/merge/pr_merge.py --self-test` | Assert the message rules the merge tool enforces |
| `python infra/checks/check_commit_body.py --ref origin/main` | Judge the merged commit's message against §2 of the conventions |

There is no CI yet.

## Project structure

| Directory | Responsibility |
|---|---|
| `packs/` | One directory per pack, named exactly as its `id`: `packs/sanguo/` |
| `shared/` | Material several packs will use; empty until the second pack needs something |
| `docs/` | Specs, decisions, intent ([docs/README.md](docs/README.md)) |
| `infra/` | The repository's own tooling, laid out as the engine lays out its own: `checks/` and `tool/merge/` |

There is no `app/`: the engine's code is not here.

## Documentation

| Looking for | Where |
|---|---|
| Why this exists | [docs/intent/](docs/intent/) |
| How it should be | [docs/specs/](docs/specs/) |
| What was decided and rejected | [docs/decisions/](docs/decisions/) |

Where a document goes: how it should be → `specs/`; decided or not →
`decisions/`; why → `intent/`; how to operate → `runbooks/`.

## Contributing

- Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.
- Changing content with AI? Read [CONTRIBUTING.ai.md](CONTRIBUTING.ai.md) too: AI
  changes need a human reviewer plus evidence, and the author cannot
  self-approve.
- A balance change is easier to argue with numbers than with prose: paste the
  before and after of the entry into an issue.

## Security

See [SECURITY.md](SECURITY.md). A pack is untrusted input to the engine, and a
release is only as good as the hash published beside it.

## License

This world is licensed under the [Apache License 2.0](LICENSE): commercial use
and redistribution are allowed, provided copyright notices and [NOTICE](NOTICE)
are kept. The engine that plays it is licensed separately, in its own
repository.
