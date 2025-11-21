# APEX overview
- Purpose: AI-powered estimation platform for utility T&D projects; ingests documents, validates, classifies (AACE Class 1–5), runs Monte Carlo risk, manages relational CBS/WBS, and provides audit trails for regulatory submissions.
- Stack: Python 3.11+ with FastAPI; Azure SQL (SQLAlchemy + Alembic); Azure OpenAI (GPT-4); Azure AI Document Intelligence; Azure Blob Storage; Azure Container Apps.
- Structure: `src/apex` app with services, Azure adapters, models/repositories, and API routers under `api/v1/`; tests split into `tests/unit` and `tests/integration` with fixtures in `tests/fixtures`; migrations under `alembic/`; infra scripts/templates under `infra/`; root helpers include `pyproject.toml`, `validation_commands.sh`, `Dockerfile`, and docs (`README.md`, `DEVELOPMENT.md`, `RUNBOOK.md`, `CLAUDE.md`).
- Entry points: FastAPI app `apex.main:app` (dev via uvicorn); Alembic migrations; validation/test commands in `validation_commands.sh`.
