---
name: project-review
description: Technical and analytical review workflow for the Telegram AI assistant project. Use after implementing new functionality, before final handoff for feature work, or when the user asks to review changes for bugs, architectural risks, plan conformance, project norms, documentation consistency, tests, and operational readiness.
---

# Project Review

Use this skill as a review pass after feature work. Do not make code changes during
the review pass unless the user asks to fix findings or the defect is trivial and
clearly within the current task.

After a review pass on behavior-changing work, follow with `project-doc-sync` to
update the plan and durable documentation.

## Required Context

Read the relevant project documents before reviewing:

- `AGENTS.md`
- `docs/PLAN.md`
- `docs/INTENT_MANAGER.md` when intent routing, context, LLM calls, or task routing changed
- `docs/REMINDERS.md` when reminder behavior changed
- `docs/MEMORY.md` when long-term memory concepts changed
- touched source files and tests

Also inspect:

- `git status --short`
- `git diff --check`
- `git diff --stat`
- the actual diff for changed code and docs

## Review Priorities

Review in this order:

1. **Correctness and regressions**
   - Find bugs, broken flows, missing state transitions, wrong DB queries, async/session issues, and behavior that contradicts existing tests or docs.
   - Pay special attention to Telegram webhook flow, reminders, callback handling, intent routing, and DB state.

2. **Plan conformance**
   - Compare the implementation against `docs/PLAN.md`.
   - Separate completed, partially completed, and not implemented plan items.
   - Do not mark a plan item complete if the behavior is only scaffolded.

3. **Project norms**
   - No local NLP through keyword lists, phrase dictionaries, or regex rules for user meanings, intents, pronouns, or semantic references.
   - Use intent-manager, structured domain entities, explicit contracts, or separate LLM resolvers for semantic interpretation.
   - Keep `user_intent_states` as pending clarification state, not a global assistant mode.
   - Keep reminders grounded in database data for lists/history.
   - Do not commit secrets, `.env`, token payloads, OAuth payloads, cookies, or DB dumps.

4. **Context safety**
   - Check that context is neither starved nor over-broad.
   - Reminder creation must not hallucinate from old conversation history.
   - If context is used to resolve references like "его", it must be explicit, bounded, and fail safely.

5. **Tests and operations**
   - Check whether tests cover the risky paths.
   - Verify commands that matter for the changed area. Prefer:
     - `python3 -m compileall services/assistant/app services/assistant/tests`
     - `docker compose exec -T assistant pytest tests`
     - `docker compose exec -T assistant ruff check app tests`
     - `docker compose exec -T assistant ruff format --check app tests`
     - `curl -fsS https://order.mrhellko.ru/health`
   - If a check cannot be run, state why and the residual risk.

## Output Format

Use a code-review stance.

Start with findings ordered by severity:

- `High`: likely data loss, security issue, production outage, or major broken user flow.
- `Medium`: behavioral bug, plan mismatch, missing safety boundary, or important missing test.
- `Low`: maintainability issue, minor mismatch, unclear docs, or small test gap.

For each finding include:

- severity;
- file and line reference;
- concrete failure mode;
- suggested direction, not necessarily a full patch.

Then include:

- **Plan Status**: done / partial / not done for the relevant plan items.
- **Checks**: commands run and results.
- **Residual Risk**: short list of risks that remain after the review.

If there are no findings, say so explicitly and still mention test gaps or residual risks.

Keep the review concise. Do not repeat large diffs or project history.
