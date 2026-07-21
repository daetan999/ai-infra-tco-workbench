---
name: frontend-interface-and-e2e-update
description: Workflow command scaffold for frontend-interface-and-e2e-update in ai-infra-tco-workbench.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /frontend-interface-and-e2e-update

Use this workflow when working on **frontend-interface-and-e2e-update** in `ai-infra-tco-workbench`.

## Goal

Updates frontend interface files and synchronizes end-to-end and contract tests.

## Common Files

- `static/app.js`
- `static/styles.css`
- `templates/index.html`
- `tests/e2e/workbench.spec.js`
- `tests/test_interface_contract.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit static frontend files (static/app.js, static/styles.css, templates/index.html)
- Update or add end-to-end tests (tests/e2e/workbench.spec.js)
- Update contract tests if interface changes (tests/test_interface_contract.py)

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.