### Changed

- `infra/tool/batch/batch.py` is the engine's copy. A pull request body now
  comes from `.batch/<id>/pr-body.source.md`; the tool refuses to invent one and
  names the five template sections it wants.
- `CARD_TYPES` is the seven commit types again: `process` is gone, and
  `pr --translations-only` is back.
