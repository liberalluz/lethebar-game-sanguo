### Added

- `.github/workflows/gate.yml` builds and checks every pack on a push or a pull
  request, and uploads a tagged pack only when its release already exists.
- `README.md` and `README.zh-CN.md` carry the marked pack table, written by
  `pack.py badge`.

### Changed

- `infra/tool/release/pack.py`, `infra/checks/check_pack.py` and the new
  `infra/checks/fixtures.py` are the v0.7.5 files, so the archive is judged by
  the release the guide names.