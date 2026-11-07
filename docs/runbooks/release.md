# Cutting a release

Two things are released from this repository and they do not share a version
number. A pack release gives a player a file to install; a repository release
gives the tooling a coordinate. The conventions behind this are in
`docs/specs/git-conventions.md` section 5.

Run every command from the repository root.

## A pack

There is one pack today, `sanguo`. A second pack follows the same steps with its
own id.

1. Bump the version in `packs/<id>/manifest.json`. Nothing else in the manifest
   changes with a release.
2. Write one fragment, `changelog.d/<batch>-<slug>.md`, with its notes under
   `### Added`, `### Changed`, `### Fixed` or `### Removed` and nothing else.
3. Check the fragments parse:

   ```text
   python infra/tool/release/release.py --root . --check
   ```

4. Fold them into the changelog, naming the stream:

   ```text
   python infra/tool/release/release.py --root . --write --stream sanguo        --version vX.Y.Z --date YYYY-MM-DD
   ```

5. Build the artifact twice and compare the hashes — the build pins timestamps
   and sorts entries, so two runs must agree:

   ```text
   python infra/tool/release/pack.py build packs/sanguo
   python infra/tool/release/pack.py hash dist/sanguo.zip
   ```

6. Commit, open the pull request, merge. The tag goes on `main`, not on the
   branch.
7. Tag and push:

   ```text
   git tag -a pack/<id>/vX.Y.Z -m "<id> X.Y.Z - <one line>"
   git push origin pack/<id>/vX.Y.Z
   ```

8. Draft the player-facing notes outside this repository, in
   `lethebar-game-sanguo-docs`: `product/release-notes/<pack>-vX.Y.Z.en.md`, with
   the translation beside it as `<pack>-vX.Y.Z.md`.
9. Create the release with those notes, then upload:

   ```text
   gh release create pack/<id>/vX.Y.Z --title "<id> X.Y.Z" --notes-file <notes>
   python infra/tool/release/pack.py publish dist/sanguo.zip        --repo liberalluz/lethebar-game-sanguo --tag pack/<id>/vX.Y.Z --apply
   ```

10. Run the six preflight checks against the published release:

    ```text
    python infra/tool/release/preflight.py --pack packs/sanguo         --repo liberalluz/lethebar-game-sanguo --tag pack/<id>/vX.Y.Z
    ```

11. Download both files again and compare the zip's sha256 with the descriptor.
    A release nobody re-downloaded is a release nobody checked.
12. Freeze the record in `lethebar-game-sanguo-docs` under
    `records/<YYYY-MM>-release-<pack>-vX.Y.Z/`: the notes copy, `release.json`,
    and a row in the index.
13. A person installs the zip in the engine and plays a few turns. That is the
    only proof that the pack works; the gate proves the bytes.

## The repository

No artifact, no GitHub Release, no notes file.

1. Write the fragment(s) for what changed in the tooling.
2. Fold them:

   ```text
   python infra/tool/release/release.py --root . --write --stream repo        --version vX.Y.Z --date YYYY-MM-DD
   ```

3. Commit, open the pull request, merge.
4. Tag and push:

   ```text
   git tag -a repo/vX.Y.Z -m "repo X.Y.Z - <one line>"
   git push origin repo/vX.Y.Z
   ```

`0.1.0` is the first repository version. A patch fixes a check, a minor adds
one, and a major is reserved for a change in the layout itself.
