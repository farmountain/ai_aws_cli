# Execution Constitution — ai_aws_cli

Audience: AI execution agent
Artifact-Class: Constitutional
Concern: Execution bounds and forbidden actions
Authority: Primary

---

## Scope of Permitted Execution

The agent is authorized to:

- Read any file in this repository
- Create, edit, or delete files within the repository structure
- Create new branches and commits (local only, unless explicitly authorized)
- Run tests, linters, build commands, and type checkers
- Request clarification from the human operator at any time

---

## Forbidden Actions

The following actions are forbidden without explicit human confirmation:

| # | Forbidden Action |
|---|---|
| F-01 | `git push --force` to any branch |
| F-02 | `git reset --hard` with uncommitted changes |
| F-03 | Deleting files outside `storage/` without a task explicitly naming the file |
| F-04 | Dropping or truncating database tables |
| F-05 | Running `rm -rf` on any directory that contains committed files |
| F-06 | Publishing or pushing to remote without an explicit commit-gate step |
| F-07 | Installing software globally without task authorization |
| F-08 | Storing secrets, tokens, or credentials in any git-tracked file |
| F-09 | Modifying CI/CD workflows without reading the full file first |
| F-10 | Overwriting governance files with content that weakens their constraints |
| F-11 | Silently swallowing errors — all failures must be logged or surfaced |
