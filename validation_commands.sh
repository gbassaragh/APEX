#!/bin/bash
# Code Quality and Security Validation Script for APEX
# Run this after installing dependencies: pip install -e .

set -e  # Exit on error

echo "===== APEX Code Validation Suite ====="
echo ""

# 1. Black - Code Formatting
echo "1. Running Black (code formatting)..."
python3 -m black src/ tests/ --line-length 100 --check
echo "✓ Black formatting check passed"
echo ""

# 2. isort - Import Sorting
echo "2. Running isort (import sorting)..."
python3 -m isort src/ tests/ --profile black --line-length 100 --check-only
echo "✓ isort import sorting check passed"
echo ""

# 3. flake8 - Linting
echo "3. Running flake8 (linting)..."
python3 -m flake8 src/ tests/ --max-line-length=100 --extend-ignore=E203,W503
echo "✓ flake8 linting check passed"
echo ""

# 4. Ruff - Fast Linting (optional, install with: pip install ruff)
if command -v ruff &> /dev/null; then
    echo "4. Running ruff (fast linting)..."
    ruff check src/ tests/
    echo "✓ ruff linting check passed"
    echo ""
else
    echo "4. Ruff not installed (optional), skipping..."
    echo ""
fi

# 5. Bandit - Security Scanning
echo "5. Running bandit (security scan)..."
# Install with: pip install bandit
if command -v bandit &> /dev/null; then
    bandit -r src/ -ll -f txt
    echo "✓ bandit security scan passed"
    echo ""
else
    echo "Installing bandit..."
    pip install bandit --quiet
    bandit -r src/ -ll -f txt
    echo "✓ bandit security scan passed"
    echo ""
fi

# 6. Syntax Validation
echo "6. Running Python syntax validation..."
find src/ tests/ -name "*.py" -exec python3 -m py_compile {} \;
echo "✓ Python syntax validation passed"
echo ""

echo "===== All Validation Checks Passed ====="
echo ""
echo "To auto-fix formatting issues, run:"
echo "  black src/ tests/ --line-length 100"
echo "  isort src/ tests/ --profile black --line-length 100"
