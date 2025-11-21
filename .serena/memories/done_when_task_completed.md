# Task completion checklist
- Run relevant tests (`pytest` scope impacted code) and/or full `./validation_commands.sh`; ensure coverage for new/modified code (aim 100%).
- Run formatting/linting (`black`, `isort --profile black`, `flake8`, `ruff`, `bandit`) or rely on pre-commit hooks to pass.
- Update docs if behavior/operations change (`README.md`, `DEVELOPMENT.md`, `RUNBOOK.md`, API examples/screenshots for contract/UI changes).
- Ensure migrations applied/created when DB schema changes (`alembic upgrade head` or new revision with message).
- Confirm no secrets committed; environment variables sourced from `.env`/Key Vault; configuration follows security guidance.
- For PRs: provide short imperative summary, link issue/story, include testing evidence (commands and results), and attach relevant artifacts (screenshots/API samples) when applicable.
