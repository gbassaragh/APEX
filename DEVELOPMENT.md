# Development Guide for APEX

## Quick Start

### 1. Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd APEX

# Create and activate virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Set up environment variables
cp .env.example .env
# Edit .env with your Azure credentials
```

### 2. Install Pre-commit Hooks (Required)

Before making any commits, install the pre-commit hooks to ensure code quality:

#### Option A: Simple Bash Hook (Quick Setup)

```bash
./githooks/install-hooks.sh
```

#### Option B: Pre-commit Framework (Recommended for Teams)

```bash
pip install pre-commit
pre-commit install
```

The hooks will automatically run on every commit and check:
- ✅ **black** - Code formatting (100 char line length)
- ✅ **flake8** - PEP 8 linting
- ✅ **isort** - Import sorting
- ✅ **ruff** - Fast Python linting
- ✅ **bandit** - Security scanning

## Code Quality Standards

### Running Validation Manually

```bash
# Run all checks
black src/ tests/ --check --line-length 100
flake8 src/ tests/
isort src/ tests/ --check-only --profile black
ruff check src/ tests/
bandit -r src/ -ll -f txt

# Auto-fix formatting issues
black src/ tests/ --line-length 100
isort src/ tests/ --profile black
```

### Pre-commit Hook Behavior

- **Validation runs automatically** before every `git commit`
- **Commit is blocked** if any check fails
- **Clear error messages** show exactly what needs to be fixed
- **Skip validation** (not recommended): `git commit --no-verify`

## Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1
```

## Running Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# All tests with coverage
pytest tests/ --cov=apex --cov-report=term-missing
```

## Local Development Server

```bash
# Set environment variables
export AZURE_SQL_SERVER="..."
export AZURE_OPENAI_ENDPOINT="..."
# ... other required env vars

# Run development server
uvicorn apex.main:app --reload --host 0.0.0.0 --port 8000

# Access API docs
open http://localhost:8000/docs  # Swagger UI
open http://localhost:8000/redoc  # ReDoc
```

## Common Development Tasks

### Adding a New API Endpoint

1. Create router in `src/apex/api/v1/your_module.py`
2. Add Pydantic schemas to `src/apex/models/schemas.py`
3. Implement repository methods in `src/apex/database/repositories/`
4. Add service layer logic in `src/apex/services/`
5. Register router in `src/apex/main.py`
6. Write tests in `tests/integration/test_your_module.py`

### Adding a New Database Table

1. Add SQLAlchemy model to `src/apex/models/database.py`
2. Create migration: `alembic revision --autogenerate -m "Add your_table"`
3. Review and edit migration file if needed
4. Apply migration: `alembic upgrade head`
5. Add repository class in `src/apex/database/repositories/`

### Debugging Tips

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with debugger
python -m debugpy --listen 5678 --wait-for-client -m uvicorn apex.main:app --reload

# Check database connections
# Use Azure Data Studio or psql to verify database schema
```

## Code Style Guidelines

- **Line Length**: 100 characters maximum
- **Imports**: Sorted with isort (black profile)
- **Formatting**: black with default settings except line-length
- **Docstrings**: Google style with type hints in signatures
- **Type Hints**: Required for all function signatures
- **Error Handling**: Use custom exceptions from `apex.utils.errors`

## Security Practices

- **No Secrets in Code**: Use Azure Key Vault or environment variables
- **Managed Identity Only**: No hardcoded API keys or connection strings
- **Input Validation**: All user input must be validated with Pydantic
- **SQL Injection Prevention**: Use SQLAlchemy ORM, never raw SQL
- **Bandit Scans**: All code must pass security scanning

## Troubleshooting

### Pre-commit Hook Issues

```bash
# Hook not running
ls -la .git/hooks/pre-commit  # Verify it exists and is executable

# Reinstall hook
./.githooks/install-hooks.sh

# Check what the hook would do
bash -x .git/hooks/pre-commit
```

### Validation Failures

```bash
# Fix formatting automatically
black src/ tests/ --line-length 100
isort src/ tests/ --profile black

# Review specific errors
flake8 src/ tests/  # See detailed error messages
ruff check src/ tests/ --fix  # Auto-fix some issues
```

### Database Connection Issues

- Verify Azure SQL credentials in environment variables
- Check network connectivity to Azure
- Ensure Managed Identity is configured if using Container Apps
- Review connection string format in `src/apex/database/connection.py`

## Additional Resources

- [CLAUDE.md](./CLAUDE.md) - Project overview and architecture
- [.githooks/README.md](./.githooks/README.md) - Detailed hook documentation
- [APEX_Prompt.md](./APEX_Prompt.md) - Complete specification
- [API Documentation](http://localhost:8000/docs) - Interactive API docs (when server running)

## Getting Help

- Check existing documentation in this repository
- Review error messages and logs carefully
- Search for similar issues in the codebase
- Consult the team for complex Azure integration questions
