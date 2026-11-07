### Fixed

- Publishing a release no longer dies reading the answer to "does this release
  exist". The reply is decoded as UTF-8 with replacement instead of with the
  console code page, so a release body in a language other than English cannot
  raise `UnicodeDecodeError` in the middle of an upload that had already
  succeeded.
