# Suggested commands
- Setup venv: `python3.11 -m venv venv && source venv/bin/activate`
- Install deps editable: `pip install -e .`
- Install pre-commit hooks: `./.githooks/install-hooks.sh` (or `pre-commit install`)
- Run dev API: `uvicorn apex.main:app --reload --host 0.0.0.0 --port 8000`
- Migrations: `alembic upgrade head`; create new: `alembic revision --autogenerate -m "<message>"`
- Tests: `pytest tests/` (all); `pytest tests/unit -v`; `pytest tests/integration -v`; coverage `pytest tests --cov=apex --cov-report=term-missing`
- Validation bundle: `./validation_commands.sh` (runs formatting/lint/test set)
- Formatting/linting individually: `black .`; `isort --profile black .`; `flake8`; `ruff .`; `bandit -r src`
- Dev docs: read `DEVELOPMENT.md`, `CLAUDE.md`, `RUNBOOK.md`; environment setup `cp .env.example .env`
