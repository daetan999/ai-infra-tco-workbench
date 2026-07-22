```markdown
# ai-infra-tco-workbench Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches the core development patterns and conventions used in the `ai-infra-tco-workbench` Python codebase. You'll learn about file naming, import/export styles, commit message conventions, and how to write and run tests. While no specific automation workflows were detected, this guide provides suggested commands to streamline common tasks.

## Coding Conventions

### File Naming
- Use **camelCase** for file names.
  - Example: `dataProcessor.py`, `modelRunner.py`

### Import Style
- Use **relative imports** within the codebase.
  - Example:
    ```python
    from .utils import calculateCost
    from ..core import infraManager
    ```

### Export Style
- Use **named exports** (i.e., explicitly define what is exported from a module).
  - Example:
    ```python
    # In infraManager.py
    def startInfra(): ...
    def stopInfra(): ...
    __all__ = ["startInfra", "stopInfra"]
    ```

### Commit Message Convention
- Use **Conventional Commits** with the `feat` prefix for new features.
- Keep commit messages concise (average 42 characters).
  - Example: `feat: add cost calculation module`

## Workflows

### Creating a New Feature
**Trigger:** When adding new functionality  
**Command:** `/create-feature`

1. Create a new Python file using camelCase naming.
2. Write your code, using relative imports for internal modules.
3. Export functions or classes using named exports.
4. Write a commit message starting with `feat:` and a short description.
5. (Optional) Add or update tests.

### Refactoring Existing Code
**Trigger:** When improving or restructuring code  
**Command:** `/refactor-code`

1. Identify the module or function to refactor.
2. Update code, maintaining camelCase file naming and relative imports.
3. Ensure all exports are explicitly named.
4. Test your changes.
5. Commit with a message like `feat: refactor [module] for clarity`.

## Testing Patterns

- Test files follow the pattern `*.test.ts`.
- The specific testing framework is **unknown**; check existing test files for structure.
- To write a test:
  - Create a file like `moduleName.test.ts`.
  - Follow the structure of existing tests.
- Example test file name: `dataProcessor.test.ts`

## Commands

| Command           | Purpose                                 |
|-------------------|-----------------------------------------|
| /create-feature   | Scaffold a new feature module           |
| /refactor-code    | Start a code refactor workflow          |
| /run-tests        | Run all test files in the codebase      |
| /check-exports    | Verify all modules use named exports    |
| /check-imports    | Ensure all imports are relative         |

```