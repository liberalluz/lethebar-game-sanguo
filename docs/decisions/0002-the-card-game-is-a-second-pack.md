# ADR-0002 · The card game is a second pack of the same world

Supersedes `ADR-0001`, written the same day. `ADR-0001` decided that
`packs/sanguo-cards` is `kind: "layer"` over `packs/sanguo`. That shape is not
available to us, for reasons the engine had already written down before this
repository existed.

## Context

`ADR-0001` rested on one sentence of `ADR-0013`: the `append` semantic "adds
entries to a declared list (choices, actions, cards, events)". If a card is a
list entry, a layer could give the world a hand of cards and the world would not
have to know.

Three records read together refuse that reading.

- **`ADR-0014`** draws the line at the name: a mod changes, it never adds, and it
  "may not introduce a resource, an action, a card, a rule shape, or a field the
  base package does not have". A card game whose whole point is to introduce
  cards is therefore not a mod.
- **`ADR-0013`** appends to *declared* lists only. `Hand.declared()` in
  `app/core/hand.gd` requires a non-empty deck, so a base with no hand has no
  list to append to. A base that declares a hand it never uses would be a world
  carrying the card game's data and its version bump — which is the thing
  `ADR-0001` was trying to avoid.
- **`ADR-0010`** puts `packs/sanguo-cards/` beside `packs/sanguo-tale/` and
  `packs/sanguo-war/` in the same world repository, at the same level, and calls
  that "the normal case, not an exception".

`ADR-0010` and `ADR-0008` also settle the two questions `ADR-0001` was really
asking: a world repository may ship several genre packs, and a capability is
engine behaviour a package names and never provides. `cards.hand@1` exists.

## Decision

1. **`packs/sanguo-cards` is a bundle.** `kind: "bundle"`, its own `entry`, its
   own `data/cards.json`, `collection: three-kingdoms`, version `0.1.0`. It is a
   whole game about this world, played on its own, not a patch over
   `packs/sanguo`.
2. **`packs/sanguo` is untouched.** It gains no hand, no cards and no reference
   to the card game. There is no `1.1.0` whose only new field exists for a
   package that is not installed.
3. **What the two packs share lives in `shared/`** and is merged in at build
   time: officer tables, place names, glossary. `ADR-0010` says a corrected
   officer number is corrected once; two copies would drift.
4. **A session that plays the world *with* a hand is a later question**, and its
   record is `ADR-0013`'s, not this one's. It needs the base package to declare
   the list, and a world that declares a hand is a world that has decided to
   carry one.
5. **`ADR-0001` is superseded, not amended.** Its reasoning is kept so the next
   person sees why the obvious shape was refused.

### What `ADR-0001` got right

- The card game must not be folded into the tale's bundle. Two genres in one
  archive is two stories that can never be released apart.
- No engine change is needed to start: `cards.hand@1` is a capability
  (`ADR-0008`), and a bundle declares its own hand.
- The save rule it quoted (the assembly is part of the save) is real, but it
  belongs to assembled sessions, and a bundle has none.

### What it got wrong

- It read `kind` as a taxonomy of genres. `ADR-0010` splits `kind` into one of
  three axes — form (`bundle`/`layer`), dimension (`profession`, `genre`, `mod`,
  `content`, `meta`, `assets`), trust — and "a second genre" is a dimension, not
  a form.
- It would have required an engine change that contradicts `ADR-0014`. The
  honest request, if this world ever wants a hand inside the tale, is `append`
  over a list the tale declares, and that request is not this record's.

## Consequences

- **Headless evidence gets simpler.** A bundle is `Session.create(entry)`;
  no `assembly` option, no composition preflight, no `V-33`/`V-34`/`V-35`.
- **The shell still shows no hand.** `app/render/shell.gd:307` and `:596` pass
  `start_counter` and `locale`, and nothing renders `Session.hand_view()`. The
  pack installs, appears on the shelf and runs headless; a player cannot see a
  card yet. That is engine work, and `ADR-0001`'s note about it stands.
- **The collection must agree.** `ADR-0012`'s `W-04` warns when two packs of one
  world disagree on its name; both packs therefore write
  `collection.id = "three-kingdoms"` with the same `names` map.
- **Two packs, two versions, one repository.** `ADR-0010`'s "one version number"
  predates per-pack tags. `docs/specs/git-conventions.md` §5 is the rule we
  follow: the version lives in each pack's manifest, and each pack is tagged
  `pack/<id>/vX.Y.Z` on its own schedule.
- **`shared/` has to become real.** It is empty today, and this record is the
  first one that needs it: the card pack will need officer names it must not
  copy by hand.

## Alternatives considered

- **Keep it a layer and ask the engine to let a layer introduce a hand.**
  Rejected: it asks the engine to contradict `ADR-0014`'s hard line, in order to
  spare this repository one package boundary.
- **Declare an empty hand in `packs/sanguo` so the layer has a list to append
  to.** Rejected here, and recorded as the fallback if this world ever needs the
  hand inside the tale: the tale would ship a field that only a package not
  installed can use, and a player without that package would carry three empty
  piles in every save.
- **One bundle with a mode switch** ("play the tale" / "play the cards").
  Rejected: the tale's data would travel inside the card game's archive, the two
  could not version apart, and `ADR-0013`'s whole point — composing at run time
  rather than at build time — would be undone by hand.
