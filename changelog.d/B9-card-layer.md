### Added

- `docs/decisions/0001`: the card game is a layer package over `sanguo`, not a
  second bundle. The record fixes the package shape, the save rule and the
  version policy before any card data exists.

### Fixed

- The milestone claimed the card work waited on a capability that shipped in
  `v0.3.0`. What is missing is a way for a player to open an assembly; the
  record names the call sites that never pass one.
