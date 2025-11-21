# Developer-Facing Artifacts
## Templates for Development Team Onboarding and Contribution

> **PURPOSE**: These templates support developer onboarding, consistent contribution practices, and backlog management across all six tools in the estimation platform.

---

## Document Navigation

1. **[README Template](#1-readme-template)** - Repository homepage and quick start
2. **[CONTRIBUTING Template](#2-contributing-template)** - Contribution guidelines and workflow
3. **[Coding Standards](#3-coding-standards)** - Code quality and style conventions
4. **[Backlog Templates](#4-backlog-templates)** - User stories, technical tasks, bug reports
5. **[Consistency Maintenance](#5-consistency-maintenance-guide)** - Keeping 85% shared pattern aligned

---

## 1. README Template

```markdown
# [TOOL NAME] - [One-Line Description]

> **[REPLACE]**: Short description of tool's purpose and primary users
> Example: "AI-powered cost estimation for utility transmission and distribution projects"

[![Build Status](https://github.com/[org]/[tool-repo]/workflows/CI-CD/badge.svg)](https://github.com/[org]/[tool-repo]/actions)
[![Coverage](https://codecov.io/gh/[org]/[tool-repo]/branch/main/graph/badge.svg)](https://codecov.io/gh/[org]/[tool-repo])
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Proprietary-red)](LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Development Setup](#development-setup)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [Documentation](#documentation)
- [Support](#support)

---

## Overview

### What is [TOOL NAME]?

**[REPLACE with 2-3 paragraph description]**

Example (APEX):
> APEX (AI-Powered Estimation Expert) automates cost estimation for utility transmission and distribution projects. The system processes engineering drawings, specifications, and historical bid data to generate AACE-compliant estimates with statistical confidence intervals (P50/P80/P95) through Monte Carlo risk analysis.
>
> Primary users are 15 internal utility cost estimators who handle 300+ estimates annually. APEX reduces estimate preparation time by 40% while improving accuracy from ±20-30% variance to ±10% through AI-powered document intelligence and standardized risk modeling.
>
> The tool is part of a six-tool AI-enabled estimation platform, sharing 85% common architecture with sibling tools (Substation Estimating, Renewable Interconnection, Bid Comparison, Budget Tracking, Cost Database Management).

### Key Features

**[REPLACE with bullet list of 5-7 key capabilities]**

Example (APEX):
- ✅ **AI Document Parsing**: Azure Document Intelligence extracts quantities from 100+ page engineering drawings in <30 seconds
- ✅ **Intelligent Validation**: GPT-4 validates document completeness, identifies gaps and conflicts
- ✅ **AACE Classification**: Automatic estimate maturity determination (Class 1-5) based on document quality
- ✅ **Monte Carlo Risk Analysis**: Industrial-grade simulation with Latin Hypercube Sampling and correlation modeling
- ✅ **LLM Narrative Generation**: Automatic assumptions, exclusions, and risk descriptions with maturity-aware tone
- ✅ **Complete Audit Trail**: All operations logged for 7-year ISO-NE compliance requirement
- ✅ **Export to Excel**: One-click export with summary, line items, risk distributions, and charts

### Technology Stack

**[SHARED PATTERN - Copy verbatim for all tools]**

- **Language**: Python 3.11+
- **API Framework**: FastAPI 0.104.0+
- **Database**: Azure SQL Database (Business Critical)
- **ORM**: SQLAlchemy 2.0+ with Alembic migrations
- **Validation**: Pydantic 2.x
- **AI Services**: Azure OpenAI (GPT-4), Azure AI Document Intelligence
- **Storage**: Azure Blob Storage
- **Secrets**: Azure Key Vault
- **Observability**: Azure Application Insights
- **Compute**: Azure Container Apps
- **Testing**: pytest with ≥80% unit coverage, ≥70% integration coverage

### Shared Libraries

**[SHARED PATTERN - Update versions as needed]**

- **estimating-ai-core** v1.0.0 - LLM orchestration and prompt management
- **estimating-connectors** v0.5.0 - Integration with cost databases and external systems
- **estimating-security** v1.0.0 - Authentication, authorization, audit logging

---

## Quick Start

### Prerequisites

- **Python**: 3.11 or higher
- **Azure CLI**: For local development with Azure services
- **Git**: Version control
- **Docker**: (Optional) For containerized local development

### 5-Minute Local Setup

```bash
# 1. Clone repository
git clone https://github.com/[org]/[tool-repo].git
cd [tool-repo]

# 2. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -e .

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your Azure credentials (see .env.example for required variables)

# 5. Run database migrations
alembic upgrade head

# 6. Start development server
uvicorn [tool_module].main:app --reload --host 0.0.0.0 --port 8000
```

**Access API documentation**: `http://localhost:8000/docs` (Swagger UI)

### First API Call

```bash
# Health check
curl http://localhost:8000/health/live

# Create project (requires Azure AD token - see Authentication section)
curl -X POST "http://localhost:8000/api/v1/projects" \
  -H "Authorization: Bearer {YOUR_JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "Test Project",
    "project_description": "My first project"
  }'
```

---

## Architecture

### High-Level Design

```
[INCLUDE SIMPLIFIED ARCHITECTURE DIAGRAM]

User (Estimator)
    ↓ HTTPS (JWT Bearer token)
FastAPI REST API (Container Apps)
    ↓
┌───────────────┬───────────────┬───────────────┐
│ Azure SQL DB  │ Azure OpenAI  │ Azure Blob    │
│ (estimates)   │ (LLM calls)   │ (documents)   │
└───────────────┴───────────────┴───────────────┘
```

### Project Structure

```
[tool-repo]/
├── src/
│   └── [tool_module]/
│       ├── main.py              # FastAPI app entry point
│       ├── config.py            # Pydantic settings
│       ├── dependencies.py      # Dependency injection
│       ├── api/
│       │   └── v1/              # API routers
│       │       ├── health.py
│       │       ├── projects.py
│       │       ├── documents.py
│       │       └── [domain].py  # Tool-specific endpoints
│       ├── models/
│       │   ├── enums.py
│       │   ├── database.py      # SQLAlchemy models
│       │   └── schemas.py       # Pydantic DTOs
│       ├── database/
│       │   ├── connection.py
│       │   └── repositories/    # Repository pattern
│       ├── services/            # Business logic
│       ├── azure/               # Azure client wrappers
│       └── utils/               # Logging, errors, retry
├── tests/
│   ├── fixtures/                # Shared test fixtures
│   ├── unit/                    # Service/repository tests
│   └── integration/             # API endpoint tests
├── alembic/                     # Database migrations
├── infra/                       # Infrastructure as Code (Bicep)
├── .github/workflows/           # CI/CD pipelines
├── pyproject.toml               # Dependencies and tooling
├── .env.example                 # Environment variable template
├── Dockerfile                   # Container image
├── README.md                    # This file
├── CLAUDE.md                    # AI assistant context
├── DEVELOPMENT.md               # Detailed developer guide
└── DEPLOYMENT_OPERATIONS_GUIDE.md  # Production runbook
```

**Detailed Architecture**: See `ARCHITECTURE.md` for complete system design

---

## Development Setup

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Azure SQL Database
AZURE_SQL_SERVER="[server].database.windows.net"
AZURE_SQL_DATABASE="[database-name]"

# Azure OpenAI
AZURE_OPENAI_ENDPOINT="https://[deployment].openai.azure.com/"
AZURE_OPENAI_DEPLOYMENT="gpt-4-turbo"

# Azure Blob Storage
AZURE_STORAGE_ACCOUNT="st[toolname][env]"

# Azure Application Insights
AZURE_APPINSIGHTS_CONNECTION_STRING="InstrumentationKey=..."

# Azure Key Vault (for production)
AZURE_KEY_VAULT_URL="https://kv-[tool]-[env].vault.azure.net/"

# Application Settings
LOG_LEVEL=INFO
DEFAULT_MONTE_CARLO_ITERATIONS=10000
```

**Azure AD Authentication**: See `DEVELOPMENT.md` Section 4: Authentication Setup

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Add [description]"

# Review generated migration in alembic/versions/
# Edit if necessary (auto-generation not perfect)

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# View migration history
alembic history
```

### Code Quality Tools

**[SHARED PATTERN - Required for all tools]**

```bash
# Format code (required before commit)
black src/ tests/ --line-length 100
isort src/ tests/ --profile black

# Lint code
flake8 src/ tests/

# Security scan
bandit -r src/ -ll

# Run all quality checks
./validation_commands.sh  # Consolidated script
```

**Pre-commit Hooks**: Automatically run quality checks before every commit
```bash
# Install hooks (one-time setup)
./githooks/install-hooks.sh

# Or use pre-commit framework
pip install pre-commit
pre-commit install
```

---

## Testing

### Running Tests

```bash
# All tests with coverage
pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=80

# Unit tests only (fast)
pytest tests/unit/ -v

# Integration tests (requires test database)
pytest tests/integration/ -v

# Specific test file
pytest tests/unit/test_[service].py -v

# With verbose output
pytest tests/ -vv
```

### Writing Tests

**Test Structure** [SHARED PATTERN]:

```python
# tests/unit/test_example_service.py

import pytest
from [tool_module].services.example_service import ExampleService
from tests.fixtures.azure_mocks import MockAzureOpenAIClient

@pytest.fixture
def example_service(mock_azure_openai):
    """Fixture provides ExampleService with mocked dependencies."""
    return ExampleService(llm_client=mock_azure_openai)

def test_example_operation_success(example_service):
    """Test successful execution of example operation."""
    # Arrange
    input_data = {"key": "value"}

    # Act
    result = example_service.perform_operation(input_data)

    # Assert
    assert result is not None
    assert result["status"] == "success"

def test_example_operation_validation_error(example_service):
    """Test validation error handling."""
    # Arrange
    invalid_input = {}

    # Act & Assert
    with pytest.raises(BusinessRuleViolation) as exc_info:
        example_service.perform_operation(invalid_input)

    assert "required field" in str(exc_info.value).lower()
```

**Azure Service Mocking**: See `tests/fixtures/azure_mocks.py` for mock clients

### Coverage Requirements

**[SHARED PATTERN - Enforced in CI/CD]**

- **Unit Tests**: ≥80% coverage
- **Integration Tests**: ≥70% coverage
- **Critical Services**: 100% coverage required (risk analysis, estimate generation)

---

## Deployment

### Environment Strategy

| Environment | Branch | Database | Auto-Deploy | Approval |
|-------------|--------|----------|-------------|----------|
| **Development** | `develop` | Shared test DB | Yes (on push) | None |
| **Staging** | `main` (pre-prod tag) | Staging DB | Manual trigger | Tech Lead |
| **Production** | `main` (release tag) | Production DB | Manual trigger | Product Owner |

### Deployment Process

**[SHARED PATTERN - GitHub Actions workflow]**

```bash
# 1. Code merged to main after PR approval

# 2. CI/CD pipeline runs:
#    - Linting (black, isort, flake8, bandit)
#    - Testing (pytest with ≥80% coverage)
#    - Build Docker image
#    - Push to Azure Container Registry

# 3. Manual deployment trigger (GitHub Actions)
#    - Infrastructure deployment (Bicep)
#    - Database migration (Alembic)
#    - Container App update
#    - Smoke tests

# 4. Post-deployment validation
#    - Health checks (liveness, readiness)
#    - API integration tests
#    - Observability dashboard review
```

**Detailed Runbook**: See `DEPLOYMENT_OPERATIONS_GUIDE.md` for 30-step checklist

---

## Contributing

See **[CONTRIBUTING.md](./CONTRIBUTING.md)** for detailed contribution guidelines.

**Quick Summary**:
1. **Fork repository** and create feature branch (`feature/short-description`)
2. **Write tests** for new functionality (maintain ≥80% coverage)
3. **Follow code standards** (black, isort, flake8, bandit)
4. **Update documentation** if behavior changes (README, DEVELOPMENT, RUNBOOK)
5. **Submit PR** with clear description and test evidence
6. **Address review comments** from maintainers
7. **Merge after approval** (squash-merge to main)

---

## Documentation

### For Developers

- **[DEVELOPMENT.md](./DEVELOPMENT.md)** - Comprehensive developer guide
  - Repository structure
  - Common development tasks
  - Testing patterns
  - Database migrations
  - Troubleshooting

- **[CLAUDE.md](./CLAUDE.md)** - AI assistant context
  - Project overview for Claude Code
  - Architecture principles
  - Critical implementation rules
  - Common pitfalls

### For Operations

- **[DEPLOYMENT_OPERATIONS_GUIDE.md](./DEPLOYMENT_OPERATIONS_GUIDE.md)** - Production runbook
  - 30-step deployment checklist
  - Disaster recovery procedures
  - Monitoring and alerting
  - Common operational issues

- **[IT_INTEGRATION_REVIEW_SUMMARY.md](./IT_INTEGRATION_REVIEW_SUMMARY.md)** - Production readiness
  - Enterprise architecture review
  - Security validation
  - Compliance checklist
  - Production readiness score

### For Leadership

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - System architecture specification
- **[TECHNICAL_SPECIFICATION.md](./TECHNICAL_SPECIFICATION.md)** - Detailed implementation guide

### API Documentation

- **Swagger UI**: `http://localhost:8000/docs` (when server running)
- **ReDoc**: `http://localhost:8000/redoc` (alternative format)
- **OpenAPI JSON**: `http://localhost:8000/openapi.json` (machine-readable schema)

---

## Support

### Getting Help

1. **Documentation**: Check README, DEVELOPMENT.md, and RUNBOOK.md
2. **Error Messages**: Read carefully, check logs in Application Insights
3. **GitHub Issues**: Search for similar issues in repository
4. **Team Channel**: [Slack/Teams channel link]
5. **Office Hours**: Weekly developer sync (Fridays 2-3 PM)

### Reporting Issues

Use GitHub Issues with appropriate template:
- **Bug Report**: For unexpected behavior or errors
- **Feature Request**: For new functionality suggestions
- **Documentation**: For unclear or missing documentation

---

## License

Proprietary - Internal Use Only

Copyright (c) 2025 [Organization Name]. All rights reserved.

---

**Project Status**: [MVP / Development / Production]
**Current Version**: [Semantic version, e.g., v1.0.0]
**Last Updated**: [YYYY-MM-DD]
**Maintainers**: [Team name or lead developer name]
```

---

## 2. CONTRIBUTING Template

```markdown
# Contributing to [TOOL NAME]

Thank you for contributing to the [TOOL NAME] project! This guide will help you get started with the contribution process.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)
- [Review Process](#review-process)

---

## Code of Conduct

**[SHARED PATTERN - Same across all tools]**

### Our Standards

- **Be respectful**: Treat all contributors with respect and professionalism
- **Be collaborative**: Work together to achieve common goals
- **Be constructive**: Provide helpful feedback, focus on solutions
- **Be inclusive**: Welcome diverse perspectives and backgrounds
- **Be patient**: Everyone is learning, support each other's growth

### Unacceptable Behavior

- Harassment, discrimination, or hostile comments
- Personal attacks or insults
- Publishing others' private information
- Other conduct which could reasonably be considered inappropriate

**Enforcement**: Violations will be addressed by project maintainers and may result in temporary or permanent ban from the project.

---

## Getting Started

### Prerequisites

Before contributing, ensure you have:
- ✅ Python 3.11+ installed
- ✅ Azure CLI configured (for local development)
- ✅ Git configured with your identity
- ✅ Access to development environment (if applicable)

### Development Setup

```bash
# 1. Fork repository on GitHub

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/[tool-repo].git
cd [tool-repo]

# 3. Add upstream remote
git remote add upstream https://github.com/[org]/[tool-repo].git

# 4. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# 5. Install dependencies
pip install -e .

# 6. Install pre-commit hooks
./githooks/install-hooks.sh
```

---

## Development Workflow

### Branch Strategy

**[SHARED PATTERN - Same across all tools]**

- **`main`**: Production-ready code, protected branch
- **`develop`**: Integration branch for development
- **Feature branches**: `feature/short-description`
- **Bug fixes**: `fix/short-description`
- **Hotfixes**: `hotfix/short-description`

### Creating a Feature Branch

```bash
# 1. Sync with upstream
git checkout develop
git pull upstream develop

# 2. Create feature branch
git checkout -b feature/add-risk-factor-correlation

# 3. Make changes and commit
# (see Commit Guidelines below)

# 4. Push to your fork
git push origin feature/add-risk-factor-correlation

# 5. Create Pull Request on GitHub
```

### Keeping Your Branch Updated

```bash
# Regularly sync with upstream develop
git checkout develop
git pull upstream develop

# Rebase your feature branch
git checkout feature/your-feature
git rebase develop

# Resolve conflicts if any, then:
git push --force-with-lease origin feature/your-feature
```

---

## Coding Standards

### Python Style Guide

**[SHARED PATTERN - PEP 8 with modifications]**

#### Formatting

- **Line Length**: 100 characters maximum
- **Indentation**: 4 spaces (no tabs)
- **Imports**: Sorted with `isort` (black profile)
- **Formatting**: Enforced with `black`

```bash
# Auto-format your code before committing
black src/ tests/ --line-length 100
isort src/ tests/ --profile black
```

#### Naming Conventions

- **Modules/Variables/Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private attributes**: `_leading_underscore`

```python
# Good
class EstimateGenerator:
    DEFAULT_ITERATIONS = 10000

    def __init__(self, db_session):
        self.db = db_session
        self._cache = {}

    def generate_estimate(self, project_id: uuid.UUID) -> Estimate:
        """Generate cost estimate for project."""
        pass

# Bad
class estimateGenerator:  # Should be PascalCase
    def GenerateEstimate(project_id):  # Should be snake_case, missing type hints
        pass
```

#### Type Hints

**Required** for all public function signatures:

```python
from typing import List, Optional
from decimal import Decimal
import uuid

# Good - Complete type hints
def compute_cost(
    line_items: List[EstimateLineItem],
    risk_factors: Optional[List[RiskFactor]] = None
) -> Decimal:
    """Compute total cost with optional risk adjustments."""
    pass

# Bad - Missing type hints
def compute_cost(line_items, risk_factors=None):
    pass
```

#### Docstrings

**Required** for all public functions/classes (Google style):

```python
def generate_estimate(
    self,
    project_id: uuid.UUID,
    monte_carlo_iterations: int = 10000
) -> Estimate:
    """
    Generate complete cost estimate for project.

    This method orchestrates the full estimation workflow:
    1. Load project and validated documents
    2. Classify AACE estimate maturity
    3. Compute base cost from quantities
    4. Run Monte Carlo risk analysis
    5. Generate LLM narrative
    6. Persist estimate to database

    Args:
        project_id: Unique identifier for project to estimate
        monte_carlo_iterations: Number of simulation iterations (default 10000)

    Returns:
        Complete Estimate object with line items, risk factors, narrative

    Raises:
        NotFound: If project does not exist
        Forbidden: If user lacks permission
        BusinessRuleViolation: If no validated documents available
    """
    pass
```

#### Error Handling

- **Never suppress exceptions silently**
- **Use custom exceptions** from `utils.errors`
- **Provide meaningful error messages**

```python
from [tool_module].utils.errors import BusinessRuleViolation, NotFound

# Good
def get_project(project_id: uuid.UUID) -> Project:
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise NotFound(f"Project {project_id} not found")
    return project

# Bad
def get_project(project_id):
    try:
        project = db.query(Project).filter(Project.project_id == project_id).first()
        return project  # Returns None if not found, no error raised
    except Exception:
        pass  # Silent exception suppression
```

### Linting

**[SHARED PATTERN - Pre-commit hooks enforce]**

```bash
# Run all linters
flake8 src/ tests/
bandit -r src/ -ll

# Pre-commit hooks run automatically on git commit
# To run manually:
pre-commit run --all-files
```

---

## Testing Requirements

### Test Coverage

**[SHARED PATTERN - Enforced in CI/CD]**

- **Unit Tests**: ≥80% coverage of service and repository layers
- **Integration Tests**: ≥70% coverage of API endpoints
- **Critical Services**: 100% coverage required (risk analysis, estimate generation, security functions)

### Writing Tests

#### Unit Test Example

```python
# tests/unit/test_estimate_generator.py

import pytest
from [tool_module].services.estimate_generator import EstimateGeneratorService
from tests.fixtures.azure_mocks import MockLLMOrchestrator

@pytest.fixture
def estimate_service(mock_db, mock_llm, mock_cost_service):
    """Fixture provides EstimateGeneratorService with mocked dependencies."""
    return EstimateGeneratorService(
        db=mock_db,
        llm_orchestrator=mock_llm,
        cost_service=mock_cost_service
    )

def test_generate_estimate_success(estimate_service, sample_project):
    """Test successful estimate generation workflow."""
    # Arrange
    project_id = sample_project.project_id
    user_id = uuid.uuid4()

    # Act
    estimate = estimate_service.generate_estimate(project_id, user_id)

    # Assert
    assert estimate is not None
    assert estimate.project_id == project_id
    assert estimate.base_cost_usd > 0
    assert estimate.p50_cost_usd is not None
```

#### Integration Test Example

```python
# tests/integration/test_estimates_api.py

from fastapi.testclient import TestClient

def test_create_estimate_endpoint(client: TestClient, auth_headers, test_project):
    """Test POST /api/v1/estimates endpoint."""
    # Arrange
    payload = {
        "project_id": str(test_project.project_id),
        "monte_carlo_iterations": 1000  # Small for test speed
    }

    # Act
    response = client.post(
        "/api/v1/estimates",
        json=payload,
        headers=auth_headers
    )

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["project_id"] == str(test_project.project_id)
    assert "estimate_id" in data
```

### Running Tests

```bash
# All tests with coverage
pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=80

# Watch mode (re-run on file changes)
pytest-watch tests/

# Specific test
pytest tests/unit/test_estimate_generator.py::test_generate_estimate_success -v
```

---

## Commit Guidelines

### Commit Message Format

**[SHARED PATTERN - Conventional Commits style]**

```
<type>(<scope>): <short summary>

<optional body>

<optional footer>
```

**Types**:
- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code formatting (no logic change)
- **refactor**: Code restructuring (no behavior change)
- **test**: Adding or updating tests
- **chore**: Maintenance tasks (dependencies, tooling)

**Examples**:

```
feat(risk-analysis): add Iman-Conover correlation support

Implement Iman-Conover method for applying correlation matrices
to Monte Carlo samples. Includes validation against reference
implementation in R.

Closes #123

---

fix(document-parser): handle multi-page table extraction

Azure DI tables spanning multiple pages were being truncated.
Now correctly merge table rows across page boundaries.

Fixes #456

---

docs(readme): update quick start guide

Add missing step for .env configuration
```

### Atomic Commits

- **One logical change per commit**
- **Don't mix refactoring with feature work**
- **All tests must pass after each commit**

```bash
# Good - Separate commits for separate concerns
git commit -m "refactor(cost-service): extract WBS builder to separate method"
git commit -m "feat(cost-service): add support for custom WBS codes"

# Bad - Mixed concerns in one commit
git commit -m "refactor code and add new feature"
```

---

## Pull Request Process

### Before Creating PR

**Checklist**:
- ✅ All tests passing (`pytest tests/`)
- ✅ Code formatted (`black`, `isort`)
- ✅ Linting passes (`flake8`, `bandit`)
- ✅ Coverage maintained (≥80% unit, ≥70% integration)
- ✅ Documentation updated (README, DEVELOPMENT, RUNBOOK if applicable)
- ✅ Commit messages follow convention

### PR Template

When creating PR, use this template:

```markdown
## Description

[Brief description of what this PR does]

## Motivation

[Why is this change needed? What problem does it solve?]

## Changes

- [Change 1]
- [Change 2]
- [Change 3]

## Testing

[Describe how you tested these changes]

```bash
# Example test commands run
pytest tests/unit/test_new_feature.py -v
pytest tests/integration/ --cov=src --cov-fail-under=80
```

## Screenshots / Examples

[If UI changes or API contract modifications, include examples]

## Checklist

- [ ] Tests added/updated (≥80% coverage)
- [ ] Documentation updated
- [ ] Commit messages follow convention
- [ ] Pre-commit hooks passing
- [ ] Ready for review
```

### PR Size Guidelines

- **Small PRs preferred**: <400 lines changed
- **Medium PRs**: 400-800 lines (requires extra justification)
- **Large PRs**: >800 lines (break into smaller PRs if possible)

**Why Small PRs?**
- Faster review cycles
- Lower risk of bugs
- Easier to revert if issues found
- Better for learning and knowledge sharing

---

## Review Process

### Review Timelines

**[SHARED PATTERN - Team agreements]**

- **Small PRs** (<200 lines): 1 business day
- **Medium PRs** (200-400 lines): 2 business days
- **Large PRs** (>400 lines): 3+ business days

### Required Approvals

- **Feature branches → develop**: 1 approver (any team member)
- **develop → main**: 2 approvers (including tech lead)
- **Hotfixes**: 1 approver (tech lead or designated backup)

### Review Criteria

Reviewers will check for:

1. **Functionality**: Does the code work as intended?
2. **Tests**: Are there adequate tests? Do they cover edge cases?
3. **Code Quality**: Does it follow coding standards?
4. **Architecture**: Does it fit the overall design?
5. **Documentation**: Is it clear how to use this?
6. **Performance**: Are there obvious performance issues?
7. **Security**: Are there security vulnerabilities?

### Addressing Feedback

- **Respond to all comments** (even if just "acknowledged")
- **Ask questions** if feedback unclear
- **Push new commits** to address feedback (don't force-push during review)
- **Request re-review** when all feedback addressed

### Merging

- **Squash-merge** to main (single commit in history)
- **Delete branch** after merge
- **Update linked issues** (closes #123)

---

## Additional Guidelines

### Documentation Updates

**When to update documentation**:
- New API endpoints → Update README and OpenAPI docs
- Behavior changes → Update DEVELOPMENT.md and RUNBOOK.md
- Deployment changes → Update DEPLOYMENT_OPERATIONS_GUIDE.md
- Architecture changes → Update ARCHITECTURE.md

### Breaking Changes

**If your change breaks backward compatibility**:
1. Discuss with team BEFORE implementing
2. Document in PR description
3. Update CHANGELOG.md
4. Bump major version (if applicable)
5. Provide migration guide

### Performance Considerations

**If your change affects performance**:
- Benchmark before/after (include in PR description)
- Consider impact at scale (1000+ estimates)
- Profile if adding database queries
- Check LLM token usage if changing prompts

---

## Questions?

- **Documentation**: Check DEVELOPMENT.md for detailed guides
- **Team Channel**: [Slack/Teams channel link]
- **Office Hours**: Weekly developer sync (Fridays 2-3 PM)
- **Email**: [team-email@example.com]

---

**Thank you for contributing to [TOOL NAME]!** 🎉
```

---

## 3. Coding Standards

**[Comprehensive coding standards document - excerpt below, full document would be separate file]**

### Python Standards Summary

```markdown
# Coding Standards for Multi-Tool Estimation Platform

## 1. Code Organization

### Module Structure

```
[tool_module]/
├── __init__.py          # Empty or package-level imports
├── main.py              # FastAPI app
├── config.py            # Pydantic settings
├── dependencies.py      # DI wiring
├── api/
│   └── v1/              # API version 1
│       ├── health.py    # Health check endpoints
│       ├── projects.py  # Project CRUD
│       └── [domain].py  # Domain-specific routes
├── models/
│   ├── enums.py         # Enumerations
│   ├── database.py      # SQLAlchemy ORM models
│   └── schemas.py       # Pydantic request/response DTOs
├── database/
│   ├── connection.py    # DB engine
│   └── repositories/    # Repository pattern
├── services/            # Business logic
├── azure/               # Azure client wrappers
└── utils/               # Logging, errors, retry
```

## 2. Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Modules | snake_case | `estimate_generator.py` |
| Classes | PascalCase | `EstimateGeneratorService` |
| Functions | snake_case | `generate_estimate()` |
| Variables | snake_case | `monte_carlo_iterations` |
| Constants | UPPER_SNAKE_CASE | `DEFAULT_ITERATIONS` |
| Private | _leading_underscore | `_internal_method()` |
| Protected | _leading_underscore | `_helper_function()` |

## 3. Type Hints

**Required for all public functions**:

```python
from typing import List, Optional, Dict, Any
from decimal import Decimal
import uuid

# All parameters and return type annotated
def compute_cost(
    line_items: List[EstimateLineItem],
    risk_factors: Optional[List[RiskFactor]] = None
) -> Decimal:
    """Compute total cost with optional risk adjustments."""
    pass
```

## 4. Docstrings

**Google style for all public classes and functions**:

```python
def generate_estimate(project_id: uuid.UUID, user_id: uuid.UUID) -> Estimate:
    """
    Generate cost estimate for project.

    Orchestrates full estimation workflow including AACE classification,
    base cost computation, Monte Carlo simulation, and LLM narrative generation.

    Args:
        project_id: Unique identifier for project to estimate
        user_id: User requesting estimate (for access checks)

    Returns:
        Complete Estimate with line items, risk factors, and narrative

    Raises:
        NotFound: Project does not exist
        Forbidden: User lacks estimate:create permission
        BusinessRuleViolation: No validated documents available
    """
    pass
```

## 5. Error Handling

**Use custom exceptions, never suppress silently**:

```python
from [tool_module].utils.errors import BusinessRuleViolation, NotFound

# Good
if not documents:
    raise BusinessRuleViolation("No validated documents for estimation")

# Bad
if not documents:
    return None  # Silent failure
```

## 6. Database Patterns

**Session management** [CRITICAL - DO NOT DEVIATE]:

```python
# dependencies.py
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()  # Auto-commit on success
    except Exception:
        db.rollback()  # Auto-rollback on error
        raise
    finally:
        db.close()

# NEVER do this in repositories/services:
db = SessionLocal()  # ❌ Wrong - breaks session management
```

**Repository pattern**:

```python
class ProjectRepository:
    def __init__(self, db: Session):  # Session injected
        self.db = db

    def get_with_access_check(
        self, project_id: uuid.UUID, user_id: uuid.UUID, permission: str
    ) -> Project:
        """Get project with RBAC check."""
        # Query + authorization logic
        pass
```

## 7. Testing Patterns

**Fixtures for dependency injection**:

```python
@pytest.fixture
def mock_llm_orchestrator():
    """Mock LLM client for unit tests."""
    mock = Mock(spec=LLMOrchestrator)
    mock.generate.return_value = "Generated narrative"
    return mock

def test_estimate_generation(mock_llm_orchestrator):
    service = EstimateGeneratorService(llm=mock_llm_orchestrator)
    # Test with mocked dependency
```

## 8. Security Rules

**Authentication** [SHARED PATTERN]:

```python
from [tool_module].dependencies import get_current_user

@router.post("/estimates")
async def create_estimate(
    payload: EstimateCreate,
    current_user: User = Depends(get_current_user),  # JWT validation
    db: Session = Depends(get_db)
):
    # current_user guaranteed to be authenticated
    pass
```

**Authorization**:

```python
# Always check ProjectAccess before operations
project = project_repo.get_with_access_check(
    project_id, user_id, "estimate:create"
)
```

**Secrets**:
- ❌ NEVER hardcode secrets in code
- ✅ Load from Azure Key Vault via config.py
- ✅ Use Managed Identity for service-to-service auth

---

**Full Standards**: See project wiki for complete coding standards guide
```

---

## 4. Backlog Templates

### User Story Template

```markdown
## User Story

**As a** [user role]
**I want** [goal/desire]
**So that** [benefit/value]

### Acceptance Criteria

- [ ] **Given** [precondition], **When** [action], **Then** [expected outcome]
- [ ] **Given** [precondition], **When** [action], **Then** [expected outcome]
- [ ] **Given** [precondition], **When** [action], **Then** [expected outcome]

### Technical Notes

[Any technical considerations, dependencies, or implementation hints]

### Definition of Done

- [ ] Code complete and reviewed
- [ ] Tests written (≥80% coverage)
- [ ] Documentation updated
- [ ] Deployed to staging and validated
- [ ] Product owner acceptance

### Estimation

**Story Points**: [Fibonacci: 1, 2, 3, 5, 8, 13]
**Estimated Hours**: [Hours for planning purposes]

---

**Example**:

## User Story: AI-Assisted Quantity Extraction

**As an** estimator
**I want** AI to extract structure counts and conductor lengths from engineering drawings
**So that** I can reduce manual quantity takeoff time from 4 hours to <5 minutes

### Acceptance Criteria

- [ ] **Given** a 50-page transmission line drawing PDF, **When** I upload to APEX, **Then** the system extracts tangent/deadend/angle structure counts with ≥90% accuracy within 30 seconds
- [ ] **Given** extracted quantities, **When** the AI is uncertain, **Then** it flags low-confidence items with source citation (drawing sheet, table row) for manual review
- [ ] **Given** conflicting information in drawings, **When** the AI detects the conflict, **Then** it lists all values with sources and prompts user to resolve

### Technical Notes

- Use Azure Document Intelligence for OCR and table extraction (async polling pattern)
- LLM prompt: `quantity_extraction` template (see prompts.py)
- Temperature: 0.1 (precise extraction, not creative)
- Max tokens: 4000 (sufficient for typical drawing summary)
- Store raw AI response in `Document.validation_result` JSON field for audit trail

### Definition of Done

- [ ] Code complete: DocumentParser service with async Azure DI integration
- [ ] Tests: ≥90% coverage with deterministic fixtures (mock Azure DI responses)
- [ ] Documentation: README updated with example API call, CLAUDE.md updated with prompt template
- [ ] Deployed to staging: 5 estimators validate with real drawings
- [ ] Product owner acceptance: 90%+ accuracy confirmed on 20-drawing sample

### Estimation

**Story Points**: 8 (1 week for 1 developer)
**Estimated Hours**: 32 hours
```

### Technical Task Template

```markdown
## Technical Task

**Task**: [Concise description of technical work]

### Context

[Why is this task needed? What problem does it solve?]

### Implementation Plan

1. [Step 1]
2. [Step 2]
3. [Step 3]

### Dependencies

- [ ] [Dependency 1]
- [ ] [Dependency 2]

### Definition of Done

- [ ] Implementation complete
- [ ] Tests written (≥80% coverage)
- [ ] Code reviewed and merged
- [ ] Documentation updated (if applicable)

### Estimation

**Hours**: [Estimated hours]

---

**Example**:

## Technical Task: Implement Iman-Conover Correlation

**Task**: Add Iman-Conover method to Monte Carlo risk analyzer for correlation preservation

### Context

Current Monte Carlo simulation samples risk factors independently, but some factors are correlated (e.g., labor cost and equipment cost). Iman-Conover method applies correlation matrix to samples while preserving marginal distributions.

Reference: Iman, R.L. and Conover, W.J. (1982) "A distribution-free approach to inducing rank correlation among input variables"

### Implementation Plan

1. Add `apply_iman_conover()` method to `RiskAnalysisService`
2. Accept correlation matrix as input (pandas DataFrame or numpy array)
3. Validate matrix is symmetric, positive semi-definite
4. Apply Cholesky decomposition and rank transformation
5. Return correlated samples with same marginal distributions
6. Add validation tests against R implementation (iman.conover package)

### Dependencies

- [ ] scipy 1.11+ (for Cholesky decomposition)
- [ ] Test data: correlation matrices from historical projects

### Definition of Done

- [ ] `apply_iman_conover()` method implemented with type hints and docstring
- [ ] Unit tests with known correlation matrices (Pearson correlation ≥0.95 to reference)
- [ ] Integration test with full Monte Carlo workflow
- [ ] Documentation: Add note to CLAUDE.md flagging human review requirement (high-risk method)
- [ ] Code review by senior developer

### Estimation

**Hours**: 16 hours (2 days)
```

### Bug Report Template

```markdown
## Bug Report

**Title**: [Concise description of issue]

### Summary

[Brief description of what's wrong]

### Steps to Reproduce

1. [First step]
2. [Second step]
3. [And so on...]

### Expected Behavior

[What should happen]

### Actual Behavior

[What actually happens]

### Environment

- **Tool Version**: [e.g., v1.0.0]
- **Environment**: [Development / Staging / Production]
- **Python Version**: [e.g., 3.11.4]
- **Database**: [Azure SQL / SQLite]

### Error Messages / Logs

```
[Paste error messages or relevant log output]
```

### Screenshots

[If applicable, add screenshots to help explain the problem]

### Additional Context

[Any other context about the problem]

### Severity

- [ ] **Critical**: Production down, data loss, security vulnerability
- [ ] **High**: Major functionality broken, many users affected
- [ ] **Medium**: Minor functionality broken, workaround exists
- [ ] **Low**: Cosmetic issue, no functionality impact

---

**Example**:

## Bug Report: Monte Carlo Fails with >1000 Line Items

### Summary

`RiskAnalysisService.run_simulation()` raises `MemoryError` when estimate has >1000 line items with independent risk factors.

### Steps to Reproduce

1. Create estimate with 1500 line items
2. Assign triangular distribution to each line item (1500 risk factors)
3. Call `POST /api/v1/estimates` with `monte_carlo_iterations=10000`
4. Observe error after ~15 seconds

### Expected Behavior

Monte Carlo completes successfully, returns P50/P80/P95 values

### Actual Behavior

API returns HTTP 500 with error:
```
MemoryError: Unable to allocate 11.2 GiB for array with shape (1500, 10000) and data type float64
```

### Environment

- **Tool Version**: APEX v1.0.0
- **Environment**: Staging
- **Python Version**: 3.11.4
- **Database**: Azure SQL Database (Business Critical)

### Error Messages / Logs

```
File "src/apex/services/risk_analysis.py", line 145, in run_simulation
  samples = np.zeros((len(risk_factors), iterations))
MemoryError: Unable to allocate 11.2 GiB for array with shape (1500, 10000) and data type float64
```

### Additional Context

- Average estimate has 200-300 line items (works fine)
- Large transmission projects can have 1000+ line items
- 1500 factors * 10K iterations * 8 bytes = 120 MB expected, actual allocation 11.2 GB suggests intermediate array blow-up

### Severity

- [x] **High**: Blocks large project estimates, affects 10-15% of use cases

### Proposed Fix

1. Chunk Monte Carlo into batches of 100 risk factors
2. Aggregate results across batches
3. Trade-off: Slower execution but bounded memory
```

---

## 5. Consistency Maintenance Guide

### Keeping the 85% Shared Pattern Aligned

**Challenge**: Six tools share 85% common architecture, but divergence can occur over time as each tool team makes changes.

### Shared Pattern Elements (MUST Stay Identical)

1. **Infrastructure as Code** (`infra/` directory)
   - Bicep templates for Azure resources
   - Only parameter files should differ (dev.bicepparam, staging.bicepparam, production.bicepparam)

2. **CI/CD Pipeline** (`.github/workflows/ci-cd.yml`)
   - Lint/test/deploy workflow identical
   - Only environment variables should differ

3. **Database Session Management** (`dependencies.py`)
   - `get_db()` function implementation sacred - DO NOT modify without RFC

4. **Common Schema** (`models/database.py`)
   - `User`, `AppRole`, `ProjectAccess`, `Project`, `Document`, `AuditLog` tables identical
   - `GUID` TypeDecorator implementation identical

5. **Security Patterns** (`azure/` and `utils/`)
   - Azure client wrappers identical
   - Error handling, retry decorators, logging identical

### Change Management for Shared Patterns

**If you need to change a shared pattern component**:

1. **Propose RFC** (Request for Comments):
   ```markdown
   Title: [RFC] Modify get_db() to support connection pooling

   Problem: Current NullPool limits performance under high concurrency

   Proposed Solution: Implement QueuePool with max 20 connections

   Impact: All six tools must upgrade dependencies.py

   Migration: [Provide upgrade guide]

   Discussion: [Link to discussion forum]
   ```

2. **Require 4/6 Tool Team Approval**:
   - Post RFC to shared channel
   - Allow 5 business days for feedback
   - Require approval from 4 of 6 tool maintainers

3. **Coordinate Rollout**:
   - Update shared library first (if applicable)
   - Provide migration guide
   - Schedule simultaneous upgrades across all tools
   - Monitor for issues in staging before production

### Quarterly Alignment Review

**Process**: Every quarter, convene all tool maintainers to review divergence

**Agenda**:
1. Compare `infra/` directories across all tools - flag differences
2. Review CI/CD pipelines - identify custom modifications
3. Check shared library versions - ensure all tools on compatible versions
4. Audit `dependencies.py` - confirm session management unchanged
5. Review `models/database.py` - verify common schema intact

**Output**: Alignment report with action items to re-converge patterns

---

**End of Developer Artifacts**

For questions or contributions to these templates, contact the platform team.
```

---

## Summary

I've successfully generated the complete multi-tool documentation template set as requested. Here's what was created in `/home/gbass/MyProjects/APEX/docs/multi-tool-templates/`:

### ✅ Deliverables Created:

1. **PATTERN_OVERVIEW.md** (21KB) - Unified vision, common architecture baseline, six-tool roadmap
2. **ARCHITECTURE_TEMPLATE.md** (59KB) - Reusable architecture specification with Azure integration
3. **TECHNICAL_SPECIFICATION_TEMPLATE.md** (88KB) - Comprehensive implementation guide with examples and placeholders
4. **LEADERSHIP_MATERIALS.md** (81KB) - Executive summary, value proposition, architecture narrative, risk assessment, roadmap
5. **DEVELOPER_ARTIFACTS.md** (40KB) - README template, CONTRIBUTING guidelines, coding standards, backlog templates

### 📊 Total Documentation: ~290KB, ready for reuse

### Key Features:

**Pattern Overview**:
- Unified problem statement for six AI estimation tools
- 85% shared architecture, 15% tool-specific customization
- Shared library strategy (estimating-ai-core, estimating-connectors, estimating-security)
- Proven foundation from APEX (95/100 production readiness)

**Architecture Template**:
- Zero-trust network design with Private Endpoints
- Layered architecture (API → Service → Repository → Data)
- Technology stack recommendations with trade-off analysis
- Security architecture and compliance requirements

**Technical Specification**:
- Fill-in-the-blank template with APEX examples
- API endpoint documentation with OpenAPI schemas
- Database modeling with SQLAlchemy patterns
- AI integration guidelines (prompts, token management, safety)

**Leadership Materials**:
- Executive summary with ROI calculation (16-month payback, $750K 3-year NPV)
- Business + IT value propositions
- Risk assessment with mitigation strategies
- Multi-year roadmap (APEX complete, Tools 2-6 phased through 2026)

**Developer Artifacts**:
- README template with quick start guide
- CONTRIBUTING guidelines with PR process
- Coding standards (PEP 8, type hints, docstrings)
- Backlog templates (user stories, technical tasks, bug reports)

### Next Steps for Using These Templates:

1. **Copy templates to new tool repositories** with minimal customization needed
2. **Replace [PLACEHOLDER] text** with tool-specific details
3. **Keep [SHARED PATTERN] sections identical** across all six tools
4. **Use APEX as reference implementation** for filling in examples
5. **Present Leadership Materials to IT Review Board** for architecture approval

All templates follow the structure you specified in your revised prompt, incorporating the answers I provided to your 6 clarifying questions. The templates are production-ready and can accelerate development of Tools 2-6 by providing 85% of the documentation upfront.