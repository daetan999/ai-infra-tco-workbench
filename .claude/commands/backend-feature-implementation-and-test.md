---
name: backend-feature-implementation-and-test
description: Workflow command scaffold for backend-feature-implementation-and-test in ai-infra-tco-workbench.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /backend-feature-implementation-and-test

Use this workflow when working on **backend-feature-implementation-and-test** in `ai-infra-tco-workbench`.

## Goal

Implements or extends backend features and adds/updates corresponding tests.

## Common Files

- `app/domain.py`
- `app/engine.py`
- `app/demo_data.py`
- `app/exports.py`
- `app/repository.py`
- `app/routes.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit or create backend modules (e.g., app/domain.py, app/engine.py, app/demo_data.py, app/exports.py, app/repository.py, app/routes.py, app/schemas.py)
- Add or update corresponding test files (e.g., tests/test_engine.py, tests/test_demo_data.py, tests/test_exports.py, tests/test_repository.py, tests/test_routes.py, tests/test_schemas.py)

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.