```markdown
# ai-infra-tco-workbench Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill teaches you the core development patterns, coding conventions, and workflows used in the `ai-infra-tco-workbench` Python project. The repository is focused on backend and frontend development for AI infrastructure Total Cost of Ownership (TCO) analysis, with a strong emphasis on modular code, clear documentation, and robust testing.

You will learn:
- How to follow the project's coding standards
- How to implement new features or update existing ones
- How to maintain and extend both backend and frontend code
- How to write and run tests
- How to update documentation and supporting assets

---

## Coding Conventions

**File Naming**
- Use `camelCase` for filenames.
  - Example: `demoData.py`, `testEngine.py`

**Import Style**
- Use relative imports within modules.
  - Example:
    ```python
    from .engine import CalculationEngine
    from .repository import Repository
    ```

**Export Style**
- Use named exports (explicitly define what is exported).
  - Example:
    ```python
    __all__ = ["CalculationEngine", "Repository"]
    ```

**Commit Messages**
- Follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) with these prefixes: `feat`, `docs`, `fix`, `test`, `refactor`.
  - Example: `feat: add GPU cost calculation to engine`

---

## Workflows

### Backend Feature Implementation and Test
**Trigger:** When you want to add a new backend feature or extend existing backend logic.  
**Command:** `/new-backend-feature`

1. Edit or create backend modules:
   - `app/domain.py`
   - `app/engine.py`
   - `app/demo_data.py`
   - `app/exports.py`
   - `app/repository.py`
   - `app/routes.py`
   - `app/schemas.py`
2. Add or update corresponding test files:
   - `tests/test_engine.py`
   - `tests/test_demo_data.py`
   - `tests/test_exports.py`
   - `tests/test_repository.py`
   - `tests/test_routes.py`
   - `tests/test_schemas.py`
3. Ensure all tests pass before committing.

**Example:**
```python
# app/engine.py
class CalculationEngine:
    def calculate_tco(self, config):
        # ...implementation...

# tests/test_engine.py
def test_calculate_tco():
    engine = CalculationEngine()
    result = engine.calculate_tco(sample_config)
    assert result["total"] > 0
```

---

### Frontend Interface and E2E Update
**Trigger:** When you want to implement or modify frontend features or workflows.  
**Command:** `/update-frontend-interface`

1. Edit static frontend files:
   - `static/app.js`
   - `static/styles.css`
   - `templates/index.html`
2. Update or add end-to-end tests:
   - `tests/e2e/workbench.spec.js`
3. Update contract tests if interface changes:
   - `tests/test_interface_contract.py`
4. Verify that all tests pass.

**Example:**
```js
// static/app.js
function updateTcoDisplay(value) {
  document.getElementById('tco-value').textContent = value;
}

// tests/e2e/workbench.spec.js
test('TCO updates on input', async ({ page }) => {
  await page.fill('#input-cost', '5000');
  await page.click('#calculate-btn');
  await expect(page.locator('#tco-value')).toHaveText('5000');
});
```

---

### Documentation and Evidence Update
**Trigger:** When you want to document new features, update methodology, or add portfolio evidence.  
**Command:** `/update-docs`

1. Edit documentation files:
   - `README.md`
   - `docs/methodology.md`
   - `docs/architecture.md`
   - `docs/guardrails.md`
2. Add or update assets:
   - `docs/assets/*.svg`
   - `docs/assets/*.png`
   - `docs/examples/*.pdf`
3. Optionally update CI/CD workflow files:
   - `.github/workflows/ci.yml`
4. Commit with a `docs:` or `chore:` prefix.

**Example:**
```markdown
# Methodology

This document describes the calculation methodology for TCO analysis...
```

---

## Testing Patterns

- **Backend tests:** Python test files in `tests/` (e.g., `tests/test_engine.py`)
- **Frontend E2E tests:** Playwright tests in `tests/e2e/` (e.g., `workbench.spec.js`)
- **Contract/interface tests:** Python files like `tests/test_interface_contract.py`
- **Test file naming:** Use `*.spec.js` for E2E, `test_*.py` for Python tests

**Example E2E Test:**
```js
// tests/e2e/workbench.spec.js
test('loads dashboard', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('h1')).toHaveText('TCO Workbench');
});
```

---

## Commands

| Command                   | Purpose                                                      |
|---------------------------|--------------------------------------------------------------|
| /new-backend-feature      | Start a new backend feature or extend backend logic           |
| /update-frontend-interface| Implement or modify frontend features and update E2E tests    |
| /update-docs              | Update documentation, methodology, or supporting evidence     |
```
