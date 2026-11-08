# Changelog

## sanguo-hard v1.0.1 - 2026-11-08

### Added
- `packs/sanguo-hard`, a mod layer over `sanguo`: grain is capped at 25, `levy` trades standing for coin, and `patrol` leaves the menu.

### Fixed
- `sanguo-hard` no longer declares the `en` locale. The engine refused the package before reading it: a declared locale must fill every node and every label, and the table carried one action string, so `V-22` stopped the install.
- `sanguo-hard` is `1.0.1`; `1.0.0` never reached a player, only a draft release.

## repo v0.2.0 - 2026-11-08

### Added
- `check --release` runs the release self-test, so an ordinary check stays fast and the tool that cuts a release is proved before a release.

### Changed
- The card game is recorded as a second bundle of this world: `ADR-0002` replaces `ADR-0001`, which `ADR-0014`'s rule against introducing a card refuses, and which `ADR-0013`'s append-only-to-declared-lists rule leaves with nothing to append to.
- `ADR-0001` keeps its reasoning: its title now says it was superseded, so the next reader meets the wrong turn and the reason together.
- The scope table now places the two things it could not place: `docs/baselines.md` and `docs/baselines/` are `repo` records, as the engine files them, and `docs/` no longer claims them.
- A changelog fragment is stated to have no scope of its own: `changelog.d/` is a waiting room, and a fragment takes the scope of the commit that earns it.
- The batch tool is the Nebula release's file: batches can pause, resume and abort without leaving a branch behind, and a commit title is checked against the rule the scaffold carries.

### Fixed
- The checks build their fixtures under `.test-tmp` instead of a sandbox directory that mode 0o700 makes undeletable.

## repo v0.1.0 - 2026-11-07

### Added
- `infra/tool/release/preflight.py`: the six checks a package passes between `gh release create` and the upload — manifest, version and contract, artifact, descriptor, release, and one real fetch of the asset. Ported from the engine with the decode the release probe learned in B4.
- `docs/runbooks/release.md`: the release path in the order it is run, for the pack and for the repository.
- `release.py --stream`: a section is composed under `## <stream> vX.Y.Z`, so the package and the tooling no longer count versions in the same line.
- `infra/checks/check_pack.py` reads the archive a pack publishes to: only `manifest.json` at the root, only `data/`, `assets/` and `i18n/` below it, no executable suffix, no symlink, no absolute path, no `..`, and the six manifest fields with their patterns.
- `pack-envelope` runs that checker's self-test on every batch.
- `translation` is the fourth gate check: a body edited after its translation was prepared is refused, and the check says which file moved.
- `docs/decisions/0001`: the card game is a layer package over `sanguo`, not a second bundle. The record fixes the package shape, the save rule and the version policy before any card data exists.

### Changed
- `CHANGELOG.md` now carries two streams: `## sanguo v1.0.0` for the package and `## repo v0.1.0` for everything that only touches this repository.
- The conventions list six scopes and describe both streams and both tag shapes.
- `infra/tool/batch/batch.py` is the engine's copy. A pull request body now comes from `.batch/<id>/pr-body.source.md`; the tool refuses to invent one and names the five template sections it wants.
- `CARD_TYPES` is the seven commit types again: `process` is gone, and `pr --translations-only` is back.

### Fixed
- Publishing a release no longer dies reading the answer to "does this release exist". The reply is decoded as UTF-8 with replacement instead of with the console code page, so a release body in a language other than English cannot raise `UnicodeDecodeError` in the middle of an upload that had already succeeded.
- The batch tool counts scope and budget against the merge base with the base branch, so a batch that is planned again no longer inherits the lines of work that merged after it started.
- A card that declares a skill has to show what the skill changed, in `.batch/<id>/evidence/skills/`, before the batch can reach a pull request.
- A pull request could ship a Chinese half that described an earlier version of the English half, because nothing compared the body against the one that was translated.
- The milestone claimed the card work waited on a capability that shipped in `v0.3.0`. What is missing is a way for a player to open an assembly; the record names the call sites that never pass one.

## sanguo v1.0.0 - 2026-11-07

### Added
- The Three Kingdoms pack ships as version `1.0.0`: one `sanguo.zip` and one `sanguo-1.0.0.json`, both attached to the `pack/sanguo/v1.0.0` release.
- The descriptor names the bytes: id, version, byte count, sha256, specVersion and the engine range the pack needs.

### Changed
- The version in `packs/sanguo/manifest.json` is `1.0.0` instead of `0.1.0`. Data, assets, locales and every other manifest field are the ones the engine shipped before this repository existed.
