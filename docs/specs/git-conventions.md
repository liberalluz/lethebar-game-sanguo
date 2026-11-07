# Git conventions

One-page defaults. Change this file when the team changes the rule.

## 1. Branches

```text
main                 long-lived, protected
feat/<topic>         user-visible feature
fix/<topic>          bug fix
process/<topic>      process/tooling only
```

- One branch = one change.
- Delete the branch after merge.

## 2. Commits

```text
<type>(<scope>): <subject>
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`.
Scopes: pick exactly one from the closed list below.

| Scope | Covers |
|---|---|
| `pack` | A pack's content: `packs/*/manifest.json`, its `data/` and `assets/` |
| `shared` | Material more than one pack uses: `shared/` |
| `docs` | Specs, decisions, intent and runbooks under `docs/` |
| `repo` | Repository conventions and records: `README`, `CONTRIBUTING`, `SECURITY`, `NOTICE`, `CHANGELOG.md`, `docs/specs/git-conventions.md`, `.gitignore` |
| `infra` | This repository's own tooling: `infra/checks/`, `infra/tool/` |

- One scope per commit, no second level. `docs(srs)` is not allowed; write
  `docs(docs): add a decision record`.
- The scope follows what the change is about, not where the file sits:
  `git-conventions.md` lives in `docs/` but its changes are `repo`.
- Adding a scope means editing this table first, in the same pull request as its
  first use.

- Subject is imperative and short.
- Body explains why, not what.
- The body carries two labelled lines, checked by `infra/checks/check_commit_body.py`:
  - `Why:` is required: one or more lines saying what problem the commit solves.
    Without it the reason for a change lives only in the pull request, which is a
    different document.
  - `Batch:` is required: `Batch: B3` when the commit implements a batch card,
    `Batch: none` when it does not. The card is the thing that decides scope, so
    the link belongs in history.
- The check reads only the commits a branch adds (`origin/main..HEAD`). It never
  rewrites or rejects merged history, so commits that predate the rule stay
  exactly as they are.
- No secrets, no generated build output.
- The body is plain text. A commit message is never rendered, so backticks,
  `**bold**` and `__bold__` reach the reader as characters: write `kind`, not
  `` `kind` ``. `check_commit_body.py` refuses all three outside a fenced block.
- Every paragraph is wrapped at 72 columns. A message is read in a terminal, in
  `git log` and in the commit list of a pull request, and none of them re-flow a
  line. `pr_merge.py --body-only` flattens what it writes: inline code and bold
  lose their markers and every paragraph is filled at 72 columns before it
  reaches `gh pr merge --body-file`.
- A squash merge makes a commit that no branch precedes, so the range check above
  cannot see it: the commit sits on the default branch and `origin/main..HEAD` is
  empty. After merging, judge that one commit directly with
  `python infra/checks/check_commit_body.py --ref origin/main` and
  `python infra/tool/merge/pr_merge.py --verify-only --ref origin/main`. Both read
  a single commit and apply the same rules.
- Detail like the above belongs in this file, not in `CONTRIBUTING.md`: that
  file is the door, and a rule copied into two places drifts in one of them.

## 3. Pull requests

- One PR = one behavior.
- Fill the PR template.
- Link the issue or record if one exists.
- Required checks must be green.
- Do not rewrite history after review unless asked.

## 4. Merge

- Squash merge by default.
- A squashed commit takes its subject from the branch commit, so the subject stays
  English and the PR title stays in the PR. Do not change the repository merge
  settings to route PR titles into `main`.
- Do not pass the subject by hand. `gh pr merge --squash` without `--subject` keeps
  the branch subject and appends `(#<number>)`, which `pr_merge.py --verify-only`
  requires; a hand-written `--subject` drops that suffix and leaves a commit on
  `main` that names no pull request.
- Pass the body on its own: `infra/tool/merge/pr_merge.py --body-only --pr <n>
  --out <file>` writes what goes into `--body-file`, and `--show` without `--out`
  writes the whole message for reading. Handing the whole message to `--body-file`
  puts the subject on the first body line as well. Redirecting the output through
  a shell pipe decodes UTF-8 as the local code page and turns every character
  outside ASCII into U+FFFD; `--out` writes the file from Python and has no such
  step.
- The author does not self-approve.
- No direct push to `main`.
- A failed check is fixed, not bypassed.

## 5. Release

- Version lives in the pack's manifest, `packs/<id>/manifest.json`; the tag and the
  published files are derived from it.
- Tag: `pack/<id>/vX.Y.Z`. The `v` appears only in the tag, so the descriptor and
  the manifest both say `"version": "X.Y.Z"`.
- One release, two files: `<id>.zip` and `<id>-X.Y.Z.json`, attached to the same
  release. The descriptor carries the sha256 of the zip, which is the only thing a
  reader can check the download against.
- Two records are written at a release, and neither is hand-counted.
  `CHANGELOG.md` is the merged record: `python infra/tool/release/release.py
  --root . --write --version vX.Y.Z --date YYYY-MM-DD` folds every fragment in
  `changelog.d/` into one section and deletes only the fragments it consumed.
  The release body is written for a player instead — what this version is, how
  to install it, what the hash is — and it is written in the source language,
  English. It is drafted outside this repository, in `lethebar-game-sanguo-docs`
  under `product/release-notes/<pack>-vX.Y.Z.en.md`, with the translation beside
  it as `<pack>-vX.Y.Z.md`（仓外，需另行检出）. What a release leaves behind is a
  frozen copy of that English file plus a release record — tag, both commit
  hashes, provider, body source, pack sha256 — in
  `records/<YYYY-MM>-release-<pack>-vX.Y.Z/`.
- A tag is not moved once it is pushed.
