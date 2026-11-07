### Fixed

- The batch tool counts scope and budget against the merge base with the base
  branch, so a batch that is planned again no longer inherits the lines of work
  that merged after it started.
- A card that declares a skill has to show what the skill changed, in
  `.batch/<id>/evidence/skills/`, before the batch can reach a pull request.
