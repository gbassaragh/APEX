# Git Hooks for APEX Project

This directory contains Git hooks that enforce code quality standards before commits.

## Quick Start

### Option 1: Simple Bash Hook (Recommended for Quick Setup)

```bash
# Install the hook
./.githooks/install-hooks.sh

# Or manually:
cp .githooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### Option 2: Pre-commit Framework (Recommended for Teams)

The `pre-commit` framework is more robust and is the industry standard for Python projects.

```bash
# Install pre-commit framework
pip install pre-commit

# Install the hooks
pre-commit install

# (Optional) Run on all files
pre-commit run --all-files
```

## What Gets Checked

Every commit will automatically run:

1. **black** - Code formatting (100 character line length)
2. **flake8** - PEP 8 linting (with E203 ignored for black compatibility)
3. **isort** - Import statement sorting
4. **ruff** - Fast Python linting
5. **bandit** - Security vulnerability scanning

## Using the Hooks

### Normal Commit

```bash
git add .
git commit -m "Your commit message"
# Hooks run automatically - commit proceeds only if all checks pass
```

### Skip Hooks (Not Recommended)

```bash
git commit --no-verify -m "Your commit message"
```

### Fix Issues Automatically

If the hooks fail, most formatting issues can be fixed automatically:

```bash
# Fix black formatting
black src/ tests/ --line-length 100

# Fix import sorting
isort src/ tests/ --profile black

# Then retry commit
git commit -m "Your commit message"
```

## Differences Between Options

| Feature | Bash Hook | Pre-commit Framework |
|---------|-----------|---------------------|
| Setup | Simple copy | `pip install pre-commit` |
| Speed | Fast | Cached (faster after first run) |
| Updates | Manual | `pre-commit autoupdate` |
| CI Integration | Manual script | Built-in GitHub Actions support |
| Shared Config | Manual sync | Version controlled config |
| Skip Individual Hooks | No | Yes (`SKIP=flake8 git commit`) |
| Auto-fixing | Manual | Built-in for some hooks |

## Troubleshooting

### Hook Not Running

```bash
# Check if hook is installed
ls -la .git/hooks/pre-commit

# Reinstall
./.githooks/install-hooks.sh
```

### Hook Fails But Code Looks Correct

```bash
# Run validation manually to see details
source venv/bin/activate
black src/ tests/ --check --line-length 100
flake8 src/ tests/
isort src/ tests/ --check-only --profile black
ruff check src/ tests/
bandit -r src/ -ll -f txt
```

### Need to Commit Despite Failures (Emergency Only)

```bash
git commit --no-verify -m "Emergency fix"
```

**Note**: This should be rare and followed by a fix commit.

## CI/CD Integration

The same checks run in the GitHub Actions CI/CD pipeline. Even if you skip hooks locally, the CI will catch issues.

See `.github/workflows/` for CI configuration.
