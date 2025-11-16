# APEX – AI-Powered Estimation Expert

Enterprise estimation platform for utility transmission and distribution projects.

## Overview

APEX automates cost estimation for utility T&D projects through:
- Intelligent document ingestion (PDFs, Word, Excel)
- AI-based document validation
- AACE-compliant estimate classification (Class 1–5)
- Industrial-grade Monte Carlo risk analysis
- Relational cost breakdown structures (CBS/WBS)
- Full audit trail for regulatory submissions

## Technology Stack

- **Python 3.11+** with FastAPI
- **Azure SQL Database** (SQLAlchemy + Alembic)
- **Azure OpenAI** (GPT-4)
- **Azure AI Document Intelligence**
- **Azure Blob Storage**
- **Azure Container Apps**

## Quick Start

```bash
# Install dependencies
pip install -e .

# Install pre-commit hooks (REQUIRED before committing)
./.githooks/install-hooks.sh
# OR: pip install pre-commit && pre-commit install

# Configure environment
cp .env.example .env
# Edit .env with your Azure credentials

# Run database migrations
alembic upgrade head

# Start development server
uvicorn apex.main:app --reload

# Run tests
pytest tests/
```

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for comprehensive development guide including:
- Pre-commit hook setup and usage
- Code quality standards
- Common development tasks
- Troubleshooting guide

See [CLAUDE.md](CLAUDE.md) for detailed architecture documentation and implementation requirements.

## Project Structure

```
apex/
├── src/apex/           # Main application code
├── tests/              # Test suite
├── alembic/            # Database migrations
└── pyproject.toml      # Dependencies
```

## License

See [LICENSE](LICENSE) file for details.
