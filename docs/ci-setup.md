# CI/CD Pipeline and Branch Protection Setup

## Overview

This setup ensures that all code changes must pass comprehensive quality checks before being merged into the main branch.

## GitHub Actions Workflow

The CI pipeline (`.github/workflows/ci.yml`) runs automatically on:
- **Push to main/develop branches**: Full test suite
- **Pull requests to main**: Full test suite before merge

### Pipeline Jobs

1. **Test Job** (`test`):
   - Tests across Python 3.8-3.12
   - Runs pre-commit hooks
   - Executes full test suite with coverage
   - Uploads coverage to Codecov

2. **Lint Job** (`lint`):
   - Code formatting (black, isort)
   - Linting (flake8)
   - Type checking (mypy)

3. **Security Job** (`security`):
   - Vulnerability scanning (safety)
   - Static security analysis (bandit)

4. **Type Check Job** (`type-check`):
   - MyPy type validation

5. **Build Job** (`build`):
   - Package building
   - Artifact upload

## Setting Up Branch Protection

To enforce that all tests pass before merging, set up branch protection rules:

### 1. Via GitHub Web Interface

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Branches**
3. Click **Add rule** for the main branch
4. Configure the following settings:

#### Required Settings
- ✅ **Require a pull request before merging**
  - ✅ Require approvals: 1
  - ✅ Dismiss stale PR approvals when new commits are pushed
  - ✅ Require review from code owners (if you have CODEOWNERS file)

- ✅ **Require status checks to pass before merging**
  - ✅ Require branches to be up to date before merging
  - Required status checks:
    - `test (3.8)`
    - `test (3.9)`
    - `test (3.10)`
    - `test (3.11)`
    - `test (3.12)`
    - `lint`
    - `type-check`
    - `security`
    - `build`

- ✅ **Require conversation resolution before merging**
- ✅ **Require signed commits** (recommended)
- ✅ **Include administrators** (applies rules to repo admins too)

### 2. Via GitHub CLI (Alternative)

```bash
# Install GitHub CLI if not already installed
# https://cli.github.com/

# Set up branch protection
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["test (3.8)","test (3.9)","test (3.10)","test (3.11)","test (3.12)","lint","type-check","security","build"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null
```

### 3. Workflow File Triggers

The current workflow triggers on:
```yaml
on:
  push:
    branches: [ main, develop ]  # Run on direct pushes
  pull_request:
    branches: [ main ]           # Run on PRs to main
```

## Local Development Workflow

### Pre-commit Setup (Recommended)
```bash
# Install pre-commit hooks locally
make pre-commit-install

# Run pre-commit on all files
make pre-commit
```

### Running Quality Checks Locally
```bash
# Run all quality checks
make check

# Individual checks
make lint          # Formatting, linting, type checking
make test          # Full test suite
make test-coverage # Tests with coverage report
```

## Codecov Integration (Optional)

For coverage reporting, add your repo to [Codecov](https://codecov.io/):

1. Sign up/login to Codecov with your GitHub account
2. Add your repository
3. Get the upload token (if private repo)
4. Add `CODECOV_TOKEN` to your repository secrets:
   - Go to GitHub repo → Settings → Secrets → Actions
   - Add new secret: `CODECOV_TOKEN`

## Security Scanning (Optional)

The pipeline includes basic security scanning. For enhanced security:

1. **Dependabot**: Enable in GitHub Settings → Security & analysis
2. **CodeQL**: Enable GitHub's code scanning
3. **Security Advisories**: Monitor repository security tab

## Troubleshooting

### Common Issues

1. **Tests fail in CI but pass locally**:
   - Check Python version compatibility
   - Verify all dependencies are in `pyproject.toml`
   - Check for environment-specific issues

2. **Pre-commit hooks fail**:
   - Run `make format` to fix formatting issues
   - Update hook versions in `.pre-commit-config.yaml`

3. **Coverage reports not uploading**:
   - Verify `CODECOV_TOKEN` is set correctly
   - Check that `coverage.xml` is generated

4. **Branch protection not working**:
   - Ensure status check names match exactly
   - Wait for initial workflow run to register status checks

## Verification

After setup, verify the pipeline works:

1. Create a test branch: `git checkout -b test-pipeline`
2. Make a small change and commit
3. Push and create a PR to main
4. Verify all status checks run and must pass before merge button activates

## Benefits

This setup ensures:
- ✅ All tests pass before merge
- ✅ Code formatting is consistent
- ✅ Type safety is maintained
- ✅ Security vulnerabilities are caught early
- ✅ Code coverage is tracked
- ✅ Multi-Python version compatibility
- ✅ No broken code reaches main branch
