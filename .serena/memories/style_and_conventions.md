# Style and conventions
- Formatting: black with 100-char lines and isort (profile black). Run via pre-commit; hooks installable through `./.githooks/install-hooks.sh` or `pre-commit install`.
- Linting: flake8, ruff, bandit for security; keep code CI-ready.
- Typing/docstrings: type hints on public functions; Google-style docstrings when helpful.
- Naming: snake_case for modules/vars/functions; PascalCase for classes; UPPER_SNAKE_CASE for constants; API routes versioned under `src/apex/api/v1/`.
- Testing: pytest with fixtures in `tests/fixtures`; prefer unit tests for services/repos and integration tests for API/DB flows; target 100% coverage on new/changed code; use `test_<area>.py` and `test_<behavior>` naming.
- Security: never commit secrets; use `.env` locally and Azure Key Vault/managed identity in environments; required env vars listed in `.env.example`; follow `src/apex/azure/` and `infra/SECURITY_VALIDATION.md` guidance.
