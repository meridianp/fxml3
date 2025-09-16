---
title: 'Git Commit Task'
read_only: true
type: 'command'
---

# Create new git commit task

- First stages ALL changes using `git add -A`, then suggests a commit message, ALWAYS asks for confirmation, and creates the commit ONLY after explicit approval
- Shows what files will be staged before proceeding

## Alternative Usage

If you want to stage files selectively instead of all changes:
1. Stage your files manually before running this task: `git add <files>`
2. Then tell me: "commit with staged files only"
3. I will skip the `git add -A` step and use only your pre-staged files
- Format of commit message depends on the affected files:
  - For package/module changes:
    - JavaScript/TypeScript packages (e.g., apps/graphql): `[package1,package2] description of changes`
    - Python modules (e.g., src/api, lib/utils): `[module1,module2] description of changes`
    - Frontend components: `[frontend] description of changes`
    - Backend services: `[backend] description of changes`
  - For configuration files in root or specialized directories:
    - Python configs:
      - requirements.txt: `[deps] description of changes`
      - setup.py/pyproject.toml: `[build] description of changes`
      - pytest.ini/.coveragerc: `[test] description of changes`
      - .flake8/.pylintrc/ruff.toml: `[lint] description of changes`
    - JavaScript/TypeScript configs:
      - package.json: `[deps] description of changes`
      - ESLint config: `[eslint] description of changes`
      - TypeScript config: `[typescript] description of changes`
      - Webpack/Vite config: `[build] description of changes`
    - General configs:
      - Docker files: `[docker] description of changes`
      - CI/CD files (.github, .gitlab-ci): `[ci] description of changes`
      - Git-related files: `[git] description of changes`
      - Claude related files (e.g., CLAUDE.md or .claude folder): `[claude] description of changes`
      - Database migrations: `[db] description of changes`
      - API specs (OpenAPI/Swagger): `[api] description of changes`
    - Other root configs: use appropriate descriptor in square brackets
  - For functionality spanning multiple languages/packages: use the functionality name as scope
  - Golden rule: Use package/module names for specific changes, otherwise use functionality/directory scope
  - If 80% or more changes are focused on a single feature/functionality, mention only the main package(s) and ignore minor related changes
  - Description should start with lowercase letter
  - Description should be concise and explain what was changed
  - Commit messages should be based on all files that will be staged/committed
- Always provide at least 5 message options in a numbered list; I will choose one or request a different option
- The scope in square brackets should be consistent across all suggested message options - it's a fixed rule based on the files changed, not something to vary between options
- When suggesting commit messages, use `git log -n 100 --oneline` to review the most recent commit messages for inspiration on format and style
- First run `git status` to show current repository state
- If there are no changes (staged or unstaged), abort the process with a message in red text: "No changes to commit. Aborting."
- Stage all changes using `git add -A` and show what files are being staged
- Display staged files in a clear format before proceeding
- If staging results in no changes (all files ignored), abort with appropriate message
- Format the suggested commit messages in orange text to make them more readable in the terminal
- NEVER proceed with `git commit -m` without explicit confirmation from me first
- Only after I explicitly confirm or modify the commit message, proceed with `git commit -m "message"`
- If I tell you that you can push the changes, you can run `git push` directly without asking for permission
- Do NOT add Claude co-authorship footer to commits
- Read ONLY the files that will be staged/committed

## Workflow

1. **Check Repository Status**: Run `git status` to see current state
2. **Show Unstaged Changes**: Display all files that will be staged
3. **Confirm Staging**: Ask "Stage all these files? (yes/no)" - abort if no
4. **Stage All Changes**: Execute `git add -A` to stage all changes
5. **Verify .gitignore**: Ensure no ignored files are being staged accidentally
6. **Display Staged Files**: Show a clear list of what will be committed
7. **Analyze Changes**: Review the staged files to determine appropriate commit scope
8. **Suggest Commit Messages**: Provide at least 5 commit message options based on the staged files
9. **Wait for Confirmation**: User must explicitly choose or modify a commit message
10. **Create Commit**: Only after approval, execute `git commit -m "chosen message"`
11. **Optional Push**: If user requests, execute `git push`

## Safety Features

- Always shows exactly what files will be committed before proceeding
- Warns if staging a large number of files (>20)
- Highlights any new untracked files being added
- Checks for common sensitive files (e.g., .env, secrets, private keys)

## Examples of Good Commit Messages

### JavaScript/TypeScript Examples
- `[ui] fix username retrieval issues in Header component on initial render`
- `[frontend] add responsive design to dashboard components`
- `[api,auth] implement JWT refresh token mechanism`
- `[build] update webpack configuration for production optimization`

### Python Examples
- `[api] add rate limiting middleware to REST endpoints`
- `[models] refactor User model with proper validation`
- `[tests] add unit tests for payment processing module`
- `[utils] implement async file upload handler`

### Full Stack Examples
- `[backend,frontend] integrate websocket support for real-time updates`
- `[db] add migration for user preferences table`
- `[docker] optimize container sizes for production deployment`
- `[ci] add automated testing for Python and JavaScript code`

## Usage Examples

### Standard Usage (stages all changes):
```
User: commit
Assistant:
1. Checking repository status...
2. The following files will be staged:
   - src/api/users.py (modified)
   - src/api/auth.py (new file)
   - tests/test_users.py (modified)
   - .env.example (new file)

   Stage all these files? (yes/no)
User: yes
Assistant:
3. Staging all changes with git add -A...
4. Files staged successfully.
5. Suggesting commit messages...
   [Choose one of the 5 suggestions]
```

### Selective Staging Usage:
```
User: git add src/api/users.py
User: commit with staged files only
Assistant:
1. Using pre-staged files only...
2. The following files will be committed:
   - src/api/users.py (modified)
3. Suggesting commit messages...
   [Choose one of the 5 suggestions]
```

## Precommit Checks

- Precommit checks run after staging files but before the commit action
- Only run precommit checks that meet their triggering conditions based on the staged files
- If any precommit check fails, immediately abort the entire process
- Display an error message and do not proceed until the issue is fixed
- After fixing issues, you'll need to run the commit task again (files will be re-staged)

### Precommit Check: Python Code Quality

- **Trigger Condition**: When editing any Python (.py) files
- **What to Check**:
  - Run appropriate linter if configured (flake8, pylint, or ruff)
  - Check for proper type hints if mypy is configured
  - Verify code follows PEP 8 standards
  - Check for missing docstrings in public functions/classes
- **Specific Checks**:
  - If `.flake8`, `.pylintrc`, or `ruff.toml` exists, use the corresponding tool
  - If `mypy.ini` or `pyproject.toml` with mypy config exists, check type hints
  - Look for Python code guidelines in `./.claude/code-guidelines/python.md` if it exists
- **Failure Action**:
  - Abort the commit process and display detailed error message
  - Show specific linting errors or style violations
  - Suggest fixes for common issues

### Precommit Check: JavaScript/TypeScript Code Quality

- **Trigger Condition**: When editing any JavaScript (.js, .jsx) or TypeScript (.ts, .tsx) files
- **What to Check**:
  - Verify ESLint compliance if `.eslintrc*` exists
  - Check TypeScript compilation if `tsconfig.json` exists
  - Validate against code guidelines if present
- **Specific Checks**:
  - For TypeScript files (.ts): Validate against guidelines in `./.claude/code-guidelines/typescript.md` if it exists
  - For React files (.tsx, .jsx): Validate against React guidelines in `./.claude/code-guidelines/react.md` if it exists
  - Run `npm run lint` or `yarn lint` if script is defined in package.json
- **Failure Action**:
  - Abort the commit process and display detailed error message
  - Show the specific guideline(s) being violated
  - Suggest fixes for common violations

### Precommit Check: GraphQL Schema Validation (Optional)

- **Trigger Condition**: When editing GraphQL files (.graphql, .gql) or GraphQL-related code
- **What to Check**:
  - Verify schema validity
  - Check for corresponding validation schemas for mutations/queries
  - Ensure proper authorization checks for ID parameters
- **Note**: This check only runs if GraphQL is detected in the project
- **Failure Action**:
  - Abort the commit process and display detailed error message
  - Suggest appropriate fixes based on the GraphQL setup

### Precommit Check: Test Coverage (Optional)

- **Trigger Condition**: When editing source code files and test configuration exists
- **What to Check**:
  - For Python: Check if pytest is configured and tests pass
  - For JavaScript: Check if Jest/Mocha/other test framework is configured and tests pass
  - Verify test coverage doesn't decrease significantly
- **Note**: Only runs if test configuration is detected
- **Failure Action**:
  - Warn about failing tests but allow proceeding with explicit confirmation
  - Show which tests are failing and why

### Precommit Check: Dependencies Security

- **Trigger Condition**: When editing dependency files (requirements.txt, package.json, etc.)
- **What to Check**:
  - For Python: Run `pip-audit` or `safety check` if available
  - For JavaScript: Run `npm audit` or `yarn audit` if available
  - Check for known vulnerabilities in dependencies
- **Failure Action**:
  - Warn about security issues but allow proceeding with explicit confirmation
  - List specific vulnerabilities found

### Precommit Check: Format Validation

- **Trigger Condition**: When code formatters are configured
- **What to Check**:
  - For Python: Check Black/autopep8 formatting if configured
  - For JavaScript: Check Prettier formatting if configured
  - Verify consistent code formatting
- **Failure Action**:
  - Suggest running the formatter but don't block commit
  - Show which files need formatting
