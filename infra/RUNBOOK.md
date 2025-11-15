# APEX Production Deployment Runbook

**Version:** 1.0
**Last Updated:** 2024
**Owner:** DevOps Team
**Purpose:** Detailed step-by-step procedures for production deployment operations

## Overview

This runbook provides comprehensive, executable procedures for all production deployment activities. Each procedure includes exact commands, expected outputs, troubleshooting steps, and rollback instructions.

**Target Audience:**
- Deployment Engineers
- On-Call Engineers
- Operations Team
- Technical Leads

**Prerequisites:**
- Azure CLI installed and authenticated (`az login`)
- Access to production Azure subscription
- Access to production resource group (`apex-rg-prod`)
- kubectl configured (if using AKS instead of Container Apps)
- Database client installed (Azure Data Studio or SQL Server Management Studio)

---

## Table of Contents

1. [Infrastructure Deployment](#infrastructure-deployment)
2. [Database Migration](#database-migration)
3. [Application Deployment](#application-deployment)
4. [Smoke Tests](#smoke-tests)
5. [Traffic Shifting](#traffic-shifting)
6. [Rollback Procedure](#rollback-procedure)
7. [Emergency Procedures](#emergency-procedures)
8. [Common Troubleshooting](#common-troubleshooting)

---

## Infrastructure Deployment

### Procedure: Deploy Azure Infrastructure with Bicep

**Duration:** ~15-20 minutes
**Rollback:** Infrastructure changes are destructive - test in staging first

#### Step 1: Prepare for Deployment

```bash
# Set variables
export ENVIRONMENT="prod"
export RESOURCE_GROUP="apex-rg-prod"
export LOCATION="eastus"

# Navigate to infrastructure directory
cd /home/gbass/MyProjects/APEX/infra

# Verify Azure CLI authentication
az account show

# Expected output: Your production Azure subscription details
```

#### Step 2: Validate Bicep Template

```bash
# Validate Bicep syntax and parameters
az deployment group validate \
  --resource-group "$RESOURCE_GROUP" \
  --template-file main.bicep \
  --parameters parameters/prod.bicepparam

# Expected output: "provisioningState": "Succeeded"
```

**If validation fails:**
- Check Bicep syntax errors in output
- Verify all parameters in `parameters/prod.bicepparam`
- Ensure resource group exists: `az group show --name "$RESOURCE_GROUP"`

#### Step 3: Run What-If Analysis

```bash
# Preview infrastructure changes
az deployment group what-if \
  --resource-group "$RESOURCE_GROUP" \
  --template-file main.bicep \
  --parameters parameters/prod.bicepparam \
  --result-format FullResourcePayloads

# Expected output: List of resources to be created/modified/deleted
```

**Review carefully:**
- ✅ Expected: New Container App revision, updated configuration
- ⚠️ Warning: Resource deletion (should not happen in normal deployment)
- ❌ Unexpected: Changes to VNet, NSGs, Private Endpoints (should be stable)

#### Step 4: Execute Deployment Script

```bash
# Run deployment script (includes production confirmations)
./deploy.sh prod apex-rg-prod

# You will be prompted:
# 1. "Have you obtained change approval? (yes/no):" → Type: yes
# 2. "Type 'DEPLOY-TO-PRODUCTION' to confirm:" → Type: DEPLOY-TO-PRODUCTION
```

**Deployment Progress:**
```
[INFO] Starting APEX infrastructure deployment...
[INFO] Environment: prod
[INFO] Resource Group: apex-rg-prod
[INFO] Validating Bicep template...
[SUCCESS] Template validation passed
[INFO] Running what-if analysis...
[INFO] Review the following changes...
[INFO] Deploying infrastructure...
```

**Expected deployment time:** 15-20 minutes

#### Step 5: Verify Deployment Outputs

```bash
# Deployment script will display outputs:
# - Container Apps FQDN: https://apex-backend-prod.azurecontainerapps.io
# - SQL Server FQDN: sql-apex-prod.database.windows.net
# - Storage Account: stapexprod
# - Key Vault URI: https://kv-apex-prod.vault.azure.net
# - Application Insights ID: <guid>

# Record these outputs for later use
```

#### Step 6: Verify Resource Creation

```bash
# List all resources in resource group
az resource list --resource-group "$RESOURCE_GROUP" --output table

# Expected resources:
# - vnet-apex-prod (Virtual Network)
# - sql-apex-prod (SQL Server)
# - apex-db-prod (SQL Database)
# - stapexprod (Storage Account)
# - kv-apex-prod (Key Vault)
# - appi-apex-prod (Application Insights)
# - openai-apex-prod (Azure OpenAI)
# - di-apex-prod (Document Intelligence)
# - apex-backend-prod (Container App)
# - 5 Private Endpoints (sql, storage, openai, di, keyvault)
# - 2 NSGs (container-apps-nsg, private-endpoint-nsg)
```

#### Troubleshooting

**Issue:** Deployment fails with "ResourceGroupNotFound"
```bash
# Create resource group
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

# Re-run deployment
./deploy.sh prod apex-rg-prod
```

**Issue:** Deployment fails with "InsufficientPermissions"
```bash
# Check your Azure RBAC role
az role assignment list --assignee $(az account show --query user.name -o tsv) --output table

# Required role: Contributor or Owner on subscription/resource group
```

**Issue:** Deployment stuck at "Provisioning"
```bash
# Check deployment status
az deployment group show \
  --resource-group "$RESOURCE_GROUP" \
  --name main \
  --query "properties.provisioningState"

# If stuck for >30 minutes, cancel and retry
az deployment group cancel --resource-group "$RESOURCE_GROUP" --name main
```

---

## Database Migration

### Procedure: Run Alembic Database Migrations

**Duration:** ~5-10 minutes
**Rollback:** Alembic downgrade or database restore

#### Prerequisites

- Database backup completed (see [DISASTER_RECOVERY.md](./DISASTER_RECOVERY.md))
- Database connection string available
- Alembic migrations tested in staging

#### Step 1: Connect to Production Database

**Option A: Via Jump Box (Recommended)**

```bash
# SSH to jump box within VNet
ssh devops@jumpbox-prod.eastus.cloudapp.azure.com

# Install Azure CLI and dependencies on jump box
sudo apt-get update && sudo apt-get install -y azure-cli python3-pip
pip3 install alembic sqlalchemy pyodbc
```

**Option B: Via Azure Bastion**

```bash
# Connect to jump box via Azure Bastion in Azure Portal
# Navigate to: Resource Group > jumpbox-prod > Connect > Bastion
```

**Option C: Via VPN**

```bash
# Connect to production VPN
# Ensure VPN routes to VNet address space (10.0.0.0/16)
```

#### Step 2: Verify Current Database Version

```bash
# Set environment variables
export AZURE_SQL_SERVER="sql-apex-prod.database.windows.net"
export AZURE_SQL_DATABASE="apex-db-prod"

# Connect to database and check Alembic version
alembic current

# Expected output: Current revision hash (e.g., "abc123def456 (head)")
```

**If Alembic table doesn't exist:**
```bash
# Initialize Alembic (first deployment only)
alembic stamp head
```

#### Step 3: Review Pending Migrations

```bash
# Show migration history
alembic history

# Expected output: List of all migrations with [current] marker

# Generate SQL for review (dry run)
alembic upgrade head --sql > migration-preview.sql

# Review migration-preview.sql for:
# - DDL statements (CREATE TABLE, ALTER TABLE, etc.)
# - Data migrations
# - No unexpected DROP statements
```

#### Step 4: Execute Database Migration

```bash
# Run Alembic migration
alembic upgrade head

# Expected output:
# INFO  [alembic.runtime.migration] Context impl MSSQLImpl.
# INFO  [alembic.runtime.migration] Will assume transactional DDL.
# INFO  [alembic.runtime.migration] Running upgrade abc123 -> def456, Add estimate risk factors table
# INFO  [alembic.runtime.migration] Running upgrade def456 -> ghi789, Add user audit log columns
```

**Monitor migration progress:**
- Migrations with large tables may take several minutes
- Do NOT interrupt migration process
- Check database CPU/DTU usage in Azure Portal during migration

#### Step 5: Verify Migration Success

```bash
# Verify new revision is current
alembic current

# Expected output: Latest revision hash (e.g., "ghi789def456 (head)")

# Verify table schema
sqlcmd -S "$AZURE_SQL_SERVER" -d "$AZURE_SQL_DATABASE" -U <username> -Q "
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_NAME;
"

# Expected tables:
# - users
# - app_roles
# - projects
# - project_access
# - documents
# - estimates
# - estimate_line_items
# - estimate_assumptions
# - estimate_exclusions
# - estimate_risk_factors
# - cost_codes
# - audit_logs
# - alembic_version
```

#### Step 6: Test Database Connectivity from Container App

```bash
# Test connection from Container App to database via private endpoint
az containerapp exec \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --command "python3 -c '
from apex.database.connection import engine
try:
    with engine.connect() as conn:
        result = conn.execute(\"SELECT 1 AS test\")
        print(\"Database connection successful:\", result.fetchone())
except Exception as e:
    print(\"Database connection failed:\", e)
'"

# Expected output: "Database connection successful: (1,)"
```

#### Troubleshooting

**Issue:** Connection timeout to database

```bash
# Verify Private Endpoint connectivity
az network private-endpoint show \
  --name pe-sql-apex-prod \
  --resource-group apex-rg-prod \
  --query "privateLinkServiceConnections[0].privateLinkServiceConnectionState"

# Expected: "status": "Approved"

# Verify NSG rules allow SQL traffic (port 1433)
az network nsg rule list \
  --nsg-name container-apps-nsg \
  --resource-group apex-rg-prod \
  --query "[?destinationPortRange=='1433']" -o table
```

**Issue:** Migration fails with "Lock timeout"

```bash
# Check for blocking queries
sqlcmd -S "$AZURE_SQL_SERVER" -d "$AZURE_SQL_DATABASE" -Q "
SELECT blocking_session_id, wait_type, wait_time, wait_resource
FROM sys.dm_exec_requests
WHERE blocking_session_id <> 0;
"

# Kill blocking session (if safe)
sqlcmd -S "$AZURE_SQL_SERVER" -d "$AZURE_SQL_DATABASE" -Q "KILL <session_id>"
```

**Issue:** Migration partially applied

```bash
# Check Alembic version table
sqlcmd -S "$AZURE_SQL_SERVER" -d "$AZURE_SQL_DATABASE" -Q "
SELECT * FROM alembic_version;
"

# If version is incorrect, manually update or rollback
alembic downgrade <previous_revision>
alembic upgrade head
```

---

## Application Deployment

### Procedure: Update Container App with New Image

**Duration:** ~5-10 minutes
**Rollback:** Traffic shift to previous revision

#### Prerequisites

- Docker image built and pushed to Azure Container Registry
- Image vulnerability scan passed (Trivy)
- Database migration completed (if required)

#### Step 1: Verify Docker Image

```bash
# Set variables
export ACR_NAME="apexacr"
export IMAGE_TAG="v1.2.3"  # Or commit SHA
export FULL_IMAGE="$ACR_NAME.azurecr.io/apex-backend:$IMAGE_TAG"

# Verify image exists in registry
az acr repository show-tags \
  --name "$ACR_NAME" \
  --repository apex-backend \
  --output table

# Expected output: List including your $IMAGE_TAG

# Check image vulnerability scan results
az acr repository show \
  --name "$ACR_NAME" \
  --repository apex-backend \
  --tag "$IMAGE_TAG" \
  --query "{digest: digest, created: created}" -o table
```

#### Step 2: Get Current Container App Configuration

```bash
# Export current configuration for rollback reference
az containerapp show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  > current-containerapp-config.json

# Record current revision
az containerapp revision list \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --query "[?properties.active==\`true\`].name" -o table

# Save current revision name for rollback
export OLD_REVISION=$(az containerapp revision list \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --query "[?properties.active==\`true\`].name" -o tsv)

echo "Current revision: $OLD_REVISION"
```

#### Step 3: Update Container App

```bash
# Update Container App with new image and environment variables
az containerapp update \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --image "$FULL_IMAGE" \
  --set-env-vars \
    ENVIRONMENT=production \
    APP_NAME=APEX \
    APP_VERSION="$IMAGE_TAG" \
    DEBUG=false \
    LOG_LEVEL=INFO \
    AZURE_SQL_SERVER=sql-apex-prod.database.windows.net \
    AZURE_SQL_DATABASE=apex-db-prod \
    AZURE_SQL_DRIVER="ODBC Driver 18 for SQL Server" \
    AZURE_OPENAI_ENDPOINT=https://openai-apex-prod.openai.azure.com \
    AZURE_OPENAI_DEPLOYMENT=gpt-4 \
    AZURE_STORAGE_ACCOUNT=stapexprod \
    AZURE_STORAGE_CONTAINER_UPLOADS=uploads \
    AZURE_STORAGE_CONTAINER_PROCESSED=processed \
    AZURE_AD_TENANT_ID=<tenant-id> \
    AZURE_AD_CLIENT_ID=<client-id> \
    DEFAULT_MONTE_CARLO_ITERATIONS=10000 \
    DEFAULT_CONFIDENCE_LEVEL=0.80 \
  --cpu 2.0 \
  --memory 4Gi \
  --min-replicas 2 \
  --max-replicas 10

# Expected output: Container App update started
# Note: New revision is created automatically
```

**Monitor deployment progress:**
```bash
# Watch revision creation
watch -n 5 "az containerapp revision list \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --query '[].{Name:name, Active:properties.active, Health:properties.healthState, Replicas:properties.replicas}' \
  -o table"

# Expected: New revision appears with "Provisioning" → "Healthy"
```

#### Step 4: Get New Revision Name

```bash
# Get new revision name
export NEW_REVISION=$(az containerapp revision list \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --query "[?properties.provisioningState==\`Succeeded\` && properties.active==\`false\`] | [0].name" -o tsv)

echo "New revision: $NEW_REVISION"
echo "Old revision: $OLD_REVISION"
```

#### Step 5: Verify New Revision Health

```bash
# Check new revision health state
az containerapp revision show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision "$NEW_REVISION" \
  --query "properties.healthState" -o tsv

# Expected output: "Healthy"

# Check replica count
az containerapp revision show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision "$NEW_REVISION" \
  --query "properties.replicas" -o tsv

# Expected: ≥2 replicas running
```

#### Step 6: Test New Revision Directly

```bash
# Get revision FQDN (unique URL for this specific revision)
export REVISION_FQDN=$(az containerapp revision show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision "$NEW_REVISION" \
  --query "properties.fqdn" -o tsv)

echo "Revision FQDN: https://$REVISION_FQDN"

# Test health endpoint on new revision
curl -f "https://$REVISION_FQDN/health/live"

# Expected: {"status":"alive","timestamp":"..."}

curl -f "https://$REVISION_FQDN/health/ready"

# Expected: {"status":"ready","checks":{...},"timestamp":"..."}
```

**If health checks fail:**
- Check Container App logs: See [Common Troubleshooting](#common-troubleshooting)
- DO NOT proceed with traffic shifting
- Investigate and fix issues before continuing

#### Troubleshooting

**Issue:** New revision stuck in "Provisioning"

```bash
# Check Container App logs
az containerapp logs show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision "$NEW_REVISION" \
  --tail 50

# Common issues:
# - Image pull failures (check ACR credentials)
# - Application startup failures (check environment variables)
# - Health check failures (check /health/live and /health/ready endpoints)
```

**Issue:** Image pull failures

```bash
# Verify ACR credentials are configured
az containerapp show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --query "properties.configuration.registries" -o table

# If missing, update Container App with ACR credentials
az containerapp registry set \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --server "$ACR_NAME.azurecr.io" \
  --identity system
```

**Issue:** Application fails to start

```bash
# Check startup logs
az containerapp logs show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision "$NEW_REVISION" \
  --follow

# Common errors:
# - Missing environment variables
# - Database connection failures
# - Port binding issues (must bind to 0.0.0.0:8000)
```

---

## Smoke Tests

### Procedure: Validate Critical Functionality

**Duration:** ~10-15 minutes
**Prerequisites:** New revision deployed and healthy

#### Step 1: Obtain Authentication Token

```bash
# Get Azure AD access token for APEX API
export TOKEN=$(az account get-access-token \
  --resource api://<AZURE_AD_CLIENT_ID> \
  --query accessToken -o tsv)

echo "Token obtained: ${TOKEN:0:20}..."

# Alternative: Use service principal
# az login --service-principal -u <app-id> -p <password> --tenant <tenant-id>
```

#### Step 2: Test Health Endpoints

```bash
# Test liveness probe (no authentication required)
curl -f "https://$REVISION_FQDN/health/live"

# Expected: {"status":"alive","timestamp":"2024-..."}

# Test readiness probe (no authentication required)
curl -f "https://$REVISION_FQDN/health/ready"

# Expected:
# {
#   "status": "ready",
#   "checks": {
#     "database": "healthy",
#     "blob_storage": "healthy"
#   },
#   "timestamp": "2024-..."
# }
```

**If readiness check fails:**
- Check "checks" object for unhealthy services
- Database unhealthy → Verify Private Endpoint connection
- Blob Storage unhealthy → Verify Managed Identity RBAC

#### Step 3: Test Authentication

```bash
# Test authenticated endpoint (GET /projects)
curl -f -H "Authorization: Bearer $TOKEN" \
  "https://$REVISION_FQDN/api/v1/projects/?page=1&page_size=10" \
  | jq .

# Expected:
# {
#   "items": [...],
#   "total": <number>,
#   "page": 1,
#   "page_size": 10,
#   "has_next": false,
#   "has_prev": false
# }
```

**If 401 Unauthorized:**
```bash
# Verify token is valid
echo "$TOKEN" | jwt decode -

# Check Azure AD configuration
az ad app show --id <AZURE_AD_CLIENT_ID> --query "appId"
```

#### Step 4: Test Project Creation (CRUD)

```bash
# Create test project
export TEST_PROJECT_ID=$(curl -f -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_number": "SMOKE-TEST-'$(date +%s)'",
    "project_name": "Smoke Test Project",
    "voltage_level": 345,
    "line_miles": 25.5,
    "terrain_type": "flat"
  }' \
  "https://$REVISION_FQDN/api/v1/projects/" \
  | jq -r '.id')

echo "Created test project: $TEST_PROJECT_ID"

# Verify project created
curl -f -H "Authorization: Bearer $TOKEN" \
  "https://$REVISION_FQDN/api/v1/projects/$TEST_PROJECT_ID" \
  | jq .

# Expected: Project details with matching ID
```

#### Step 5: Test Document Upload (Blob Storage Integration)

```bash
# Create test PDF document
echo "%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj << /Type /Page /Parent 2 0 R /Resources << >> /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer << /Size 4 /Root 1 0 R >>
startxref
214
%%EOF" > smoke-test.pdf

# Upload document
export TEST_DOCUMENT_ID=$(curl -f -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@smoke-test.pdf" \
  -F "project_id=$TEST_PROJECT_ID" \
  -F "document_type=scope" \
  "https://$REVISION_FQDN/api/v1/documents/upload" \
  | jq -r '.id')

echo "Uploaded document: $TEST_DOCUMENT_ID"

# Verify document in blob storage via API
curl -f -H "Authorization: Bearer $TOKEN" \
  "https://$REVISION_FQDN/api/v1/documents/$TEST_DOCUMENT_ID" \
  | jq .

# Expected: Document details with blob_path
```

#### Step 6: Test Azure OpenAI Integration (Optional - May Consume Tokens)

```bash
# Trigger document validation (uses Azure OpenAI)
curl -f -X POST \
  -H "Authorization: Bearer $TOKEN" \
  "https://$REVISION_FQDN/api/v1/documents/$TEST_DOCUMENT_ID/validate" \
  | jq .

# Expected: Validation result with completeness_score
# Note: May take 30-60 seconds for LLM processing
```

#### Step 7: Performance Baseline

```bash
# Create curl timing format file
echo "time_namelookup:  %{time_namelookup}s\n\
time_connect:  %{time_connect}s\n\
time_appconnect:  %{time_appconnect}s\n\
time_pretransfer:  %{time_pretransfer}s\n\
time_redirect:  %{time_redirect}s\n\
time_starttransfer:  %{time_starttransfer}s\n\
----------\n\
time_total:  %{time_total}s\n\
http_code:  %{http_code}\n" > curl-format.txt

# Measure response time for 10 requests
for i in {1..10}; do
  echo "Request $i:"
  curl -w "@curl-format.txt" -o /dev/null -s \
    -H "Authorization: Bearer $TOKEN" \
    "https://$REVISION_FQDN/api/v1/projects/?page=1&page_size=10"
  echo "---"
  sleep 1
done

# Expected:
# - time_total < 0.5s (500ms) for most requests
# - http_code: 200
```

#### Step 8: Cleanup Test Data (Optional)

```bash
# Delete test document
curl -f -X DELETE \
  -H "Authorization: Bearer $TOKEN" \
  "https://$REVISION_FQDN/api/v1/documents/$TEST_DOCUMENT_ID"

# Delete test project (will soft-delete, set status to ARCHIVED)
curl -f -X DELETE \
  -H "Authorization: Bearer $TOKEN" \
  "https://$REVISION_FQDN/api/v1/projects/$TEST_PROJECT_ID"

# Cleanup test PDF
rm smoke-test.pdf curl-format.txt
```

#### Smoke Test Results Summary

**Record results:**
- [ ] Health endpoints: PASS / FAIL
- [ ] Authentication: PASS / FAIL
- [ ] Project CRUD: PASS / FAIL
- [ ] Document upload (Blob Storage): PASS / FAIL
- [ ] LLM validation (Azure OpenAI): PASS / FAIL (optional)
- [ ] Performance baseline: PASS / FAIL (P95 < 500ms)

**If ANY test fails:** DO NOT proceed with traffic shifting. Investigate and fix issues.

---

## Traffic Shifting

### Procedure: Blue-Green Deployment with Gradual Rollout

**Duration:** ~15-20 minutes (including monitoring)
**Rollback:** Shift traffic back to old revision

#### Step 1: Verify Prerequisites

```bash
# Verify new revision is healthy
az containerapp revision show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision "$NEW_REVISION" \
  --query "properties.healthState" -o tsv

# Expected: "Healthy"

# Verify old revision still active
az containerapp revision show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision "$OLD_REVISION" \
  --query "properties.active" -o tsv

# Expected: "true"

# Verify smoke tests passed
# See previous section
```

#### Step 2: Canary Deployment (10% Traffic)

```bash
# Shift 10% of traffic to new revision (canary)
az containerapp ingress traffic set \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision-weight "$NEW_REVISION=10" "$OLD_REVISION=90"

echo "Canary deployment: 10% traffic to new revision"
echo "Monitoring for 10 minutes..."
```

#### Step 3: Monitor Canary Performance

**Monitor for 10 minutes. Check these metrics:**

```bash
# Application Insights metrics (via Azure Portal or CLI)
az monitor metrics list \
  --resource "/subscriptions/<sub-id>/resourceGroups/apex-rg-prod/providers/Microsoft.Insights/components/appi-apex-prod" \
  --metric "requests/count" "requests/failed" "requests/duration" \
  --start-time "$(date -u -d '10 minutes ago' '+%Y-%m-%dT%H:%M:%SZ')" \
  --end-time "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
  --interval PT1M \
  --aggregation Average \
  --output table
```

**Acceptance Criteria for Canary:**
- ✅ Error rate < 1%
- ✅ P95 response time < 2s
- ✅ No critical alerts triggered
- ✅ No 500 errors from new revision
- ✅ Availability ≥ 99.9%

**If canary fails criteria:**
```bash
# Rollback immediately
az containerapp ingress traffic set \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision-weight "$OLD_REVISION=100" "$NEW_REVISION=0"

echo "Canary failed - traffic rolled back to old revision"
# See [Rollback Procedure](#rollback-procedure) for next steps
```

#### Step 4: Increase Traffic to 50%

**If canary passes acceptance criteria:**

```bash
# Shift 50% of traffic to new revision
az containerapp ingress traffic set \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision-weight "$NEW_REVISION=50" "$OLD_REVISION=50"

echo "50% traffic shift completed"
echo "Monitoring for 5 minutes..."
```

**Monitor for 5 minutes** (same criteria as canary)

#### Step 5: Shift 100% Traffic

**If 50% split performs well:**

```bash
# Shift all traffic to new revision
az containerapp ingress traffic set \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision-weight "$NEW_REVISION=100" "$OLD_REVISION=0"

echo "100% traffic shifted to new revision"
echo "Deployment complete - entering 24-hour stability window"
```

#### Step 6: Verify Traffic Distribution

```bash
# Verify traffic weights
az containerapp ingress traffic show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --output table

# Expected output:
# Revision                           Weight
# ---------------------------------  ------
# apex-backend-prod--<NEW_REVISION>  100
# apex-backend-prod--<OLD_REVISION>  0
```

#### Step 7: Monitor New Revision

**Continue monitoring for 24 hours:**

- Check Application Insights dashboard every 30 minutes (first 8 hours)
- Check Application Insights dashboard every 2 hours (next 16 hours)
- Review alert notifications (should be none)

**After 24-hour stability window:**
```bash
# Deactivate old revision
az containerapp revision deactivate \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision "$OLD_REVISION"

echo "Old revision deactivated - deployment fully complete"
```

#### Troubleshooting

**Issue:** Traffic split not working (all traffic still on old revision)

```bash
# Check ingress configuration
az containerapp ingress show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod

# Verify both revisions are active
az containerapp revision list \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --query "[].{Name:name, Active:properties.active, Traffic:properties.trafficWeight}" \
  -o table
```

**Issue:** New revision returning errors under load

```bash
# Check replica count (may need to scale up)
az containerapp revision show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision "$NEW_REVISION" \
  --query "properties.replicas"

# Scale up if needed
az containerapp update \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --min-replicas 3 \
  --max-replicas 15
```

---

## Rollback Procedure

### Procedure: Emergency Rollback to Previous Revision

**Duration:** ~5-10 minutes
**When to Use:** Critical bugs, security issues, performance degradation

#### Step 1: Identify Rollback Trigger

**Common rollback triggers:**
- Error rate >10% for >5 minutes
- P95 response time >5s for >5 minutes
- Critical bug affecting estimation accuracy
- Security vulnerability discovered
- Database corruption or data loss

**Decision Authority:**
- Deployment Engineer (during deployment window)
- On-Call Engineer (after deployment)
- Technical Lead (escalation)

#### Step 2: Stop All Deployment Activities

```bash
# Cancel any in-progress deployments
az deployment group cancel \
  --resource-group apex-rg-prod \
  --name main

# Announce rollback decision
echo "ROLLBACK INITIATED at $(date)" | tee rollback-log.txt
# Send notification to #apex-deployment Slack channel
```

#### Step 3: Shift Traffic to Previous Revision

```bash
# Immediately shift 100% traffic back to old revision
az containerapp ingress traffic set \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision-weight "$OLD_REVISION=100" "$NEW_REVISION=0"

echo "Traffic shifted to previous revision: $OLD_REVISION"
```

#### Step 4: Verify Rollback Success

```bash
# Verify traffic distribution
az containerapp ingress traffic show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --output table

# Expected:
# Revision                           Weight
# ---------------------------------  ------
# apex-backend-prod--<OLD_REVISION>  100
# apex-backend-prod--<NEW_REVISION>  0

# Test health endpoint
curl -f https://apex-backend-prod.azurecontainerapps.io/health/ready

# Expected: {"status":"ready",...}
```

#### Step 5: Rollback Database Migration (If Required)

**Option A: Alembic Downgrade (If migration is reversible)**

```bash
# Check if downgrade is possible
alembic history | grep -A 5 "$(alembic current)"

# If <down_revision> exists, downgrade
alembic downgrade -1

# Verify database version
alembic current

# Expected: Previous revision
```

**Option B: Database Restore (If migration is NOT reversible)**

**See [DISASTER_RECOVERY.md](./DISASTER_RECOVERY.md#database-restore) for full procedure.**

```bash
# Restore database from pre-migration backup
# WARNING: This will lose all data created after backup!

# 1. Stop application traffic (already done above)
# 2. Restore database from backup (.bacpac file)
# 3. Verify restore success
# 4. Reconnect application
```

#### Step 6: Deactivate Failed Revision

```bash
# Deactivate new revision to prevent accidental reactivation
az containerapp revision deactivate \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision "$NEW_REVISION"

echo "Failed revision deactivated"
```

#### Step 7: Run Smoke Tests on Rolled-Back Revision

```bash
# Run critical smoke tests (see Smoke Tests section)
# Verify:
# - Health endpoints responding
# - Authentication working
# - Project CRUD operations successful
# - Document upload working
```

#### Step 8: Post-Rollback Communication

```bash
# Send rollback notification
cat <<EOF
APEX Production Rollback - $(date)

Deployment of version $IMAGE_TAG has been rolled back.

Reason: <Insert reason>

Current Status:
- Application: Running on previous revision ($OLD_REVISION)
- Database: <Rolled back / Not rolled back>
- User Impact: <Describe any user impact>

Next Steps:
1. Root cause analysis to begin immediately
2. Fix to be developed and tested in staging
3. Re-deployment scheduled for <date/time>

Contact: ops-team@company.com
EOF

# Send email to stakeholders
# Update status page
```

#### Step 9: Preserve Evidence

```bash
# Collect logs from failed revision
az containerapp logs show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision "$NEW_REVISION" \
  --tail 1000 \
  > failed-revision-logs.txt

# Export Application Insights data
# See MONITORING_AND_ALERTING.md for query procedures

# Save deployment artifacts
mkdir rollback-evidence-$(date +%Y%m%d-%H%M%S)
mv failed-revision-logs.txt rollback-evidence-*/
mv current-containerapp-config.json rollback-evidence-*/
mv rollback-log.txt rollback-evidence-*/
```

#### Step 10: Initiate Root Cause Analysis

**See [INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md#root-cause-analysis) for RCA procedure.**

**Required actions:**
- Create incident report
- Conduct 5 Whys analysis
- Identify action items for remediation
- Update deployment procedures to prevent recurrence

---

## Emergency Procedures

### Complete System Outage

**Symptoms:** All health checks failing, 100% error rate

#### Immediate Actions (Within 5 Minutes)

```bash
# 1. Check Container App status
az containerapp show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --query "properties.runningStatus"

# 2. Check Application Insights for errors
# Navigate to Azure Portal > Application Insights > Failures

# 3. Check if issue is infrastructure-wide
az resource list --resource-group apex-rg-prod --query "[].{Name:name, Status:properties.provisioningState}" -o table
```

#### Recovery Options

**Option 1: Restart Container App**

```bash
az containerapp restart \
  --name apex-backend-prod \
  --resource-group apex-rg-prod
```

**Option 2: Scale to Zero and Back**

```bash
# Scale down
az containerapp update \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --min-replicas 0 \
  --max-replicas 0

# Wait 30 seconds

# Scale up
az containerapp update \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --min-replicas 2 \
  --max-replicas 10
```

**Option 3: Redeploy Last Known Good Revision**

```bash
# List all revisions
az containerapp revision list \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --query "[].{Name:name, Created:properties.createdTime, Health:properties.healthState}" \
  -o table

# Activate last known good revision
az containerapp revision activate \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision <LAST_GOOD_REVISION>

# Shift 100% traffic
az containerapp ingress traffic set \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision-weight "<LAST_GOOD_REVISION>=100"
```

### Database Connection Failures

**Symptoms:** 500 errors, "Cannot connect to database" in logs

#### Diagnostic Steps

```bash
# 1. Check SQL Server status
az sql server show \
  --name sql-apex-prod \
  --resource-group apex-rg-prod \
  --query "state"

# Expected: "Ready"

# 2. Check Private Endpoint status
az network private-endpoint show \
  --name pe-sql-apex-prod \
  --resource-group apex-rg-prod \
  --query "privateLinkServiceConnections[0].privateLinkServiceConnectionState.status"

# Expected: "Approved"

# 3. Test DNS resolution from Container App
az containerapp exec \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --command "nslookup sql-apex-prod.database.windows.net"

# Expected: Private IP (10.0.x.x)

# 4. Test database connection
az containerapp exec \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --command "python3 -c 'from apex.database.connection import engine; engine.connect()'"
```

#### Recovery Actions

```bash
# If Private Endpoint is disconnected
az network private-endpoint connection approve \
  --id <connection-id> \
  --description "Emergency reconnection"

# If Managed Identity permissions lost
# Re-assign Azure SQL DB Contributor role
export PRINCIPAL_ID=$(az containerapp show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --query "identity.principalId" -o tsv)

az role assignment create \
  --assignee "$PRINCIPAL_ID" \
  --role "SQL DB Contributor" \
  --scope "/subscriptions/<sub-id>/resourceGroups/apex-rg-prod/providers/Microsoft.Sql/servers/sql-apex-prod"
```

### Blob Storage Access Issues

**Symptoms:** Document upload failures, 403 Forbidden errors

#### Diagnostic Steps

```bash
# 1. Check Storage Account status
az storage account show \
  --name stapexprod \
  --resource-group apex-rg-prod \
  --query "statusOfPrimary"

# Expected: "available"

# 2. Check Managed Identity RBAC
az role assignment list \
  --assignee "$PRINCIPAL_ID" \
  --scope "/subscriptions/<sub-id>/resourceGroups/apex-rg-prod/providers/Microsoft.Storage/storageAccounts/stapexprod" \
  --query "[].roleDefinitionName"

# Expected: "Storage Blob Data Contributor"

# 3. Test blob access from Container App
az containerapp exec \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --command "python3 -c '
from apex.azure.blob_storage import BlobStorageClient
client = BlobStorageClient()
containers = client.list_containers()
print(\"Accessible containers:\", containers)
'"
```

#### Recovery Actions

```bash
# Re-assign Storage Blob Data Contributor role
az role assignment create \
  --assignee "$PRINCIPAL_ID" \
  --role "Storage Blob Data Contributor" \
  --scope "/subscriptions/<sub-id>/resourceGroups/apex-rg-prod/providers/Microsoft.Storage/storageAccounts/stapexprod"

# Verify Private Endpoint
az network private-endpoint show \
  --name pe-storage-apex-prod \
  --resource-group apex-rg-prod \
  --query "privateLinkServiceConnections[0].privateLinkServiceConnectionState.status"
```

---

## Common Troubleshooting

### View Container App Logs

```bash
# Tail live logs
az containerapp logs show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --follow

# Get last 100 lines
az containerapp logs show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --tail 100

# Get logs from specific revision
az containerapp logs show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --revision "$NEW_REVISION" \
  --tail 50

# Filter logs by error level
az containerapp logs show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --tail 100 \
  --output json \
  | jq '.[] | select(.level == "ERROR")'
```

### Execute Commands in Container

```bash
# Open interactive shell
az containerapp exec \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --command "/bin/bash"

# Run one-off command
az containerapp exec \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --command "python3 --version"

# Check environment variables
az containerapp exec \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --command "printenv | grep AZURE"
```

### Application Insights Queries

```bash
# Get error count (last hour)
az monitor app-insights query \
  --app appi-apex-prod \
  --resource-group apex-rg-prod \
  --analytics-query "
    requests
    | where timestamp > ago(1h)
    | summarize ErrorCount = countif(success == false), TotalCount = count()
    | extend ErrorRate = ErrorCount * 100.0 / TotalCount
  "

# Get slowest requests (last hour)
az monitor app-insights query \
  --app appi-apex-prod \
  --resource-group apex-rg-prod \
  --analytics-query "
    requests
    | where timestamp > ago(1h)
    | top 10 by duration desc
    | project timestamp, name, duration, resultCode, url
  "

# Get exceptions (last hour)
az monitor app-insights query \
  --app appi-apex-prod \
  --resource-group apex-rg-prod \
  --analytics-query "
    exceptions
    | where timestamp > ago(1h)
    | project timestamp, type, outerMessage, problemId
    | order by timestamp desc
  "
```

### Network Connectivity Testing

```bash
# Test from Container App to SQL Server
az containerapp exec \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --command "nc -zv sql-apex-prod.database.windows.net 1433"

# Test from Container App to Storage Account
az containerapp exec \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --command "nc -zv stapexprod.blob.core.windows.net 443"

# Test from Container App to Azure OpenAI
az containerapp exec \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --command "nc -zv openai-apex-prod.openai.azure.com 443"
```

### Database Query Performance

```bash
# Connect to database via Azure Data Studio or sqlcmd

# Check long-running queries
SELECT
    r.session_id,
    r.status,
    r.command,
    r.cpu_time,
    r.total_elapsed_time,
    t.text AS query_text
FROM sys.dm_exec_requests r
CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) t
WHERE r.session_id <> @@SPID
ORDER BY r.total_elapsed_time DESC;

# Check blocking sessions
SELECT
    blocking_session_id,
    session_id,
    wait_type,
    wait_time,
    wait_resource
FROM sys.dm_exec_requests
WHERE blocking_session_id <> 0;

# Check database size and usage
EXEC sp_spaceused;
```

---

## Appendix: Quick Reference Commands

### Environment Variables

```bash
# Production environment variables (always set these first)
export ENVIRONMENT="prod"
export RESOURCE_GROUP="apex-rg-prod"
export ACR_NAME="apexacr"
export IMAGE_TAG="v1.2.3"  # Update for each deployment
export FULL_IMAGE="$ACR_NAME.azurecr.io/apex-backend:$IMAGE_TAG"
```

### Health Check URLs

```bash
# Liveness probe
curl https://apex-backend-prod.azurecontainerapps.io/health/live

# Readiness probe
curl https://apex-backend-prod.azurecontainerapps.io/health/ready
```

### Common Azure CLI Commands

```bash
# List revisions
az containerapp revision list \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --output table

# Show current traffic weights
az containerapp ingress traffic show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --output table

# Tail logs
az containerapp logs show \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --follow
```

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024 | DevOps Team | Initial production runbook |

**Approval:**
- Technical Lead: _______________
- Operations Manager: _______________

---

**END OF RUNBOOK**
