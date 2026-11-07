# ADR-0001 · The card game is a layer over the world, not a second bundle

Superseded by `ADR-0002` on 2026-11-07. `ADR-0014` forbids a mod from
introducing a card, so the card game is a second pack of the world rather than a
layer over the first. The reasoning below is kept as the record of a wrong turn,
because the shape it chose is the one most people propose first.

## Context

`packs/sanguo` ships one thing: a 24-turn campaign, `kind: bundle`, `requires: []`,
whose manifest names no other package. The next genre for this world is a card
game — a hand, a deck, a draw, a discard — and the question is what package shape
it takes.

Two engine releases decide what is possible:

- `cards.hand@1` shipped in **`v0.3.0`** (`B41`, `TC-CARDS-001`): a package
  declares a hand, a deck and its cards, and the engine deals, plays, discards and
  draws them.
- Assembly and layers shipped in **`v0.4.0`** (`ADR-0013`, `REQ-041`–`REQ-043`): a
  session is a base package plus zero or more layers; a layer declares what it
  edits and merges through exactly three semantics — override, append, disable;
  two layers writing one field is refused (`V-35`) rather than resolved by order;
  and the assembly is part of the save.

The constraint from the split is that the engine does not change for us, and this
repository releases per pack: one id, one version in the manifest, one tag
`pack/<id>/vX.Y.Z`, one archive and one descriptor.

## Decision

**`packs/sanguo-cards` is a layer package.** `kind: "layer"`, `layer: "sanguo"`.
It appends cards and actions to declared lists. It does not override the world's
numbers and does not touch `nodes`, `phases`, `entry` or `saveSchema`.

**`packs/sanguo` stays a bundle and never names the layer.** The base does not
know the genre exists; a player who wants the campaign alone keeps what they have.

**The save belongs to the base.** A run of `sanguo` plus `sanguo-cards` writes
under `sanguo` with the assembly recorded in the snapshot, as `ADR-0013` requires.
A save whose layer is no longer installed refuses to load rather than loading
without it — that is inherited, not invented here.

**The layer is versioned on its own.** `0.1.0` while it can only be opened
headless, `1.0.0` when a player can open it. Tag `pack/sanguo-cards/vX.Y.Z`, its
own archive and descriptor.

**Numbers shared by both genres go to `shared/`**, not copied into the layer.

## Consequences

- Two packs to build, hash and release. The per-pack tag, descriptor and release
  machinery already in this repository handles that without change.
- **Playtesting is blocked on the engine, not on the capability.** `Assembly` is
  passed by the caller — `Session.create(entry, {"assembly": [...]})` — and the
  only call sites that pass it are in `app/tests/run_tests.gd`. The interface
  (`app/render/shell.gd:307`, `:596`) creates sessions with `start_counter` and
  `locale` only, so no player can open base plus layer today. M3's acceptance
  therefore needs an engine change — a menu that picks layers, or an entry that
  names them — and that is the maintenance side's decision, not ours.
- Headless verification is possible now: a test-side assembly proves the merge
  and that the cards load, before anything is published.
- Disabling the layer returns the base exactly; the engine tests that comparison.
  A merged bundle could not offer it.

## Alternatives considered

- **Fold the cards into `packs/sanguo`.** Rejected: the campaign and the card game
  would release on one version, a player who wants the campaign would download the
  cards, and there would be no way to run the base alone.
- **A second full bundle that duplicates the world.** Rejected: it is the
  "duplicate a package to make a variant" path `ADR-0013` already rejected — two
  copies of the same numbers, drifting apart.
- **A mod that overrides numbers.** Different goal: that changes the world's
  numbers, it does not add a genre. Those mods have their own record (`ADR-0014`
  on the engine side).
