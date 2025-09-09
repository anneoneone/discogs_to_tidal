# Pre-commit Setup

This project uses [pre-commit](https://pre-commit.com/) hooks to ensure code quality and consistency before commits.

## What Pre-commit Does

Pre-commit automatically runs the following checks before each commit:

### Code Formatting & Style
- **Black**: Formats Python code consistently (88 character line length)
- **isort**: Sorts imports in the correct order
- **flake8**: Checks for PEP 8 style violations and common errors

### Type Checking
- **mypy**: Basic type checking for the main source code (with relaxed settings)

### General Quality
- **trailing-whitespace**: Removes trailing whitespace
- **end-of-file-fixer**: Ensures files end with a newline
- **check-yaml/toml/json**: Validates configuration file syntax
- **check-merge-conflict**: Prevents commits with merge conflict markers
- **check-added-large-files**: Prevents accidentally committing large files
- **debug-statements**: Prevents committing debug statements

## Setup

Pre-commit is automatically set up when you run:

```bash
make install-dev
make pre-commit-install
```

Or manually:

```bash
.venv/bin/pip install pre-commit
.venv/bin/pre-commit install
```

## Usage

### Automatic (Recommended)
Pre-commit hooks run automatically before each `git commit`. If any checks fail:

1. The commit is blocked
2. Fixable issues (like formatting) are automatically fixed
3. You need to `git add` the fixes and commit again
4. Manual fixes may be required for some issues

### Manual Testing
You can run pre-commit manually:

```bash
# Run on all files
make pre-commit

# Run on specific files
.venv/bin/pre-commit run --files src/discogs_to_tidal/cli/main.py

# Run a specific hook
.venv/bin/pre-commit run black --all-files
```

### Bypassing (Not Recommended)
In rare cases, you can skip pre-commit hooks:

```bash
git commit --no-verify -m "Your commit message"
```

**Note**: This should only be used in exceptional circumstances.

## Configuration

The pre-commit configuration is in `.pre-commit-config.yaml`. Key points:

- **Scope**: Only checks files in `src/` directory (excludes `tests/`, `spikes/`, etc.)
- **Relaxed mypy**: Uses relaxed type checking to focus on major issues
- **Auto-fixing**: Many issues are automatically fixed (formatting, whitespace)

## Benefits

- **Consistent code style** across all contributors
- **Catch common errors** before they reach CI/CD
- **Automatic formatting** saves time
- **Better code quality** without manual effort
- **Faster CI builds** since basic checks pass locally

## Troubleshooting

### Pre-commit fails on files you didn't change
Pre-commit runs on all changed files. If other files have issues, fix them or temporarily exclude them.

### Mypy errors you can't fix
The pre-commit mypy configuration is relaxed. For stricter checking, use:

```bash
make lint  # Runs full mypy checking
```

### Need to update hooks
```bash
.venv/bin/pre-commit autoupdate
```
