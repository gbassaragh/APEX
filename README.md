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

See [CLAUDE.md](CLAUDE.md) for detailed development guidance and architecture documentation.

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
