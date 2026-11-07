### Added

- `translation` is the fourth gate check: a body edited after its translation was
  prepared is refused, and the check says which file moved.

### Fixed

- A pull request could ship a Chinese half that described an earlier version of
  the English half, because nothing compared the body against the one that was
  translated.
