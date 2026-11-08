### Changed

- The batch tool is the Nebula release's file: batches can pause, resume and
  abort without leaving a branch behind, and a commit title is checked
  against the rule the scaffold carries.

### Fixed

- The checks build their fixtures under `.test-tmp` instead of a sandbox
  directory that mode 0o700 makes undeletable.

### Added

- `check --release` runs the release self-test, so an ordinary check stays
  fast and the tool that cuts a release is proved before a release.
