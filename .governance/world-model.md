# World Model — ai_aws_cli

Audience: AI reasoning agent
Artifact-Class: World Model
Concern: Operational truth — entities, locations, invariants

---

## System Identity

| Attribute | Value |
|---|---|
| Project name | ai_aws_cli |
| Governance model | Spec-driven; OpenSpec change control |
| Runtime language | (set by project) |
| Repository | `D:\all_projects\ai_aws_cli\ai_aws_cli` |

---

## Source-of-Truth Table

| Concern | Source | Authority |
|---|---|---|
| Reasoning conduct | `CLAUDE.md` | Primary |
| Execution bounds | `AGENT.md` | Primary |
| What exists and where | This file | Canonical |

---

## Invariants

| ID | Invariant |
|---|---|
| INV-01 | `storage/` is listed in `.gitignore` and contains no committed files |
| INV-02 | No secrets or credentials in git-tracked files |
