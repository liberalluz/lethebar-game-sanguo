# Baselines

| ID | Anchor | Frozen | Scope | Hashes | Detail | Known gap |
|---|---|---|---|---|---|---|
| BL-1 | `bf76a88` | 2026-11-07 | Controlled specs at `1.0.0`: `SRS`, `SDD` and their `zh-CN` translations | `docs/baselines/BL-1.files.json` | Four files, `sha256`, one entry each. The SRS fixes the nineteen behaviours the pack has as shipped (`REQ-001`–`REQ-019`); the SDD fixes its shape, its turn order, its localisation rules and the four limits it does not remove | `STP` and `STD` do not exist yet, so no test case is frozen: nothing here says the pack is correct, only that these four files are what it must keep. The pack's own bytes are covered by `sanguo-1.0.0.json` and not by this baseline. The tag `pack/sanguo/v1.0.0` is written in B3 against a later commit, so this anchor stays at `bf76a88`, the commit that introduced the specs |
