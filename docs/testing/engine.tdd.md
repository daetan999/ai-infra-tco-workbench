# Deterministic finance engine TDD evidence

## Source and user journey

The guarantees were derived from the finance-engine task rather than a separate plan file. As an
infrastructure decision maker, I need the same bounded assumptions to produce the same auditable
TCO, unit economics, ROI, payback, sensitivity, confidence, and lineage outputs without a network
dependency or financial guarantee.

## RED and GREEN evidence

- Initial RED: `python3 -m pytest -o addopts='' -q tests/test_engine.py` failed during collection
  with `ModuleNotFoundError: No module named 'app.domain'`. The test contract was preserved in
  checkpoint commit `e62df3f` after a shared-index commit race.
- Initial GREEN: `/tmp/tco-venv-1/bin/python -m pytest -o addopts='' -q
  tests/test_engine.py` passed 16 tests. Implementation checkpoint: `19dfd17`.
- Sensitivity RED: the focused regression command produced three expected failures, proving that
  growth varied only proposed TCO, low utilization could become zero, and zero utilization passed
  validation. Regression checkpoint: `5c5c9e1`.
- Final GREEN: `/tmp/tco-venv-1/bin/python -m pytest -o addopts='' -q
  tests/test_engine.py` passed 19 tests. Fix checkpoint: `a958826`.

## Test specification

| Guarantee | Test type | Result |
|---|---|---|
| Annual compute, storage, network, energy, staffing, transition, growth, and TCO formulas round explicitly | Unit | PASS |
| Training, inference, and productive-accelerator-hour unit costs use recurring cost and return unavailable for zero workload denominators | Unit | PASS |
| Savings, productivity value, net value, ROI, payback, and non-positive-benefit behavior remain distinct and deterministic | Unit | PASS |
| Utilization, price, growth, and energy sensitivities are ordered and recalculate the affected states | Unit | PASS |
| Frozen results, copied inputs, stable repeated results, source confidence, and output lineage preserve auditability | Unit | PASS |
| Invalid bounds and booleans fail fast while the public adapter returns JSON-serializable data | Boundary/integration | PASS |

## Coverage and quality

`/tmp/tco-venv-1/bin/python -m pytest -o addopts='' -q tests/test_engine.py
--cov=app.domain --cov=app.engine --cov-report=term-missing --cov-branch
--cov-fail-under=80` passed 19 tests at 93% branch-aware coverage. Ruff passes for `app/domain.py`,
`app/engine.py`, and `tests/test_engine.py`. Both production files remain below 800 lines and every
function remains below 50 lines.

The final integrated run had 39 passing and 6 failing tests at 95% total coverage. The six failures
were outside the finance-engine ownership boundary (demo fixture values, schema validation, and
unfinished frontend assets/contracts); the real-engine route integration passed.
