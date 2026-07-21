---
name: documentation-and-evidence-update
description: Workflow command scaffold for documentation-and-evidence-update in ai-infra-tco-workbench.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /documentation-and-evidence-update

Use this workflow when working on **documentation-and-evidence-update** in `ai-infra-tco-workbench`.

## Goal

Updates documentation, methodology, and supporting evidence/assets.

## Common Files

- `README.md`
- `docs/methodology.md`
- `docs/architecture.md`
- `docs/guardrails.md`
- `docs/assets/tco-comparison.png`
- `docs/assets/tco-dashboard.png`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit documentation files (docs/methodology.md, docs/architecture.md, docs/guardrails.md, README.md)
- Add or update assets (docs/assets/*.svg, docs/assets/*.png, docs/examples/*.pdf)
- Optionally update CI/CD workflow files (.github/workflows/ci.yml)

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.