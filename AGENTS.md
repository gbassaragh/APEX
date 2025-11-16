# Repository Guidelines

## Project Structure & Module Organization
- `src/apex/`: FastAPI app, services (`services/`), Azure adapters (`azure/`), database models/repositories (`models/`, `database/`), and API routers (`api/v1/`).
- `tests/`: `unit/` for isolated components, `integration/` for API/database flows, shared fixtures in `tests/fixtures/`.
- `alembic/`: Migration environment; versions are auto-generated into `alembic/versions/`.
- `infra/`: Bicep templates and deployment scripts; parameters per environment in `infra/parameters/`.
- Root helpers: `pyproject.toml` (deps/tooling), `validation_commands.sh`, `Dockerfile`, and docs such as `DEVELOPMENT.md`, `RUNBOOK.md`, `CLAUDE.md`.

## Build, Test, and Development Commands
- Install/editable deps: `pip install -e .` (use `python3.11 -m venv venv && source venv/bin/activate` first).
- Run dev API: `uvicorn apex.main:app --reload --host 0.0.0.0 --port 8000`.
- Migrations: `alembic upgrade head` (apply), `alembic revision --autogenerate -m "...“` (create).
- Validation bundle: `./validation_commands.sh` or run tools individually (below).
- Tests: `pytest tests/` (all), `pytest tests/unit -v`, `pytest tests/integration -v`, `pytest tests --cov=apex --cov-report=term-missing` (coverage).

## Coding Style & Naming Conventions
- Formatting: `black` (100-char lines) + `isort --profile black`; enforce via pre-commit hooks (`./.githooks/install-hooks.sh` or `pre-commit install`).
- Linting: `flake8`, `ruff`, `bandit` (security); keep fixes in CI-ready state before pushing.
- Typing/docstrings: Type hints on public functions; Google-style docstrings where helpful.
- Naming: modules/vars/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE_CASE`; keep API routes versioned under `src/apex/api/v1/`.

## Testing Guidelines
- Framework: `pytest` with fixtures in `tests/fixtures/`; prefer isolated unit tests for services and repositories, and integration tests for API/database behaviors.
- Conventions: Name test files `test_<area>.py` and functions `test_<behavior>`.
- Coverage: Target 100% for new/modified code; add regression tests alongside fixes.
- Setup: Use provided fixtures/mocks for Azure and DB; avoid hitting live services in tests.

## Commit & Pull Request Guidelines
- Commits: Short, imperative summaries (e.g., “Fix estimate routing bug”); run pre-commit hooks before committing.
- PRs: Include purpose, linked issue/story, and testing evidence (`pytest …`, `alembic upgrade head` if applicable). Add screenshots or API examples when UI/contract changes occur.
- Scope: Keep PRs small and focused; update docs (README/DEVELOPMENT/RUNBOOK) when behavior or operations change.

## Security & Configuration Tips
- Never commit secrets; use `.env` locally and Azure Key Vault in environments.
- Required env vars include Azure SQL/OpenAI/Blob/Key Vault settings (see `.env.example`); export or load them before running services or tests.
- Prefer managed identity/Key Vault retrievals over inline connection strings; follow guidance in `src/apex/azure/` and `infra/SECURITY_VALIDATION.md`.
