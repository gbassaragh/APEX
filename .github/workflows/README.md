# APEX CI/CD Pipeline Documentation

## Overview

The APEX CI/CD pipeline automates building, testing, and deploying the APEX backend to Azure Container Apps across development, staging, and production environments.

## Pipeline Stages

### 1. Code Quality & Security (code-quality)
- **Runs on:** All pushes and pull requests
- **Tasks:**
  - Code formatting check (Black, line-length=100)
  - Import ordering check (isort)
  - Linting (Flake8)
  - Security scanning (Bandit)
- **Artifacts:** `bandit-security-report` (JSON)

### 2. Tests (test)
- **Runs on:** After code quality passes
- **Tasks:**
  - Unit tests (`tests/unit/`)
  - Integration tests (`tests/integration/`)
  - Code coverage reporting (Codecov)
- **Artifacts:** `pytest-results`, coverage reports

### 3. Build (build)
- **Runs on:** After tests pass
- **Tasks:**
  - Build Docker image
  - Push to Azure Container Registry
  - Vulnerability scanning (Trivy)
  - Cache layers for faster builds
- **Outputs:** Image tag and digest

### 4. Deploy to Development (deploy-dev)
- **Triggers:**
  - Pushes to `develop` branch
  - Manual workflow dispatch with `environment: dev`
- **Tasks:**
  - Deploy infrastructure via Bicep
  - Update Container App with new image
  - Run database migrations (TODO)
  - Health checks

### 5. Deploy to Staging (deploy-staging)
- **Triggers:**
  - Pushes to `main` branch (not PRs)
- **Requires:** Successful dev deployment
- **Tasks:**
  - Deploy infrastructure via Bicep
  - Update Container App with new image
  - Smoke tests
  - Health checks

### 6. Deploy to Production (deploy-prod)
- **Triggers:**
  - **Manual approval required** (workflow_dispatch with `environment: prod`)
- **Requires:** Successful staging deployment
- **Tasks:**
  - Infrastructure deployment
  - Blue-Green deployment with gradual traffic shifting (TODO)
  - Database migrations (TODO)
  - Production health checks
  - Automated rollback on failure (TODO)

## Required GitHub Secrets

### Azure Credentials
- `AZURE_CREDENTIALS_DEV` - Service principal for dev environment
- `AZURE_CREDENTIALS_STAGING` - Service principal for staging
- `AZURE_CREDENTIALS_PROD` - Service principal for production

### Azure Container Registry
- `AZURE_CONTAINER_REGISTRY` - ACR hostname (e.g., `apexregistry.azurecr.io`)
- `AZURE_ACR_USERNAME` - ACR admin username
- `AZURE_ACR_PASSWORD` - ACR admin password

## Setting Up Azure Service Principals

```bash
# Development environment
az ad sp create-for-rbac \
  --name "apex-github-actions-dev" \
  --role contributor \
  --scopes /subscriptions/{subscription-id}/resourceGroups/apex-rg-dev \
  --sdk-auth

# Staging environment
az ad sp create-for-rbac \
  --name "apex-github-actions-staging" \
  --role contributor \
  --scopes /subscriptions/{subscription-id}/resourceGroups/apex-rg-staging \
  --sdk-auth

# Production environment (minimum permissions)
az ad sp create-for-rbac \
  --name "apex-github-actions-prod" \
  --role contributor \
  --scopes /subscriptions/{subscription-id}/resourceGroups/apex-rg-prod \
  --sdk-auth
```

Save the JSON output as GitHub secrets (`AZURE_CREDENTIALS_DEV`, etc.).

## Manual Production Deployment

1. Navigate to **Actions** → **APEX CI/CD Pipeline**
2. Click **Run workflow**
3. Select `environment: prod`
4. Click **Run workflow**
5. Approve deployment in **Environments** → **production**

## Branch Strategy

- `develop` → Automatic deployment to **Development**
- `main` → Automatic deployment to **Staging**, manual to **Production**
- `feature/*` → CI checks only (no deployment)

## Rollback Procedure

### Automatic Rollback (TODO - Not yet implemented)
- Health check failures trigger automatic rollback
- Reverts to previous Container App revision

### Manual Rollback
```bash
# List revisions
az containerapp revision list \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --output table

# Activate previous revision
az containerapp revision activate \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision {previous-revision-name}
```

## Database Migrations

### Current State (TODO)
Database migrations via Alembic are not yet automated in the pipeline.

### Planned Implementation
- Run migrations via Azure Container Apps exec
- Run as pre-deployment job
- Validate migration success before traffic shifting

### Manual Migration
```bash
# Connect to container
az containerapp exec \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --command bash

# Inside container
alembic upgrade head
```

## Monitoring Deployment

### GitHub Actions UI
- View real-time logs for each job
- Monitor deployment status
- Download artifacts (test results, security reports)

### Azure Portal
- Container App logs: Application Insights
- Deployment history: Container App → Revisions
- Traffic distribution: Container App → Ingress

## Troubleshooting

### Build Failures
- Check Docker build logs
- Verify all dependencies in `pyproject.toml`
- Check ODBC driver installation

### Test Failures
- Review pytest output in GitHub Actions logs
- Download `pytest-results` artifact for detailed analysis
- Check code coverage report

### Deployment Failures
- Verify Azure credentials are valid
- Check resource group exists
- Verify Container App configuration
- Review Bicep deployment logs

### Health Check Failures
- Verify `/health/ready` endpoint is accessible
- Check Application Insights for errors
- Review Container App logs

## Security Scanning

### Bandit (Python Security)
- Scans for common security issues in Python code
- Report available as artifact: `bandit-security-report`

### Trivy (Container Vulnerabilities)
- Scans Docker image for known vulnerabilities
- Results uploaded to GitHub Security tab
- Fails build on HIGH/CRITICAL vulnerabilities

## TODO Items

- [ ] Implement database migration automation
- [ ] Implement blue-green deployment with traffic shifting
- [ ] Implement automated rollback on health check failure
- [ ] Add notification system (Slack, Teams, email)
- [ ] Add performance testing in staging
- [ ] Implement canary deployments for production
- [ ] Add end-to-end smoke tests
- [ ] Implement feature flags for gradual rollouts

## Contact

For questions or issues with the CI/CD pipeline, contact the APEX development team.
