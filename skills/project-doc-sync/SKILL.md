---
name: project-doc-sync
description: Documentation and plan synchronization workflow for behavior-changing updates in this assistant project. Use after `project-review` when application behavior changed, or when project docs, plan, and durable repo rules need to be brought back in sync.
---

# Project Doc Sync

Use this skill after a `project-review` pass for changes that alter application behavior.

## Required Context

Read the relevant material before editing docs:

- `AGENTS.md`
- `docs/PLAN.md`
- `docs/INTENT_MANAGER.md` when routing or context behavior changed
- `docs/REMINDERS.md` when reminder behavior changed
- `docs/MEMORY.md` when memory behavior changed
- `docs/WEB_SEARCH.md` when search behavior changed
- `README.md` for user-facing capability summaries
- touched code and tests

Also inspect:

- `git status --short`
- `git diff --check`
- `git diff --stat`
- the actual diff for code and docs

## What To Update

Keep documentation honest and minimal:

- update `docs/PLAN.md` for status changes and current scope;
- update the domain doc that matches the behavior change;
- update `README.md` only when the change affects user-facing capability summaries or setup;
- update `AGENTS.md` only for durable repo rules or recurring workflows;
- add a dedicated doc when a behavior is now substantial enough to deserve one.

## Rules

- Do not mark a plan item complete if the implementation is still scaffolded.
- Do not repeat code details in multiple docs unless there is a user-facing reason.
- Keep links current and prefer one canonical doc per feature area.
- Do not add local keyword heuristics or other banned semantic shortcuts in docs.

## Output

- list the docs changed and why;
- mention any docs intentionally left untouched;
- call out any residual mismatch between code and docs.
