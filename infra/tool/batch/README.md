# Project-local batch execution

Optional, project-local execution layer for the implementation stage. It is not
a core Nebula skill and is only installed when bootstrap is called with
`--with-execution`.

The tool is stack-agnostic. It owns the state machine:

```text
plan -> approve -> start -> check -> pr -> merge
```

A stage skill or the project itself provides the checks and provider commands
through `infra/tool/batch/config.json`; `batch.py` only runs commands, reads exit
codes, and writes evidence.

## Files

```text
infra/tool/batch/
  batch.py       state machine
  config.json    project-owned commands and defaults
  README.md      this file
.batch/          local state and evidence; never commit
```

## Commands

```bash
python infra/tool/batch/batch.py plan --from ../<project>-docs/process/batches/B8.md
python infra/tool/batch/batch.py approve B8 --confirm <hash8>
python infra/tool/batch/batch.py start B8
python infra/tool/batch/batch.py check B8
python infra/tool/batch/batch.py pr B8 --prepare
python infra/tool/batch/batch.py pr B8 --create --confirm <body-hash8>
python infra/tool/batch/batch.py merge B8 --pr 123 --yes
python infra/tool/batch/batch.py adopt B1 --from ../<project>-docs/process/batches/B1.md
python infra/tool/batch/batch.py status B8
```

`plan --from` reads the single external Markdown card and writes a snapshot to
`.batch/<id>/card.json`. The snapshot records the source path and the SHA-256 of
the raw Markdown bytes. `approve` binds both hashes; `start`, `check`, and `pr`
re-read the source and refuse a changed card. A card edit therefore requires a
new approval.

`plan --goal` is only for a dated ad-hoc investigation; it is not a planning
card and cannot become one later. `adopt` records an old B1–B7 card as a
read-only legacy snapshot; it never invents approval or scope.

## Gates

`check` runs four gates before the configured commands:

- **scope**: every changed path must match `allowed` and none may match
  `forbidden`.
- **budget**: added plus deleted lines, measured against the card base, must not
  exceed `size_budget`. Untracked files count by line; binary files are reported
  but not counted.
- **changelog**: every declared fragment must exist under `changelog.d/`, be
  changed by this batch, and be non-empty. `feat`/`fix` must declare one when
  the project has `changelog.d/`.
- **skills**: every declared non-stage skill must be installed under
  `.agents/skills`, `.claude/skills`, `.codex/skills`, `.codebuddy/skills`, or
  `.workbuddy/skills`. Stage skills are rejected when the card is registered.

A failing gate stops the configured commands and leaves the batch in
`check_failed`. The exit record still has to record the actual
`applied`/`partial`/`skipped` status of each skill.

## Configuration

`config.json`:

```json
{
  "base": "main",
  "branch_prefix": "batch/",
  "scope": {"ignore": [], "generated": []},
  "checks": [
    {
      "name": "test",
      "command": ["python", "-m", "pytest"],
      "cwd": ".",
      "timeout": 600
    }
  ],
  "pr_create": ["gh", "pr", "create", "--title", "{title}", "--body-file", "{body}"],
  "merge": ["gh", "pr", "merge", "{pr}", "--merge"]
}
```

- `checks`: commands run by `check`; each writes `evidence/<name>.log`.
  `cwd` is relative to the project root.
- `pr_create` / `merge`: optional provider hooks. Placeholders:
  `{id}`, `{title}`, `{body}`, `{branch}`, `{root}`, `{pr}`.
- `scope.ignore`: paths ignored by scope checks; `.batch/` is always ignored.
- `scope.generated`: generated paths ignored by scope checks, kept separate
  from hand-written ignores so a project can review the stack's output.
- Empty hooks mean the tool stops at `pr --prepare` or reports that merge must
  be done externally.
- `--with-execution` fills `checks`/`scope` from the selected stack's
  `execution.yaml`; it never overwrites an existing `config.json`.

## Boundaries

- It does not decide whether a change should be batched.
- It does not know Flutter, Swift, or any other stack.
- It does not replace review or human merge approval.
- It does not store records or release notes.
- The project owns `config.json`; bootstrap does not overwrite it on re-run.
