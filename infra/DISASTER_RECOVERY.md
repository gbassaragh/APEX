# APEX Disaster Recovery Plan

**Version:** 1.0
**Last Updated:** 2024
**Owner:** DevOps Team / DBA Team
**Purpose:** Backup, disaster recovery, and business continuity procedures

## Overview

This document defines disaster recovery (DR) procedures for the APEX platform to ensure business continuity in the event of catastrophic failures, data loss, or regional outages.

**Recovery Objectives:**

| Metric | Target | Definition |
|--------|--------|------------|
| **RTO** (Recovery Time Objective) | 4 hours | Maximum acceptable downtime |
| **RPO** (Recovery Point Objective) | 1 hour | Maximum acceptable data loss |
| **MTTR** (Mean Time To Recovery) | 2 hours | Average time to restore service |

**Disaster Scenarios Covered:**
1. Database corruption or data loss
2. Complete Azure region outage
3. Blob storage data loss
4. Application secrets compromise
5. Accidental resource deletion
6. Ransomware / security breach

**DR Testing Schedule:**
- **Tabletop exercises:** Quarterly
- **Backup restore tests:** Monthly
- **Full DR failover:** Annually

---

## Table of Contents

1. [Backup Procedures](#backup-procedures)
2. [Database Recovery](#database-recovery)
3. [Blob Storage Recovery](#blob-storage-recovery)
4. [Regional Failover](#regional-failover)
5. [Security Incident Recovery](#security-incident-recovery)
6. [Testing & Validation](#testing--validation)

---

## Backup Procedures

### 1.1 Azure SQL Database Backups

**Automated Backups (Azure Built-In):**

Azure SQL Database provides automatic backups:
- **Full backups:** Weekly (Sunday at 00:00 UTC)
- **Differential backups:** Every 12 hours
- **Transaction log backups:** Every 5-10 minutes
- **Retention:** 7 days (short-term), 35 days (long-term retention configured)

**Verify Automatic Backups:**

```bash
# List available restore points
az sql db list-restore-points \
  --name apex-db-prod \
  --server sql-apex-prod \
  --resource-group apex-rg-prod \
  --output table

# Expected output: List of restore points with timestamps
```

**Long-Term Retention (LTR) Configuration:**

```bash
# Configure long-term retention policy
az sql db ltr-policy set \
  --server sql-apex-prod \
  --database apex-db-prod \
  --resource-group apex-rg-prod \
  --weekly-retention P4W \
  --monthly-retention P12M \
  --yearly-retention P7Y \
  --week-of-year 1

# Weekly: Keep 4 weeks
# Monthly: Keep 12 months
# Yearly: Keep 7 years (for compliance)

# Verify LTR policy
az sql db ltr-policy show \
  --server sql-apex-prod \
  --database apex-db-prod \
  --resource-group apex-rg-prod
```

**Manual Backup (Pre-Migration, Pre-Deployment):**

```bash
# Export database to .bacpac file
export BACKUP_DATE=$(date +%Y%m%d-%H%M%S)
export STORAGE_KEY=$(az storage account keys list \
  --account-name stapexprod \
  --resource-group apex-rg-prod \
  --query "[0].value" -o tsv)

# Create backup container if not exists
az storage container create \
  --name backups \
  --account-name stapexprod \
  --account-key "$STORAGE_KEY"

# Generate SAS token (valid for 24 hours)
export SAS_TOKEN=$(az storage container generate-sas \
  --name backups \
  --account-name stapexprod \
  --account-key "$STORAGE_KEY" \
  --permissions rwl \
  --expiry $(date -u -d '+24 hours' '+%Y-%m-%dT%H:%MZ') \
  -o tsv)

# Export database
az sql db export \
  --name apex-db-prod \
  --server sql-apex-prod \
  --resource-group apex-rg-prod \
  --admin-user <sql-admin-username> \
  --admin-password <sql-admin-password> \
  --storage-key-type SharedAccessKey \
  --storage-key "$SAS_TOKEN" \
  --storage-uri "https://stapexprod.blob.core.windows.net/backups/apex-db-backup-$BACKUP_DATE.bacpac"

# Wait for export to complete
az sql db list-export-operations \
  --server sql-apex-prod \
  --resource-group apex-rg-prod \
  --output table
```

**Backup Verification:**

```bash
# Verify backup file exists in blob storage
az storage blob list \
  --container-name backups \
  --account-name stapexprod \
  --account-key "$STORAGE_KEY" \
  --prefix "apex-db-backup-" \
  --output table

# Download backup file (for offsite storage)
az storage blob download \
  --container-name backups \
  --name "apex-db-backup-$BACKUP_DATE.bacpac" \
  --file "./apex-db-backup-$BACKUP_DATE.bacpac" \
  --account-name stapexprod \
  --account-key "$STORAGE_KEY"

# Verify file integrity (check file size)
ls -lh "./apex-db-backup-$BACKUP_DATE.bacpac"
```

---

### 1.2 Blob Storage Backups

**Blob Versioning (Enabled):**

Azure Blob Storage versioning automatically maintains previous versions of blobs:

```bash
# Verify blob versioning enabled
az storage account blob-service-properties show \
  --account-name stapexprod \
  --resource-group apex-rg-prod \
  --query "isVersioningEnabled"

# Expected: true

# Enable versioning (if not already enabled)
az storage account blob-service-properties update \
  --account-name stapexprod \
  --resource-group apex-rg-prod \
  --enable-versioning true
```

**Soft Delete (90 Days Retention):**

```bash
# Verify soft delete enabled
az storage account blob-service-properties show \
  --account-name stapexprod \
  --resource-group apex-rg-prod \
  --query "{BlobSoftDelete: deleteRetentionPolicy.enabled, BlobSoftDeleteDays: deleteRetentionPolicy.days, ContainerSoftDelete: containerDeleteRetentionPolicy.enabled, ContainerSoftDeleteDays: containerDeleteRetentionPolicy.days}"

# Enable soft delete for blobs and containers
az storage account blob-service-properties update \
  --account-name stapexprod \
  --resource-group apex-rg-prod \
  --enable-delete-retention true \
  --delete-retention-days 90 \
  --enable-container-delete-retention true \
  --container-delete-retention-days 90
```

**Manual Backup (AzCopy):**

```bash
# Install AzCopy (if not already installed)
wget https://aka.ms/downloadazcopy-v10-linux -O azcopy.tar.gz
tar -xzf azcopy.tar.gz
sudo mv azcopy_linux_amd64_*/azcopy /usr/local/bin/

# Generate SAS token for source account
export SAS_SOURCE=$(az storage account generate-sas \
  --account-name stapexprod \
  --services b \
  --resource-types sco \
  --permissions rl \
  --expiry $(date -u -d '+24 hours' '+%Y-%m-%dT%H:%MZ') \
  -o tsv)

# Backup to local storage (offsite)
azcopy copy \
  "https://stapexprod.blob.core.windows.net/?$SAS_SOURCE" \
  "./blob-backup-$BACKUP_DATE/" \
  --recursive=true \
  --include-pattern="*.pdf;*.docx;*.xlsx"  # Only document files

# Or backup to secondary Azure region (geo-redundancy)
# Create storage account in secondary region (e.g., westus)
az storage account create \
  --name stapexprdr \
  --resource-group apex-rg-dr \
  --location westus \
  --sku Standard_GRS \
  --kind StorageV2

# Generate SAS token for destination
export SAS_DEST=$(az storage account generate-sas \
  --account-name stapexprdr \
  --services b \
  --resource-types sco \
  --permissions rwl \
  --expiry $(date -u -d '+24 hours' '+%Y-%m-%dT%H:%MZ') \
  -o tsv)

# Copy blobs to DR storage account
azcopy copy \
  "https://stapexprod.blob.core.windows.net/?$SAS_SOURCE" \
  "https://stapexprdr.blob.core.windows.net/?$SAS_DEST" \
  --recursive=true
```

---

### 1.3 Azure Key Vault Backups

**Backup Secrets and Certificates:**

```bash
# List all secrets
az keyvault secret list \
  --vault-name kv-apex-prod \
  --query "[].id" -o tsv > secret-list.txt

# Backup each secret
mkdir -p keyvault-backup-$BACKUP_DATE

while read secret_id; do
  SECRET_NAME=$(basename "$secret_id")
  az keyvault secret backup \
    --vault-name kv-apex-prod \
    --name "$SECRET_NAME" \
    --file "./keyvault-backup-$BACKUP_DATE/$SECRET_NAME.backup"
done < secret-list.txt

# Verify backups
ls -lh ./keyvault-backup-$BACKUP_DATE/

# Upload backups to blob storage (encrypted)
az storage blob upload-batch \
  --destination backups \
  --source "./keyvault-backup-$BACKUP_DATE/" \
  --account-name stapexprod \
  --account-key "$STORAGE_KEY" \
  --pattern "*.backup"
```

**Alternative: Export Secrets to Encrypted File:**

```bash
# Export all secrets (NOT recommended for production - use Key Vault backup instead)
az keyvault secret list \
  --vault-name kv-apex-prod \
  --query "[].{Name:name, Value:value}" -o json \
  > secrets-export.json

# Encrypt with GPG
gpg --symmetric --cipher-algo AES256 secrets-export.json

# Upload encrypted file
az storage blob upload \
  --container-name backups \
  --name "secrets-backup-$BACKUP_DATE.json.gpg" \
  --file "secrets-export.json.gpg" \
  --account-name stapexprod \
  --account-key "$STORAGE_KEY"

# Delete plaintext file immediately
shred -u secrets-export.json
```

---

### 1.4 Infrastructure as Code (Bicep Templates)

**Git Repository Backup:**

All Bicep templates are version-controlled in Git:

```bash
# Ensure all changes are committed
cd /home/gbass/MyProjects/APEX
git status

# Tag current production infrastructure
git tag -a "prod-$(date +%Y%m%d)" -m "Production infrastructure as of $(date)"
git push origin "prod-$(date +%Y%m%d)"

# Backup to remote repository (GitLab/GitHub)
git push origin main
```

**Export Current Resource Configuration:**

```bash
# Export entire resource group configuration
az group export \
  --name apex-rg-prod \
  --output json \
  > "resource-group-export-$BACKUP_DATE.json"

# Upload to blob storage
az storage blob upload \
  --container-name backups \
  --name "resource-group-export-$BACKUP_DATE.json" \
  --file "resource-group-export-$BACKUP_DATE.json" \
  --account-name stapexprod \
  --account-key "$STORAGE_KEY"
```

---

### 1.5 Backup Retention Schedule

| Backup Type | Frequency | Retention | Storage Location |
|-------------|-----------|-----------|------------------|
| **Database Automated** | Continuous | 7 days (PITR), 35 days (LTR) | Azure SQL (geo-redundant) |
| **Database Manual** | Pre-deployment, weekly | 90 days | Blob Storage (GRS) |
| **Blob Storage (Versioning)** | Automatic on change | 90 days (soft delete) | Azure Blob (GRS) |
| **Blob Storage Manual** | Weekly | 1 year | Offsite + Secondary region |
| **Key Vault Secrets** | Weekly | 1 year | Blob Storage (encrypted) |
| **Infrastructure (Bicep)** | On change (Git commit) | Indefinite | Git repository |
| **Application Code** | On commit | Indefinite | Git repository |

---

## Database Recovery

### 2.1 Point-in-Time Restore (PITR)

**Use Case:** Accidental data deletion, data corruption (last 7 days)

**Recovery Time:** ~15-30 minutes
**Data Loss:** Minimal (restore to any point within last 7 days, down to the second)

**Restore Procedure:**

```bash
# Identify restore point (timestamp of last known good state)
export RESTORE_TIME="2024-01-15T14:30:00Z"  # UTC timestamp

# Create new database from PITR
az sql db restore \
  --dest-name apex-db-restored-$(date +%Y%m%d-%H%M%S) \
  --server sql-apex-prod \
  --resource-group apex-rg-prod \
  --name apex-db-prod \
  --time "$RESTORE_TIME" \
  --elastic-pool <pool-name>  # Optional: restore to same elastic pool

# Monitor restore progress
az sql db show \
  --name apex-db-restored-$(date +%Y%m%d-%H%M%S) \
  --server sql-apex-prod \
  --resource-group apex-rg-prod \
  --query "status"

# Expected: "Online" when complete (takes 15-30 minutes)
```

**Validation:**

```bash
# Connect to restored database
sqlcmd -S sql-apex-prod.database.windows.net \
  -d apex-db-restored-$(date +%Y%m%d-%H%M%S) \
  -U <sql-admin> \
  -P <password>

# Verify data integrity
SELECT COUNT(*) AS ProjectCount FROM projects;
SELECT COUNT(*) AS EstimateCount FROM estimates;
SELECT MAX(created_at) AS LatestTimestamp FROM audit_logs;

# Compare with production database
# If validation passes:
# 1. Stop application traffic to production database
# 2. Rename production database to apex-db-old
# 3. Rename restored database to apex-db-prod
# 4. Update connection strings (if database name changed)
# 5. Resume application traffic
```

**Database Rename (Cutover):**

```bash
# Stop Container App to prevent writes
az containerapp update \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --min-replicas 0 \
  --max-replicas 0

# Rename production database (backup)
az sql db rename \
  --name apex-db-prod \
  --server sql-apex-prod \
  --resource-group apex-rg-prod \
  --new-name apex-db-old-$(date +%Y%m%d)

# Rename restored database to production
az sql db rename \
  --name apex-db-restored-$(date +%Y%m%d-%H%M%S) \
  --server sql-apex-prod \
  --resource-group apex-rg-prod \
  --new-name apex-db-prod

# Resume Container App
az containerapp update \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --min-replicas 2 \
  --max-replicas 10

# Verify application connectivity
curl https://apex-backend-prod.azurecontainerapps.io/health/ready
```

---

### 2.2 Long-Term Retention (LTR) Restore

**Use Case:** Restore from weekly/monthly/yearly backup (beyond 7 days)

**Recovery Time:** ~30-60 minutes
**Data Loss:** Up to 1 week (or 1 month, depending on restore point)

**List Available LTR Backups:**

```bash
# List all LTR backups
az sql db ltr-backup list \
  --location eastus \
  --server sql-apex-prod \
  --database apex-db-prod \
  --resource-group apex-rg-prod \
  --output table

# Expected output: List of backups with timestamps and retention type (Weekly/Monthly/Yearly)
```

**Restore from LTR Backup:**

```bash
# Get specific backup ID
export BACKUP_ID=$(az sql db ltr-backup list \
  --location eastus \
  --server sql-apex-prod \
  --database apex-db-prod \
  --resource-group apex-rg-prod \
  --query "[?contains(completedTime, '2024-01-01')].id" -o tsv | head -1)

# Restore database from LTR backup
az sql db ltr-backup restore \
  --dest-database apex-db-ltr-restored-$(date +%Y%m%d) \
  --dest-server sql-apex-prod \
  --dest-resource-group apex-rg-prod \
  --backup-id "$BACKUP_ID"

# Monitor restore progress
az sql db show \
  --name apex-db-ltr-restored-$(date +%Y%m%d) \
  --server sql-apex-prod \
  --resource-group apex-rg-prod \
  --query "status"
```

---

### 2.3 .bacpac File Restore (Manual Backup)

**Use Case:** Restore from manual pre-deployment backup

**Recovery Time:** ~1-2 hours (depending on database size)
**Data Loss:** Depends on backup age

**Import .bacpac File:**

```bash
# List available .bacpac backups
az storage blob list \
  --container-name backups \
  --account-name stapexprod \
  --account-key "$STORAGE_KEY" \
  --prefix "apex-db-backup-" \
  --output table

# Select backup to restore
export BACKUP_FILE="apex-db-backup-20240115-143000.bacpac"

# Generate SAS token for backup file
export BACKUP_SAS=$(az storage blob generate-sas \
  --container-name backups \
  --name "$BACKUP_FILE" \
  --account-name stapexprod \
  --account-key "$STORAGE_KEY" \
  --permissions r \
  --expiry $(date -u -d '+24 hours' '+%Y-%m-%dT%H:%MZ') \
  -o tsv)

# Import database from .bacpac
az sql db import \
  --name apex-db-restored-$(date +%Y%m%d) \
  --server sql-apex-prod \
  --resource-group apex-rg-prod \
  --admin-user <sql-admin-username> \
  --admin-password <sql-admin-password> \
  --storage-key-type SharedAccessKey \
  --storage-key "$BACKUP_SAS" \
  --storage-uri "https://stapexprod.blob.core.windows.net/backups/$BACKUP_FILE"

# Monitor import progress
az sql db list-import-operations \
  --server sql-apex-prod \
  --resource-group apex-rg-prod \
  --output table
```

**Post-Restore Tasks:**

```bash
# Update database compatibility level (if needed)
sqlcmd -S sql-apex-prod.database.windows.net \
  -d apex-db-restored-$(date +%Y%m%d) \
  -U <sql-admin> \
  -Q "ALTER DATABASE CURRENT SET COMPATIBILITY_LEVEL = 150;"

# Run Alembic to apply any missing migrations
alembic upgrade head

# Verify schema version
alembic current
```

---

## Blob Storage Recovery

### 3.1 Undelete Soft-Deleted Blobs

**Use Case:** Accidental blob deletion (within 90 days)

**Recovery Time:** <5 minutes
**Data Loss:** None

**List Deleted Blobs:**

```bash
# List soft-deleted blobs
az storage blob list \
  --container-name uploads \
  --account-name stapexprod \
  --account-key "$STORAGE_KEY" \
  --include d \
  --output table

# Expected output: Deleted blobs with deletion timestamp
```

**Restore Deleted Blob:**

```bash
# Undelete specific blob
az storage blob undelete \
  --container-name uploads \
  --name "projects/PROJ-001/scope-document.pdf" \
  --account-name stapexprod \
  --account-key "$STORAGE_KEY"

# Verify blob restored
az storage blob show \
  --container-name uploads \
  --name "projects/PROJ-001/scope-document.pdf" \
  --account-name stapexprod \
  --account-key "$STORAGE_KEY" \
  --query "{Name: name, DeletedTime: properties.deletedTime, IsDeleted: deleted}"

# Expected: deletedTime: null, deleted: false
```

**Bulk Restore (All Deleted Blobs in Container):**

```bash
# Restore all deleted blobs in a container
az storage blob undelete-batch \
  --container-name uploads \
  --account-name stapexprod \
  --account-key "$STORAGE_KEY"
```

---

### 3.2 Restore Previous Blob Version

**Use Case:** Accidental overwrite, restore older version

**Recovery Time:** <5 minutes
**Data Loss:** None

**List Blob Versions:**

```bash
# List all versions of a specific blob
az storage blob list \
  --container-name uploads \
  --prefix "projects/PROJ-001/scope-document.pdf" \
  --account-name stapexprod \
  --account-key "$STORAGE_KEY" \
  --include v \
  --output table

# Expected output: All versions with version ID and last modified timestamp
```

**Promote Previous Version to Current:**

```bash
# Get version ID of desired version
export VERSION_ID="2024-01-15T14:30:00.0000000Z"

# Copy previous version to current (promotes it)
az storage blob copy start \
  --source-container uploads \
  --source-name "projects/PROJ-001/scope-document.pdf" \
  --source-blob-version-id "$VERSION_ID" \
  --destination-container uploads \
  --destination-blob "projects/PROJ-001/scope-document.pdf" \
  --account-name stapexprod \
  --account-key "$STORAGE_KEY"

# Wait for copy to complete
az storage blob show \
  --container-name uploads \
  --name "projects/PROJ-001/scope-document.pdf" \
  --account-name stapexprod \
  --account-key "$STORAGE_KEY" \
  --query "properties.copy.status"

# Expected: "success"
```

---

### 3.3 Restore from Secondary Region (Geo-Redundancy)

**Use Case:** Primary region outage, blob storage unavailable

**Recovery Time:** ~30 minutes (manual failover)
**Data Loss:** Up to 15 minutes (RPO for GRS replication)

**Initiate Storage Account Failover:**

```bash
# Check replication status
az storage account show \
  --name stapexprod \
  --resource-group apex-rg-prod \
  --query "{Replication: sku.name, SecondaryLocation: secondaryLocation, StatusOfSecondary: statusOfSecondary}"

# Expected: Replication: Standard_GRS, StatusOfSecondary: "available"

# Initiate account failover to secondary region
az storage account failover \
  --name stapexprod \
  --resource-group apex-rg-prod \
  --yes  # Skip confirmation

# Monitor failover progress
az storage account show \
  --name stapexprod \
  --resource-group apex-rg-prod \
  --query "{PrimaryLocation: primaryLocation, StatusOfPrimary: statusOfPrimary}"

# After failover:
# - Secondary region becomes primary
# - New secondary region is configured
# - Replication resumes

# Update Container App environment variables (if needed)
# No change required if using storage account name (DNS automatically resolves to new primary)
```

**Alternative: Restore from Manual Backup:**

```bash
# If failover not possible, restore from DR storage account (stapexprdr in westus)
azcopy copy \
  "https://stapexprdr.blob.core.windows.net/?$SAS_DR" \
  "https://stapexprod.blob.core.windows.net/?$SAS_PROD" \
  --recursive=true

# Or create new storage account and update Container App configuration
```

---

## Regional Failover

### 4.1 Azure Region Outage

**Scenario:** Complete East US region outage, all services unavailable

**Recovery Strategy:** Failover to West US (DR region)

**Recovery Time:** 2-4 hours
**Data Loss:** Up to 1 hour (RPO)

**Prerequisites:**
- DR infrastructure deployed in West US (standby mode)
- Database geo-replication configured
- Blob storage geo-redundancy (GRS) enabled
- DNS CNAME records ready for failover

---

### 4.2 DR Infrastructure Setup (West US)

**Deploy DR Infrastructure:**

```bash
# Create DR resource group
az group create \
  --name apex-rg-dr \
  --location westus

# Deploy infrastructure to DR region
cd /home/gbass/MyProjects/APEX/infra
./deploy.sh dr apex-rg-dr westus

# Expected resources in DR region:
# - vnet-apex-dr (VNet)
# - sql-apex-dr (SQL Server with geo-replica)
# - stapexprdr (Storage Account - GRS paired)
# - kv-apex-dr (Key Vault - secrets synced)
# - apex-backend-dr (Container App - standby)
```

**Configure SQL Geo-Replication:**

```bash
# Create geo-replica of production database in DR region
az sql db replica create \
  --name apex-db-prod \
  --server sql-apex-prod \
  --resource-group apex-rg-prod \
  --partner-server sql-apex-dr \
  --partner-resource-group apex-rg-dr \
  --secondary-type Geo

# Verify replication status
az sql db replica list-links \
  --name apex-db-prod \
  --server sql-apex-prod \
  --resource-group apex-rg-prod \
  --query "[].{Partner: partnerServer, Role: partnerRole, ReplicationState: replicationState}"

# Expected: Partner: sql-apex-dr, Role: Secondary, ReplicationState: CATCH_UP or SYNCHRONIZED
```

---

### 4.3 Failover Procedure

**Step 1: Verify Primary Region Outage**

```bash
# Check Azure Service Health
az resource health list --resource-group apex-rg-prod

# Check Application Insights
az monitor metrics list \
  --resource <app-insights-resource-id> \
  --metric "availabilityResults/availabilityPercentage" \
  --start-time "$(date -u -d '15 minutes ago' '+%Y-%m-%dT%H:%M:%SZ')" \
  --interval PT1M

# If availability = 0% for >15 minutes → Declare DR event
```

**Step 2: Initiate Database Failover**

```bash
# Initiate planned failover (zero data loss, if primary is reachable)
az sql db replica set-primary \
  --name apex-db-prod \
  --server sql-apex-dr \
  --resource-group apex-rg-dr

# Or forced failover (potential data loss, if primary is unreachable)
az sql db replica force-failover \
  --name apex-db-prod \
  --server sql-apex-dr \
  --resource-group apex-rg-dr

# Verify new primary
az sql db replica list-links \
  --name apex-db-prod \
  --server sql-apex-dr \
  --resource-group apex-rg-dr

# Expected: Role: Primary
```

**Step 3: Failover Blob Storage**

```bash
# Initiate storage account failover (if GRS)
az storage account failover \
  --name stapexprod \
  --resource-group apex-rg-prod \
  --yes

# Or use DR storage account
# Update Container App environment variables:
# AZURE_STORAGE_ACCOUNT=stapexprdr
```

**Step 4: Activate DR Container App**

```bash
# Update DR Container App with current configuration
az containerapp update \
  --name apex-backend-dr \
  --resource-group apex-rg-dr \
  --image apexacr.azurecr.io/apex-backend:latest \
  --set-env-vars \
    AZURE_SQL_SERVER=sql-apex-dr.database.windows.net \
    AZURE_SQL_DATABASE=apex-db-prod \
    AZURE_STORAGE_ACCOUNT=stapexprdr \
    ENVIRONMENT=production

# Scale up DR Container App
az containerapp update \
  --name apex-backend-dr \
  --resource-group apex-rg-dr \
  --min-replicas 2 \
  --max-replicas 10

# Verify health
curl https://apex-backend-dr.westus.azurecontainerapps.io/health/ready
```

**Step 5: DNS Cutover**

```bash
# Update DNS CNAME record to point to DR region
# (This depends on your DNS provider - Azure DNS, Cloudflare, etc.)

# Example: Azure DNS
az network dns record-set cname set-record \
  --resource-group dns-rg \
  --zone-name apex.company.com \
  --record-set-name www \
  --cname apex-backend-dr.westus.azurecontainerapps.io

# Verify DNS propagation
dig apex.company.com

# Expected: CNAME pointing to DR region
```

**Step 6: Validate Failover**

```bash
# Run smoke tests against DR environment
export TOKEN=$(az account get-access-token --resource api://<CLIENT_ID> --query accessToken -o tsv)

curl -H "Authorization: Bearer $TOKEN" \
  https://apex-backend-dr.westus.azurecontainerapps.io/api/v1/projects/ \
  | jq .

# Expected: 200 OK, project list returned

# Test document upload
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test-document.pdf" \
  -F "project_id=<PROJECT_ID>" \
  -F "document_type=scope" \
  https://apex-backend-dr.westus.azurecontainerapps.io/api/v1/documents/upload

# Expected: 201 Created
```

**Step 7: Communicate Failover**

```
DISASTER RECOVERY FAILOVER ACTIVATED

APEX platform has been successfully failed over to the DR site (West US) due to primary region outage.

Service Status: OPERATIONAL
DR Region: West US
Estimated Data Loss: <1 hour (RPO)
Recovery Time: <4 hours (RTO)

All users can continue to access APEX at the normal URL (DNS cutover complete).

We will continue to monitor the situation and provide updates every hour.

APEX Operations Team
```

---

### 4.4 Failback Procedure (After Primary Region Recovery)

**When to Failback:** After primary region is stable for 24 hours

**Failback Steps:**

```bash
# 1. Verify primary region is healthy
az resource health list --resource-group apex-rg-prod

# 2. Sync data from DR to primary (reverse geo-replication)
az sql db replica create \
  --name apex-db-prod \
  --server sql-apex-dr \
  --resource-group apex-rg-dr \
  --partner-server sql-apex-prod \
  --partner-resource-group apex-rg-prod \
  --secondary-type Geo

# Wait for synchronization
az sql db replica list-links \
  --name apex-db-prod \
  --server sql-apex-dr \
  --resource-group apex-rg-dr \
  --query "[?partnerServer=='sql-apex-prod'].replicationState"

# Expected: "SYNCHRONIZED"

# 3. Planned failover back to primary
az sql db replica set-primary \
  --name apex-db-prod \
  --server sql-apex-prod \
  --resource-group apex-rg-prod

# 4. Sync blob storage back to primary
azcopy copy \
  "https://stapexprdr.blob.core.windows.net/?$SAS_DR" \
  "https://stapexprod.blob.core.windows.net/?$SAS_PROD" \
  --recursive=true

# 5. Activate primary Container App
az containerapp update \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --min-replicas 2 \
  --max-replicas 10

# 6. DNS cutover back to primary
az network dns record-set cname set-record \
  --resource-group dns-rg \
  --zone-name apex.company.com \
  --record-set-name www \
  --cname apex-backend-prod.azurecontainerapps.io

# 7. Deactivate DR Container App
az containerapp update \
  --name apex-backend-dr \
  --resource-group apex-rg-dr \
  --min-replicas 0 \
  --max-replicas 0
```

---

## Security Incident Recovery

### 5.1 Compromised Secrets / Keys

**Scenario:** Azure AD client secret, API keys, or Managed Identity compromised

**Immediate Actions (Within 15 Minutes):**

```bash
# 1. Rotate compromised secrets
# Azure AD Client Secret
az ad app credential reset \
  --id <AZURE_AD_CLIENT_ID> \
  --append  # Creates new secret without deleting old one

# 2. Update Key Vault with new secret
az keyvault secret set \
  --vault-name kv-apex-prod \
  --name "AZURE-AD-CLIENT-SECRET" \
  --value "<new-secret>"

# 3. Restart Container App to pick up new secret
az containerapp restart \
  --name apex-backend-prod \
  --resource-group apex-rg-prod

# 4. Revoke old secret after 24 hours (grace period)
az ad app credential delete \
  --id <AZURE_AD_CLIENT_ID> \
  --key-id <old-credential-key-id>
```

---

### 5.2 Ransomware Attack

**Scenario:** Ransomware encrypts blob storage or database

**Recovery Strategy:**

```bash
# 1. Isolate affected systems immediately
# Disable public network access to all resources
az sql server update \
  --name sql-apex-prod \
  --resource-group apex-rg-prod \
  --enable-public-network false

az storage account update \
  --name stapexprod \
  --resource-group apex-rg-prod \
  --default-action Deny

# 2. Assess impact
# Check for encrypted/corrupted files
az storage blob list \
  --container-name uploads \
  --account-name stapexprod \
  --account-key "$STORAGE_KEY" \
  | jq '.[] | select(.properties.contentLength == 0)'

# 3. Restore from clean backup (before infection time)
# Use PITR for database
export RESTORE_TIME="<timestamp-before-infection>"
az sql db restore \
  --dest-name apex-db-clean \
  --server sql-apex-prod \
  --resource-group apex-rg-prod \
  --name apex-db-prod \
  --time "$RESTORE_TIME"

# 4. Restore blob storage from version history or soft delete
# Undelete files (if soft-deleted by ransomware)
az storage blob undelete-batch \
  --container-name uploads \
  --account-name stapexprod

# 5. Scan for malware/backdoors
# Run security scan on all recovered data
# Engage security team for forensic analysis

# 6. Re-deploy infrastructure from clean Bicep templates
# Delete compromised resource group
az group delete --name apex-rg-prod --yes --no-wait

# Redeploy from IaC
./deploy.sh prod apex-rg-prod

# 7. Restore data to new clean infrastructure
```

---

## Testing & Validation

### 6.1 Monthly Backup Restore Test

**Objective:** Verify backups are restorable and data integrity is maintained

**Procedure:**

```bash
# 1. Select random backup from last month
RANDOM_BACKUP=$(az sql db ltr-backup list \
  --location eastus \
  --server sql-apex-prod \
  --database apex-db-prod \
  --resource-group apex-rg-prod \
  --query "[0].id" -o tsv)

# 2. Restore to test database
az sql db ltr-backup restore \
  --dest-database apex-db-test-restore \
  --dest-server sql-apex-prod \
  --dest-resource-group apex-rg-prod \
  --backup-id "$RANDOM_BACKUP"

# 3. Run data integrity checks
sqlcmd -S sql-apex-prod.database.windows.net \
  -d apex-db-test-restore \
  -U <sql-admin> \
  -Q "
SELECT
    'Projects' AS TableName, COUNT(*) AS RowCount FROM projects
UNION ALL
SELECT 'Estimates', COUNT(*) FROM estimates
UNION ALL
SELECT 'Documents', COUNT(*) FROM documents;
"

# 4. Document test results
echo "Backup Restore Test - $(date)" >> backup-test-log.txt
echo "Backup ID: $RANDOM_BACKUP" >> backup-test-log.txt
echo "Restore Time: <duration>" >> backup-test-log.txt
echo "Data Integrity: PASS/FAIL" >> backup-test-log.txt

# 5. Cleanup test database
az sql db delete \
  --name apex-db-test-restore \
  --server sql-apex-prod \
  --resource-group apex-rg-prod \
  --yes
```

---

### 6.2 Quarterly DR Tabletop Exercise

**Objective:** Validate team readiness and DR procedures

**Scenario Examples:**
1. East US region outage
2. Database corruption
3. Ransomware attack
4. Accidental resource group deletion

**Exercise Format:**
- Duration: 2 hours
- Participants: DevOps, DBA, Management, Security
- Facilitator: DR Lead
- Outcomes: Action items for DR plan improvements

**Sample Questions:**
- Who is the Incident Commander for DR events?
- What is the RTO for regional failover?
- Where are database backups stored?
- How do we validate data integrity after restore?
- What is the communication plan for stakeholders?

---

### 6.3 Annual Full DR Failover Test

**Objective:** Validate complete DR infrastructure and failover process

**Procedure:**

```bash
# 1. Schedule maintenance window (off-hours)
# 2. Announce planned DR test to stakeholders
# 3. Execute full failover to DR region (see Section 4.3)
# 4. Run smoke tests in DR environment
# 5. Measure RTO (target: <4 hours)
# 6. Measure RPO (data loss, target: <1 hour)
# 7. Document lessons learned
# 8. Failback to primary region (see Section 4.4)
```

**Success Criteria:**
- Failover completed within RTO
- Data loss within RPO
- All smoke tests passing in DR environment
- Stakeholder communication timely and accurate

---

## Appendix: Contact Information

**Emergency Contacts:**

| Role | Name | Email | Phone | Availability |
|------|------|-------|-------|--------------|
| DR Lead |  | dr-lead@company.com |  | 24/7 |
| DBA Team |  | dba-team@company.com |  | 24/7 |
| Azure Support |  | Premier Support Portal |  | 24/7 |
| Security Team |  | security@company.com |  | 24/7 for Sev0 |

**Vendor Contacts:**
- **Azure Support:** https://portal.azure.com/#view/Microsoft_Azure_Support
- **Microsoft TAM:**  -

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024 | DevOps Team | Initial disaster recovery plan |

**Approval:**
- DR Lead: _______________
- DBA Manager: _______________
- Operations Manager: _______________

---

**END OF DISASTER RECOVERY PLAN**
