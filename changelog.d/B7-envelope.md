### Added

- `infra/checks/check_pack.py` reads the archive a pack publishes to: only
  `manifest.json` at the root, only `data/`, `assets/` and `i18n/` below it, no
  executable suffix, no symlink, no absolute path, no `..`, and the six manifest
  fields with their patterns.
- `pack-envelope` runs that checker's self-test on every batch.
