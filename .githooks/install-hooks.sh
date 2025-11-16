#!/bin/bash
# Installation script for Git hooks

echo "Installing Git hooks for APEX project..."

# Create .git/hooks directory if it doesn't exist
mkdir -p .git/hooks

# Copy pre-commit hook
cp .githooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

echo "✅ Pre-commit hook installed successfully!"
echo ""
echo "The following checks will run before each commit:"
echo "  - black (code formatting)"
echo "  - flake8 (linting)"
echo "  - isort (import sorting)"
echo "  - ruff (fast linting)"
echo "  - bandit (security scanning)"
echo ""
echo "To bypass the hook (not recommended), use: git commit --no-verify"
