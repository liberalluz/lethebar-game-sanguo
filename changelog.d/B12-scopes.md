### Changed

- The scope table now places the two things it could not place: `docs/baselines.md`
  and `docs/baselines/` are `repo` records, as the engine files them, and
  `docs/` no longer claims them.
- A changelog fragment is stated to have no scope of its own: `changelog.d/` is a
  waiting room, and a fragment takes the scope of the commit that earns it.
