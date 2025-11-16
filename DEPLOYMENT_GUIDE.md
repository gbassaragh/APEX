# APEX Deployment Guide

**Version**: 1.0.0
**Target Platform**: Azure Container Apps
**Date**: 2025-11-15

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Database Setup](#database-setup)
4. [Container Deployment](#container-deployment)
5. [Environment Configuration](#environment-configuration)
6. [Post-Deployment Verification](#post-deployment-verification)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Tools

```bash
# Azure CLI (latest version)
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
az --version  # Verify installation

# Docker (for local testing)
sudo apt-get update
sudo apt-get install docker.io
docker --version

# Python 3.11+ (for local development)
python3 --version
```

### Required Azure Services

- Azure subscription with Contributor access
- Resource group creation permissions
- Service principal for deployments (optional for CI/CD)

### Azure Service Requirements

| Service | SKU | Purpose |
|---------|-----|---------|
| Azure SQL Database | Standard S2 | Relational database |
| Azure Blob Storage | Standard LRS | Document storage |
| Azure OpenAI | Standard | LLM validation |
| Azure Document Intelligence | S0 | PDF/document parsing |
| Azure Container Apps | Consumption | Application runtime |
| Azure Application Insights | - | Monitoring & logging |
| Azure Key Vault | Standard | Secrets management (optional) |

---

## Infrastructure Setup

### Option 1: Bicep Infrastructure as Code (Recommended)

The `infrastructure/bicep/` directory contains reusable modules for all Azure resources.

**Step 1: Review deployment parameters**

```bash
cd infrastructure/bicep
cat main.parameters.dev.json
```

**Step 2: Deploy infrastructure**

```bash
# Login to Azure
az login

# Set subscription
az account set --subscription "Your-Subscription-ID"

# Create resource group
az group create \
  --name rg-apex-dev \
  --location eastus

# Deploy infrastructure
az deployment group create \
  --resource-group rg-apex-dev \
  --template-file main.bicep \
  --parameters @main.parameters.dev.json \
  --parameters sqlAdminPassword="<SecurePassword>"
```

**Step 3: Verify deployment**

```bash
# List deployed resources
az resource list \
  --resource-group rg-apex-dev \
  --output table
```

### Option 2: Azure Portal Manual Setup

<details>
<summary>Click to expand manual setup steps</summary>

#### 1. Create Azure SQL Database

1. Navigate to Azure Portal → Create a resource → SQL Database
2. Configuration:
   - **Resource group**: `rg-apex-dev`
   - **Database name**: `apex-db`
   - **Server**: Create new
     - Server name: `apex-sql-server-dev`
     - Location: `East US`
     - Authentication: `Use Microsoft Entra authentication only`
   - **Compute + storage**: Standard S2 (50 DTU)
   - **Backup storage redundancy**: Locally-redundant
3. Networking:
   - **Connectivity method**: Private endpoint
   - **Allow Azure services**: Yes

#### 2. Create Azure Blob Storage

1. Navigate to Azure Portal → Create a resource → Storage account
2. Configuration:
   - **Resource group**: `rg-apex-dev`
   - **Storage account name**: `apexstoragedev` (must be globally unique)
   - **Performance**: Standard
   - **Redundancy**: Locally-redundant storage (LRS)
3. Networking:
   - **Network access**: Enable public access from selected virtual networks
   - **Private endpoint**: Add private endpoint
4. Create containers:
   - `uploads` (Private access)
   - `dead-letter-queue` (Private access)

#### 3. Create Azure OpenAI Service

1. Navigate to Azure Portal → Create a resource → Azure OpenAI
2. Configuration:
   - **Resource group**: `rg-apex-dev`
   - **Region**: `East US`
   - **Name**: `apex-openai-dev`
   - **Pricing tier**: Standard S0
3. Deploy model:
   - Go to Azure OpenAI Studio
   - Deployments → Create new deployment
   - Model: `gpt-4` or `gpt-4-32k`
   - Deployment name: `gpt-4-deployment`

#### 4. Create Azure Document Intelligence

1. Navigate to Azure Portal → Create a resource → Document Intelligence
2. Configuration:
   - **Resource group**: `rg-apex-dev`
   - **Region**: `East US`
   - **Name**: `apex-doc-intel-dev`
   - **Pricing tier**: S0

#### 5. Create Azure Container Apps Environment

1. Navigate to Azure Portal → Create a resource → Container Apps
2. Create environment first:
   - **Resource group**: `rg-apex-dev`
   - **Name**: `apex-env-dev`
   - **Region**: `East US`
   - **Zone redundancy**: Disabled (for dev)
3. Create Container App:
   - **Name**: `apex-app-dev`
   - **Container image**: Will be updated via CI/CD
   - **Ingress**: Enabled, HTTP only, Port 8000
   - **Scale**: Min 1, Max 10

</details>

---

## Database Setup

### Step 1: Create Database Schema

The Alembic migrations handle all schema creation automatically.

```bash
# Install dependencies
pip install -e .

# Set environment variables (temporary for migration)
export AZURE_SQL_SERVER="apex-sql-server-dev.database.windows.net"
export AZURE_SQL_DATABASE="apex-db"
export AZURE_AD_TENANT_ID="your-tenant-id"
export AZURE_AD_CLIENT_ID="your-client-id"
export TESTING="false"

# Run migrations
alembic upgrade head

# Verify tables created
az sql db show \
  --resource-group rg-apex-dev \
  --server apex-sql-server-dev \
  --name apex-db
```

### Step 2: Seed Reference Data (Optional)

```sql
-- Connect to database and run:
-- Seed AppRole table
INSERT INTO app_role (id, role_name) VALUES
(1, 'Estimator'),
(2, 'Manager'),
(3, 'Auditor');

-- Verify
SELECT * FROM app_role;
```

---

## Container Deployment

### Step 1: Build Container Image

```bash
# Build Docker image
docker build -t apex:1.0.0 .

# Test locally
docker run -p 8000:8000 \
  -e AZURE_SQL_SERVER="..." \
  -e AZURE_OPENAI_ENDPOINT="..." \
  apex:1.0.0

# Test health endpoint
curl http://localhost:8000/health/live
```

### Step 2: Push to Azure Container Registry

```bash
# Create container registry (one-time setup)
az acr create \
  --resource-group rg-apex-dev \
  --name apexregistrydev \
  --sku Basic

# Login to registry
az acr login --name apexregistrydev

# Tag and push image
docker tag apex:1.0.0 apexregistrydev.azurecr.io/apex:1.0.0
docker push apexregistrydev.azurecr.io/apex:1.0.0
```

### Step 3: Deploy to Container Apps

```bash
# Update container app with new image
az containerapp update \
  --name apex-app-dev \
  --resource-group rg-apex-dev \
  --image apexregistrydev.azurecr.io/apex:1.0.0 \
  --set-env-vars \
    DEBUG=false \
    ENVIRONMENT=development \
    AZURE_SQL_SERVER=apex-sql-server-dev.database.windows.net \
    AZURE_SQL_DATABASE=apex-db \
    AZURE_OPENAI_ENDPOINT=https://apex-openai-dev.openai.azure.com/ \
    AZURE_OPENAI_DEPLOYMENT=gpt-4-deployment \
    AZURE_DI_ENDPOINT=https://apex-doc-intel-dev.cognitiveservices.azure.com/ \
    AZURE_STORAGE_ACCOUNT=apexstoragedev \
    CORS_ORIGINS="https://apex-frontend.azurewebsites.net" \
    LOG_LEVEL=INFO

# Verify deployment
az containerapp show \
  --name apex-app-dev \
  --resource-group rg-apex-dev \
  --query "properties.latestRevisionName"
```

---

## Environment Configuration

### Required Environment Variables

Create a `.env` file for local development (never commit to Git):

```bash
# Application
APP_NAME="APEX"
APP_VERSION="1.0.0"
ENVIRONMENT="development"  # development | staging | production
DEBUG="false"              # MUST be false in production
LOG_LEVEL="INFO"          # DEBUG | INFO | WARNING | ERROR

# Azure SQL Database
AZURE_SQL_SERVER="apex-sql-server-dev.database.windows.net"
AZURE_SQL_DATABASE="apex-db"

# Azure OpenAI
AZURE_OPENAI_ENDPOINT="https://apex-openai-dev.openai.azure.com/"
AZURE_OPENAI_DEPLOYMENT="gpt-4-deployment"

# Azure Document Intelligence
AZURE_DI_ENDPOINT="https://apex-doc-intel-dev.cognitiveservices.azure.com/"

# Azure Blob Storage
AZURE_STORAGE_ACCOUNT="apexstoragedev"
AZURE_STORAGE_CONTAINER_UPLOADS="uploads"

# Azure AD (Authentication)
AZURE_AD_TENANT_ID="your-tenant-id"
AZURE_AD_CLIENT_ID="your-client-id"

# CORS (Production: Set to actual frontend domain)
CORS_ORIGINS="https://apex-frontend.azurewebsites.net,http://localhost:3000"

# Application Insights
AZURE_APPINSIGHTS_CONNECTION_STRING="InstrumentationKey=...;IngestionEndpoint=..."

# Upload Limits
MAX_UPLOAD_SIZE_MB="50"
ALLOWED_MIME_TYPES="application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Monte Carlo Settings
DEFAULT_MONTE_CARLO_ITERATIONS="10000"
```

### Azure Container Apps Configuration

Set environment variables in Azure Portal:

1. Navigate to Container App → Configuration → Environment variables
2. Add each variable from the list above
3. For secrets (not used since we use Managed Identity), mark as "Secret"

---

## Post-Deployment Verification

### Step 1: Health Checks

```bash
# Get Container App FQDN
APEX_URL=$(az containerapp show \
  --name apex-app-dev \
  --resource-group rg-apex-dev \
  --query "properties.configuration.ingress.fqdn" \
  --output tsv)

# Test liveness endpoint
curl https://$APEX_URL/health/live

# Test readiness endpoint (checks database)
curl https://$APEX_URL/health/ready

# Expected responses:
# {"status": "alive"}
# {"status": "ready", "database": "connected"}
```

### Step 2: Smoke Tests

```bash
# Test root endpoint
curl https://$APEX_URL/

# Expected response:
# {
#   "name": "APEX",
#   "version": "1.0.0",
#   "status": "operational",
#   "docs": "disabled"
# }

# Test authentication (requires valid AAD token)
TOKEN="your-aad-token"
curl -H "Authorization: Bearer $TOKEN" \
  https://$APEX_URL/api/v1/projects

# Expected: 200 OK with empty project list or 401 if token invalid
```

### Step 3: Monitoring Verification

```bash
# Check Application Insights logs
az monitor app-insights query \
  --app $(az monitor app-insights component show \
    --resource-group rg-apex-dev \
    --query "[0].name" -o tsv) \
  --analytics-query "requests | where timestamp > ago(1h) | take 10"

# Expected: Recent request logs from health checks
```

---

## Troubleshooting

### Container Won't Start

**Check logs**:
```bash
az containerapp logs show \
  --name apex-app-dev \
  --resource-group rg-apex-dev \
  --type console \
  --tail 50
```

**Common issues**:
- Missing environment variables → Check Configuration
- Database connection failure → Verify Managed Identity permissions
- Image pull failure → Check Azure Container Registry access

### Database Connection Errors

**Error**: `Login failed for user 'NT AUTHORITY\ANONYMOUS LOGON'`

**Solution**: Configure Managed Identity for Azure SQL

```bash
# Assign Managed Identity to Container App
az containerapp identity assign \
  --name apex-app-dev \
  --resource-group rg-apex-dev \
  --system-assigned

# Get Managed Identity Object ID
IDENTITY_ID=$(az containerapp identity show \
  --name apex-app-dev \
  --resource-group rg-apex-dev \
  --query principalId -o tsv)

# Grant SQL permissions (run in SQL database):
# CREATE USER [apex-app-dev] FROM EXTERNAL PROVIDER;
# ALTER ROLE db_datareader ADD MEMBER [apex-app-dev];
# ALTER ROLE db_datawriter ADD MEMBER [apex-app-dev];
```

### Azure Service Permissions

**Error**: `BlobNotFound` or `Unauthorized`

**Solution**: Grant Managed Identity access to Blob Storage

```bash
# Get Container App Managed Identity
IDENTITY_ID=$(az containerapp identity show \
  --name apex-app-dev \
  --resource-group rg-apex-dev \
  --query principalId -o tsv)

# Grant Storage Blob Data Contributor role
az role assignment create \
  --assignee $IDENTITY_ID \
  --role "Storage Blob Data Contributor" \
  --scope /subscriptions/{sub-id}/resourceGroups/rg-apex-dev/providers/Microsoft.Storage/storageAccounts/apexstoragedev
```

### CORS Errors

**Error**: `Access-Control-Allow-Origin` missing

**Solution**: Update CORS_ORIGINS environment variable

```bash
az containerapp update \
  --name apex-app-dev \
  --resource-group rg-apex-dev \
  --set-env-vars CORS_ORIGINS="https://your-frontend-domain.com"
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy to Azure Container Apps

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Login to Azure
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Build and push Docker image
        run: |
          az acr build \
            --registry apexregistrydev \
            --image apex:${{ github.sha }} \
            --file Dockerfile .

      - name: Deploy to Container Apps
        run: |
          az containerapp update \
            --name apex-app-dev \
            --resource-group rg-apex-dev \
            --image apexregistrydev.azurecr.io/apex:${{ github.sha }}

      - name: Run smoke tests
        run: |
          APEX_URL=$(az containerapp show \
            --name apex-app-dev \
            --resource-group rg-apex-dev \
            --query "properties.configuration.ingress.fqdn" \
            --output tsv)
          curl -f https://$APEX_URL/health/ready || exit 1
```

---

## Rollback Procedure

### Quick Rollback to Previous Revision

```bash
# List revisions
az containerapp revision list \
  --name apex-app-dev \
  --resource-group rg-apex-dev \
  --output table

# Activate previous revision
az containerapp revision activate \
  --name apex-app-dev \
  --resource-group rg-apex-dev \
  --revision <previous-revision-name>

# Deactivate current (broken) revision
az containerapp revision deactivate \
  --name apex-app-dev \
  --resource-group rg-apex-dev \
  --revision <broken-revision-name>
```

### Database Migration Rollback

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision-id>

# Verify current version
alembic current
```

---

## Security Hardening Post-Deployment

### 1. Enable Private Endpoints

```bash
# SQL Database private endpoint
az network private-endpoint create \
  --name apex-sql-pe \
  --resource-group rg-apex-dev \
  --vnet-name apex-vnet \
  --subnet apex-subnet \
  --private-connection-resource-id <sql-resource-id> \
  --group-id sqlServer \
  --connection-name apex-sql-connection
```

### 2. Configure Firewall Rules

```bash
# Restrict Azure SQL to Azure services only
az sql server firewall-rule create \
  --resource-group rg-apex-dev \
  --server apex-sql-server-dev \
  --name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0

# Delete any public IP rules
az sql server firewall-rule delete \
  --resource-group rg-apex-dev \
  --server apex-sql-server-dev \
  --name AllowAll
```

### 3. Enable Storage HTTPS-Only

```bash
az storage account update \
  --resource-group rg-apex-dev \
  --name apexstoragedev \
  --https-only true
```

---

## Scaling Configuration

### Auto-Scaling Rules

```bash
# Configure scaling rules
az containerapp update \
  --name apex-app-dev \
  --resource-group rg-apex-dev \
  --min-replicas 1 \
  --max-replicas 10 \
  --scale-rule-name cpu-scaling \
  --scale-rule-type cpu \
  --scale-rule-metadata concurrentRequests=50

# Monitor scaling
az containerapp replica list \
  --name apex-app-dev \
  --resource-group rg-apex-dev \
  --output table
```

---

## Backup and Disaster Recovery

### Database Backups

Azure SQL Database provides automatic backups:
- Point-in-time restore: 7-35 days
- Long-term retention: Up to 10 years (optional)

**Manual backup**:
```bash
az sql db copy \
  --resource-group rg-apex-dev \
  --server apex-sql-server-dev \
  --name apex-db \
  --dest-name apex-db-backup-$(date +%Y%m%d)
```

### Blob Storage Backups

**Enable soft delete**:
```bash
az storage blob service-properties delete-policy update \
  --account-name apexstoragedev \
  --enable true \
  --days-retained 14
```

---

## Support Contacts

### Azure Support
- Portal: https://portal.azure.com → Help + support
- Phone: 1-800-642-7676 (US)

### Application Support
- Email: apex-support@your-company.com
- On-call: PagerDuty / OpsGenie

---

## Appendix

### Environment-Specific Configuration

| Environment | Resource Group | FQDN |
|-------------|----------------|------|
| Development | rg-apex-dev | apex-app-dev.niceocean-12345678.eastus.azurecontainerapps.io |
| Staging | rg-apex-staging | apex-app-staging.niceocean-87654321.eastus.azurecontainerapps.io |
| Production | rg-apex-prod | api.apex.your-company.com |

### Useful Azure CLI Commands

```bash
# View all resources in resource group
az resource list --resource-group rg-apex-dev --output table

# Get Container App logs
az containerapp logs show --name apex-app-dev --resource-group rg-apex-dev --tail 100

# Restart Container App
az containerapp revision restart --name apex-app-dev --resource-group rg-apex-dev

# Get Managed Identity details
az containerapp identity show --name apex-app-dev --resource-group rg-apex-dev
```

---

**Document Version**: 1.0.0
**Last Updated**: 2025-11-15
**Maintained By**: DevOps Team
