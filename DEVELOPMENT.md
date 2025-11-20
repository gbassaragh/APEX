# Development Guide for APEX

## Table of Contents

1. [Quick Start](#quick-start)
2. [Repository Structure](#repository-structure)
3. [Code Quality Standards](#code-quality-standards)
4. [Testing Guidelines](#testing-guidelines)
5. [Database Migrations](#database-migrations)
6. [Local Development Server](#local-development-server)
7. [Common Development Tasks](#common-development-tasks)
8. [Code Style Guidelines](#code-style-guidelines)
9. [Commit & Pull Request Guidelines](#commit--pull-request-guidelines)
10. [Security Practices](#security-practices)
11. [Troubleshooting](#troubleshooting)
12. [Additional Resources](#additional-resources)

---

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

---

## Repository Structure

### Project Organization

- **`src/apex/`**: FastAPI application root
  - `main.py`: Application entry point with router registration
  - `config.py`: Pydantic settings (environment-based configuration)
  - `dependencies.py`: Dependency injection wiring, DB session management
  - **`api/v1/`**: API routers (projects, documents, estimates, health, jobs)
    - Keep API routes versioned under v1 namespace
    - New endpoints follow `/api/v1/{resource}` pattern
  - **`models/`**: Data models and schemas
    - `enums.py`: Enumerations (ProjectStatus, ValidationStatus, AACEClass, TerrainType)
    - `database.py`: SQLAlchemy ORM models with GUID type
    - `schemas.py`: Pydantic DTOs (request/response models), ErrorResponse, PaginatedResponse
  - **`database/`**: Database layer
    - `connection.py`: Engine with NullPool for stateless operation
    - **`repositories/`**: Repository pattern (project, document, estimate, job, audit)
  - **`services/`**: Business logic layer
    - **`llm/`**: LLM orchestration (maturity-aware routing by AACE class)
    - `document_parser.py`: Azure Document Intelligence wrapper
    - `risk_analysis.py`: Monte Carlo engine (LHS, Iman-Conover, Spearman)
    - `aace_classifier.py`: AACE Class 1-5 determination
    - `cost_database.py`: Cost breakdown structure (CBS/WBS) builder
    - `estimate_generator.py`: Main orchestration service
    - `background_jobs.py`: Async job workers (document validation, estimate generation)
  - **`azure/`**: Azure service adapters
    - Managed Identity helpers, blob storage, key vault clients
  - **`utils/`**: Utilities (logging, errors, retry decorators, middleware)

- **`tests/`**: Test suite
  - **`unit/`**: Isolated component tests (services, repositories)
  - **`integration/`**: API/database flow tests
  - **`fixtures/`**: Shared fixtures and Azure mocks (`azure_mocks.py`)

- **`alembic/`**: Database migration environment
  - **`versions/`**: Auto-generated migration scripts

- **`infra/`**: Infrastructure as Code
  - Bicep templates and deployment scripts
  - **`parameters/`**: Environment-specific parameters (dev, staging, prod)

- **Root helpers**:
  - `pyproject.toml`: Dependencies and tooling configuration (single source of truth)
  - `validation_commands.sh`: Consolidated validation runner
  - `Dockerfile`: Container build configuration
  - Documentation: `DEVELOPMENT.md`, `RUNBOOK.md`, `CLAUDE.md`, `DEPLOYMENT_OPERATIONS_GUIDE.md`

---

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

# Consolidated validation script
./validation_commands.sh
```

### Pre-commit Hook Behavior

- **Validation runs automatically** before every `git commit`
- **Commit is blocked** if any check fails
- **Clear error messages** show exactly what needs to be fixed
- **Skip validation** (not recommended): `git commit --no-verify`

---

## Testing Guidelines

### Framework and Conventions

- **Framework**: `pytest` with fixtures in `tests/fixtures/`
- **Test Types**:
  - **Unit tests**: Isolated component tests for services and repositories
  - **Integration tests**: API/database behavior tests with full request/response cycle
- **Naming Conventions**:
  - Test files: `test_<area>.py`
  - Test functions: `test_<behavior>`
- **Coverage Target**: 100% for new/modified code; add regression tests alongside fixes
- **Azure Mocking**: Use provided fixtures/mocks for Azure services; avoid hitting live services in tests

### Running Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# All tests with coverage
pytest tests/ --cov=apex --cov-report=term-missing

# Specific test file
pytest tests/unit/test_risk_analysis.py -v

# With verbose output and coverage
pytest tests/ -v --cov=apex --cov-report=term-missing
```

---

## Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# View migration history
alembic history

# Current database version
alembic current
```

**Note**: All schema changes must go through Alembic migrations. Review auto-generated migrations before applying.

---

## Local Development Server

```bash
# Set environment variables
export AZURE_SQL_SERVER="..."
export AZURE_OPENAI_ENDPOINT="..."
# ... other required env vars (see .env.example)

# Run development server with auto-reload
uvicorn apex.main:app --reload --host 0.0.0.0 --port 8000

# Access API documentation
open http://localhost:8000/docs  # Swagger UI
open http://localhost:8000/redoc  # ReDoc

# Health checks
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

---

## Common Development Tasks

### Adding a New API Endpoint

1. Create router in `src/apex/api/v1/your_module.py`
2. Add Pydantic schemas to `src/apex/models/schemas.py`
3. Implement repository methods in `src/apex/database/repositories/`
4. Add service layer logic in `src/apex/services/`
5. Register router in `src/apex/main.py`
6. Write tests in `tests/integration/test_your_module.py`
7. **Update documentation** (README/DEVELOPMENT/RUNBOOK) when behavior changes
8. **Include screenshots or API examples** in PR if UI/contract changes occur

### Adding a New Database Table

1. Add SQLAlchemy model to `src/apex/models/database.py`
2. Create migration: `alembic revision --autogenerate -m "Add your_table"`
3. Review and edit migration file if needed
4. Apply migration: `alembic upgrade head`
5. Add repository class in `src/apex/database/repositories/`
6. Write unit tests for repository operations

### Adding a New Service

1. Create service class in `src/apex/services/your_service.py`
2. Add dependency injection in `src/apex/dependencies.py` if needed
3. Write comprehensive unit tests in `tests/unit/test_your_service.py`
4. Mock external dependencies (Azure services, database)
5. Document service behavior in docstrings

### Debugging Tips

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with debugger
python -m debugpy --listen 5678 --wait-for-client -m uvicorn apex.main:app --reload

# Check database connections
# Use Azure Data Studio or psql to verify database schema

# View application logs
tail -f logs/apex.log  # If file logging is configured
```

---

## Code Style Guidelines

### Formatting Standards

- **Line Length**: 100 characters maximum
- **Imports**: Sorted with isort (black profile)
- **Formatting**: black with default settings except line-length
- **Docstrings**: Google style with type hints in signatures
- **Type Hints**: Required for all public function signatures

### Naming Conventions

- **Modules/Variables/Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **API Routes**: Versioned under `src/apex/api/v1/`

### Error Handling

- Use custom exceptions from `apex.utils.errors`
- Always provide meaningful error messages
- Log errors with appropriate context
- Never suppress exceptions silently

### Documentation

- Add Google-style docstrings to all public functions
- Document complex logic with inline comments
- Keep README and DEVELOPMENT guides up to date
- Update RUNBOOK when operational procedures change

---

## Commit & Pull Request Guidelines

### Commit Messages

- **Format**: Short, imperative summaries (e.g., "Fix estimate routing bug")
- **Length**: First line ≤50 chars, body ≤72 chars per line
- **Pre-commit**: Run pre-commit hooks before committing (enforced automatically)
- **Scope**: One logical change per commit

### Pull Request Requirements

- **Purpose**: Clear description of what and why
- **Linked Issue**: Reference story/issue number
- **Testing Evidence**: Include test results (`pytest ...`, migration success if applicable)
- **Screenshots/Examples**: Add for UI changes or API contract modifications
- **Documentation**: Update docs (README/DEVELOPMENT/RUNBOOK) when behavior or operations change
- **Size**: Keep PRs small and focused (prefer multiple small PRs over one large PR)
- **Review**: Address all review comments before merging

### Branch Strategy

- **Feature branches**: `feature/short-description`
- **Bug fixes**: `fix/short-description`
- **Hotfixes**: `hotfix/short-description`
- **Base branch**: `main` (or `develop` if using GitFlow)

---

## Security Practices

### Configuration Management

- **No Secrets in Code**: Never commit secrets, API keys, or credentials
- **Environment Variables**: Use `.env` locally (git-ignored)
- **Azure Key Vault**: Required for all environments (dev, staging, prod)
- **Managed Identity**: All Azure services must use Managed Identity authentication
- **Configuration Pattern**: See `src/apex/config.py` for Pydantic settings

### Development Security

- **Input Validation**: All user input validated with Pydantic schemas
- **SQL Injection Prevention**: Use SQLAlchemy ORM exclusively, never raw SQL
- **Authentication**: Azure AD JWT tokens required for all API endpoints
- **Authorization**: Check `User` + `ProjectAccess` + `AppRole` tables
- **Bandit Scans**: All code must pass security scanning (enforced by pre-commit hooks)
- **Dependency Scanning**: Run `pip-audit` regularly to check for vulnerable packages

### Azure Integration Security

- **Private Endpoints**: All Azure services behind private endpoints
- **VNet Integration**: Container Apps must be VNet-injected
- **Zero Trust**: No hardcoded connection strings with credentials
- **Audit Trail**: All operations logged to `AuditLog` table (ISO compliance)

---

## Troubleshooting

### Pre-commit Hook Issues

```bash
# Hook not running
ls -la .git/hooks/pre-commit  # Verify it exists and is executable

# Reinstall hook
./.githooks/install-hooks.sh

# Check what the hook would do
bash -x .git/hooks/pre-commit

# Force reinstall with pre-commit framework
pre-commit uninstall
pre-commit install
```

### Validation Failures

```bash
# Fix formatting automatically
black src/ tests/ --line-length 100
isort src/ tests/ --profile black

# Review specific errors
flake8 src/ tests/  # See detailed error messages
ruff check src/ tests/ --fix  # Auto-fix some issues

# Security scan issues
bandit -r src/ -ll -f txt  # View security warnings
```

### Database Connection Issues

- Verify Azure SQL credentials in environment variables
- Check network connectivity to Azure (`ping <server>.database.windows.net`)
- Ensure Managed Identity is configured if using Container Apps
- Review connection string format in `src/apex/database/connection.py`
- Check firewall rules in Azure SQL Server settings

### Test Failures

```bash
# Run specific failing test with verbose output
pytest tests/unit/test_specific.py::test_function -v

# Check test fixtures
pytest tests/ --fixtures  # List all available fixtures

# Debug test database state
pytest tests/ --pdb  # Drop into debugger on failure
```

### Import Errors

```bash
# Verify editable install
pip install -e .

# Check Python path
python -c "import sys; print(sys.path)"

# Reinstall dependencies
pip install --force-reinstall -e .
```

---

## Additional Resources

- **[CLAUDE.md](./CLAUDE.md)** - Project overview, architecture, and implementation rules
- **[DEPLOYMENT_OPERATIONS_GUIDE.md](./DEPLOYMENT_OPERATIONS_GUIDE.md)** - Complete production deployment procedures
- **[IT_INTEGRATION_REVIEW_SUMMARY.md](./IT_INTEGRATION_REVIEW_SUMMARY.md)** - Production readiness assessment
- **[RUNBOOK.md](./RUNBOOK.md)** - Operational procedures and troubleshooting
- **[.githooks/README.md](./.githooks/README.md)** - Detailed pre-commit hook documentation
- **[APEX_Prompt.md](./APEX_Prompt.md)** - Complete functional specification
- **[API Documentation](http://localhost:8000/docs)** - Interactive API docs (when server running)

---

## Getting Help

- Check existing documentation in this repository
- Review error messages and logs carefully
- Search for similar issues in the codebase
- Run `./validation_commands.sh` to identify common issues
- Consult the team for complex Azure integration questions
- See RUNBOOK.md for operational troubleshooting procedures
