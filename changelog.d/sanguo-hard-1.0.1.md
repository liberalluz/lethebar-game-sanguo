### Fixed

- `sanguo-hard` no longer declares the `en` locale. The engine refused the
  package before reading it: a declared locale must fill every node and every
  label, and the table carried one action string, so `V-22` stopped the install.
- `sanguo-hard` is `1.0.1`; `1.0.0` never reached a player, only a draft release.
