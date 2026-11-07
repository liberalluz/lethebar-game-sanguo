# Security

## Reporting

Do not open a public issue for a vulnerability. Contact the maintainer privately
with:

```text
affected version (the tag, e.g. pack/sanguo/v1.0.0)
the file or release that is affected
reproduction
impact
suggested fix
```

## Handling

- Acknowledgment within a reasonable time.
- Fix in a private branch, release, then disclose.
- A withdrawn release is never re-uploaded under the same tag: the tag stays
  where it is and a new version carries the fix.
- Never commit credentials, signing material, or customer data.

## What counts as a security issue here

This repository ships data, not code: a manifest, seven JSON files and two
assets, published as `sanguo.zip` plus a descriptor. The engine treats a pack as
untrusted input and never executes code found inside it, so the risks are
different from a program's:

- **A tampered release.** `sanguo.zip` whose sha256 does not match the
  `sanguo-<version>.json` published beside it. Verify before reporting; if they
  match, the report is about content, not transport.
- **A malicious or broken pack.** A change that makes the engine crash, hang, or
  write outside the save slot `save:sanguo:<slot>`. Path traversal in `assets`,
  an entry that loops forever, or a save that will not reload belongs here.
- **An asset we had no right to ship.** Art or audio that reproduces someone
  else's work. Tell us the original and we replace it or withdraw the release.
- **A leaked credential.** Nothing in this repository needs one; if a token or
  key appears in a commit, treat it as compromised.

## Package envelope

A pack is data, never code. The engine enforces the limits (declared sizes,
entry count, compression ratio) in `app/core/package_limits.gd` before it reads
anything, and records what it installed so a reloaded run reads the way it read
before. If the engine accepted a pack it should have refused, report it in
[this repository's issues](https://github.com/liberalluz/lethebar-game-sanguo/issues)
with the pack attached: when the cause turns out to be the loader rather than
the pack, we carry it to [lethebar](https://github.com/liberalluz/lethebar/issues)
ourselves.
