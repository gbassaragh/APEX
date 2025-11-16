# APEX Operational Runbook

**Version**: 1.0.0
**Last Updated**: 2025-11-15
**On-Call Team**: DevOps + Platform Engineering

## Table of Contents

1. [System Overview](#system-overview)
2. [Common Operations](#common-operations)
3. [Incident Response](#incident-response)
4. [Monitoring & Alerts](#monitoring--alerts)
5. [Disaster Recovery](#disaster-recovery)
6. [Maintenance Procedures](#maintenance-procedures)

---

## System Overview

### Architecture

```
┌─────────────┐
│   Frontend  │
│  (React UI) │
└──────┬──────┘
       │ HTTPS
       ▼
┌──────────────────────────────────────────┐
│  Azure Container Apps (APEX API)         │
│  - FastAPI + Python 3.11                 │
│  - Min 1 / Max 10 replicas               │
│  - Managed Identity authentication       │
└─────┬────────┬────────┬────────┬─────────┘
      │        │        │        │
      ▼        ▼        ▼        ▼
   ┌────┐   ┌────┐   ┌────┐   ┌────┐
   │SQL │   │Blob│   │OpenAI  │DocI│
   │DB  │   │Stor│   │       │ntel│
   └────┘   └────┘   └────┘   └────┘
```

### Key Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| API | FastAPI + Python 3.11 | REST API |
| Database | Azure SQL (S2) | Relational data |
| Storage | Azure Blob Storage | Document files |
| AI Services | Azure OpenAI (GPT-4) | Document validation |
| Parsing | Azure Document Intelligence | PDF extraction |
| Monitoring | Azure Application Insights | Observability |

### Service Dependencies

**Critical** (P0 - Outage causes full system failure):
- Azure Container Apps
- Azure SQL Database
- Managed Identity service

**High** (P1 - Major features degraded):
- Azure OpenAI (document validation unavailable)
- Azure Document Intelligence (cannot process new documents)
- Azure Blob Storage (cannot upload/download documents)

**Medium** (P2 - Minor features degraded):
- Application Insights (monitoring unavailable)

---

## Common Operations

### Viewing Logs

**Application Logs** (Container Apps):
```bash
# Last 50 lines
az containerapp logs show \
  --name apex-app-prod \
  --resource-group rg-apex-prod \
  --type console \
  --tail 50

# Follow logs (real-time)
az containerapp logs show \
  --name apex-app-prod \
  --resource-group rg-apex-prod \
  --type console \
  --follow

# Filter by timestamp
az containerapp logs show \
  --name apex-app-prod \
  --resource-group rg-apex-prod \
  --type console \
  --since 1h
```

**Application Insights Logs**:
```kusto
// Last 100 requests
requests
| where timestamp > ago(1h)
| order by timestamp desc
| take 100
| project timestamp, url, resultCode, duration

// Errors in last hour
exceptions
| where timestamp > ago(1h)
| project timestamp, type, outerMessage, operation_Name
| order by timestamp desc

// Slow requests (> 5 seconds)
requests
| where timestamp > ago(1h)
| where duration > 5000
| project timestamp, url, duration, resultCode
| order by duration desc
```

### Restarting the Application

**Restart all replicas**:
```bash
az containerapp revision restart \
  --name apex-app-prod \
  --resource-group rg-apex-prod
```

**Restart specific revision**:
```bash
az containerapp revision restart \
  --name apex-app-prod \
  --resource-group rg-apex-prod \
  --revision apex-app-prod--abc123
```

### Scaling

**Manual scale**:
```bash
# Scale up to 5 replicas immediately
az containerapp update \
  --name apex-app-prod \
  --resource-group rg-apex-prod \
  --min-replicas 5 \
  --max-replicas 10

# Scale down after incident resolved
az containerapp update \
  --name apex-app-prod \
  --resource-group rg-apex-prod \
  --min-replicas 1 \
  --max-replicas 10
```

**Check current scale**:
```bash
az containerapp replica list \
  --name apex-app-prod \
  --resource-group rg-apex-prod \
  --output table
```

### Database Operations

**Check database status**:
```bash
az sql db show \
  --resource-group rg-apex-prod \
  --server apex-sql-server-prod \
  --name apex-db \
  --query "{name:name, status:status, tier:currentServiceObjectiveName}"
```

**Database performance metrics**:
```bash
az monitor metrics list \
  --resource /subscriptions/{sub}/resourceGroups/rg-apex-prod/providers/Microsoft.Sql/servers/apex-sql-server-prod/databases/apex-db \
  --metric "dtu_consumption_percent" \
  --start-time $(date -u -d '1 hour ago' '+%Y-%m-%dT%H:%M:%SZ') \
  --end-time $(date -u '+%Y-%m-%dT%H:%M:%SZ') \
  --interval PT1M \
  --aggregation Average
```

**Execute SQL query** (read-only for safety):
```bash
az sql db query \
  --resource-group rg-apex-prod \
  --server apex-sql-server-prod \
  --name apex-db \
  --auth-type ADIntegrated \
  --query "SELECT COUNT(*) as total FROM project"
```

### Certificate & SSL

**Check Container App ingress**:
```bash
az containerapp ingress show \
  --name apex-app-prod \
  --resource-group rg-apex-prod

# Expected: HTTPS enabled, custom domain configured
```

---

## Incident Response

### Incident Severity Levels

| Severity | Description | Response Time | Examples |
|----------|-------------|---------------|----------|
| **P0** | Complete outage | < 15 minutes | API down, database unreachable |
| **P1** | Major degradation | < 1 hour | Document validation failing, high error rate |
| **P2** | Minor degradation | < 4 hours | Slow responses, monitoring unavailable |
| **P3** | Cosmetic issues | < 24 hours | Log noise, minor UI glitches |

### P0: Complete Outage

**Symptoms**:
- Health endpoints returning 503 or timing out
- Zero successful requests in last 5 minutes
- All users unable to access system

**Immediate Actions**:

1. **Check Container App status**:
   ```bash
   az containerapp show \
     --name apex-app-prod \
     --resource-group rg-apex-prod \
     --query "properties.{status:runningStatus, replicas:template.scale.minReplicas}"
   ```

2. **Check recent deployments**:
   ```bash
   az containerapp revision list \
     --name apex-app-prod \
     --resource-group rg-apex-prod \
     --output table

   # If recent deployment, rollback immediately (see Rollback section)
   ```

3. **Check Azure Service Health**:
   ```bash
   az rest --method get \
     --url "https://management.azure.com/subscriptions/{sub}/providers/Microsoft.ResourceHealth/availabilityStatuses?api-version=2020-05-01"
   ```

4. **Check database connectivity**:
   ```bash
   curl -f https://api.apex.company.com/health/ready
   # If fails, database may be down
   ```

5. **Escalate**:
   - Open Azure support ticket (Severity A)
   - Notify stakeholders
   - Update status page

### P1: Major Degradation - Document Validation Failing

**Symptoms**:
- Users reporting "Document validation failed"
- High rate of 500 errors on `/documents/{id}/validate` endpoint
- Azure OpenAI or Document Intelligence errors in logs

**Investigation**:

1. **Check Azure OpenAI quota**:
   ```bash
   # Check Application Insights for rate limit errors
   az monitor app-insights query \
     --app apex-insights-prod \
     --analytics-query "
       exceptions
       | where timestamp > ago(1h)
       | where outerMessage contains '429' or outerMessage contains 'RateLimitError'
       | summarize count() by bin(timestamp, 5m)
     "
   ```

2. **Check Document Intelligence**:
   - Navigate to Azure Portal → Document Intelligence resource
   - Check "Metrics" → "Total Calls" and "Failed Calls"
   - Document Intelligence has 15 requests/minute limit on S0 tier

3. **Temporary Mitigation**:
   ```bash
   # If OpenAI rate limit: Scale up deployment
   # If DI limit: Users must wait 1-2 minutes between validations

   # Add monitoring alert for rate limits
   az monitor metrics alert create \
     --name "OpenAI Rate Limit Alert" \
     --resource-group rg-apex-prod \
     --scopes /subscriptions/{sub}/resourceGroups/rg-apex-prod/providers/Microsoft.CognitiveServices/accounts/apex-openai-prod \
     --condition "total failedCalls > 5" \
     --window-size 5m \
     --evaluation-frequency 1m \
     --action <action-group-id>
   ```

4. **Long-term Fix**:
   - Implement queue-based processing for document validation
   - Add retry logic with exponential backoff
   - Upgrade OpenAI deployment to higher quota

### P1: High Error Rate (> 5% of requests failing)

**Symptoms**:
- Error rate alert triggered
- Spike in 500 Internal Server Error responses
- Users experiencing intermittent failures

**Investigation**:

1. **Check error distribution**:
   ```kusto
   requests
   | where timestamp > ago(15m)
   | summarize Total = count(), Errors = countif(resultCode >= 500)
   | extend ErrorRate = 100.0 * Errors / Total
   ```

2. **Identify error patterns**:
   ```kusto
   exceptions
   | where timestamp > ago(15m)
   | summarize count() by type, outerMessage
   | order by count_ desc
   ```

3. **Check for specific issues**:
   - Database connection pool exhaustion → Restart app
   - Azure service transient errors → Wait for Azure recovery
   - Code bug → Rollback to previous version

### P2: Slow Response Times (> 5 seconds for API calls)

**Symptoms**:
- Users reporting slowness
- Average response time > 2 seconds (normal: < 500ms for CRUD)

**Investigation**:

1. **Check database DTU usage**:
   ```bash
   az sql db show-usage \
     --resource-group rg-apex-prod \
     --server apex-sql-server-prod \
     --name apex-db

   # If > 80% DTU: Scale up database tier
   ```

2. **Check application performance**:
   ```kusto
   requests
   | where timestamp > ago(1h)
   | summarize avg(duration), percentile(duration, 95) by bin(timestamp, 5m)
   | render timechart
   ```

3. **Identify slow endpoints**:
   ```kusto
   requests
   | where timestamp > ago(1h)
   | where duration > 5000
   | summarize count() by url
   | order by count_ desc
   ```

4. **Mitigation**:
   - Scale up database (S2 → S3) if database-bound
   - Scale out Container App replicas if CPU-bound
   - Add caching for frequently accessed data (future enhancement)

---

## Monitoring & Alerts

### Key Metrics to Monitor

**Application Health**:
- Request success rate (target: > 99%)
- Average response time (target: < 500ms for CRUD, < 2min for validation)
- Active replicas (target: 1-5 normal load)

**Azure Services**:
- SQL Database DTU usage (alert: > 80%)
- OpenAI API calls and quota
- Document Intelligence quota
- Blob Storage operations

**Business Metrics**:
- Documents uploaded per hour
- Documents validated per hour
- Projects created per day
- Active users

### Recommended Alerts

**Critical Alerts** (PagerDuty / On-call):

1. **API Availability < 99% (5-minute window)**:
   ```kusto
   requests
   | where timestamp > ago(5m)
   | summarize success_rate = 100.0 * countif(resultCode < 500) / count()
   | where success_rate < 99
   ```

2. **Database Unreachable**:
   ```kusto
   customMetrics
   | where name == "database_health"
   | where value == 0
   ```

3. **Error Rate > 5% (5-minute window)**:
   ```kusto
   requests
   | where timestamp > ago(5m)
   | summarize error_rate = 100.0 * countif(resultCode >= 500) / count()
   | where error_rate > 5
   ```

**Warning Alerts** (Email / Slack):

1. **Slow Response Times (95th percentile > 3s)**
2. **DTU Usage > 80% for 15 minutes**
3. **Failed Authentication Attempts > 20 in 5 minutes**

### Dashboard Queries

**Real-time Health Dashboard**:
```kusto
// Last 24 hours overview
let timeRange = 24h;
let successRate = requests
| where timestamp > ago(timeRange)
| summarize SuccessRate = 100.0 * countif(resultCode < 500) / count();

let avgResponseTime = requests
| where timestamp > ago(timeRange)
| where resultCode < 500
| summarize AvgDuration = avg(duration);

let errorCount = exceptions
| where timestamp > ago(timeRange)
| summarize ErrorCount = count();

let activeUsers = customEvents
| where timestamp > ago(timeRange)
| where name == "user_activity"
| summarize UniqueUsers = dcount(user_Id);

print
  SuccessRate = toscalar(successRate),
  AvgResponseTime_ms = toscalar(avgResponseTime),
  TotalErrors = toscalar(errorCount),
  ActiveUsers = toscalar(activeUsers)
```

---

## Disaster Recovery

### Recovery Time Objective (RTO) & Recovery Point Objective (RPO)

| Component | RTO | RPO | Backup Strategy |
|-----------|-----|-----|-----------------|
| Application | 15 minutes | 0 (stateless) | Redeploy container |
| Database | 4 hours | 1 hour | Point-in-time restore |
| Blob Storage | 1 hour | 15 minutes | Soft delete + geo-replication |
| Configuration | 15 minutes | 0 | Infrastructure as Code (Bicep) |

### Database Restore Procedure

**Point-in-time restore** (within last 7 days):

```bash
# Restore to new database
az sql db restore \
  --resource-group rg-apex-prod \
  --server apex-sql-server-prod \
  --name apex-db-restored \
  --dest-name apex-db \
  --time "2025-11-15T14:30:00Z"

# Swap databases (manual step in Azure Portal or via T-SQL)
```

**Geo-restore** (disaster recovery from another region):

```bash
# Restore from geo-replicated backup
az sql db geo-restore \
  --resource-group rg-apex-dr \
  --server apex-sql-server-dr \
  --name apex-db \
  --dest-database apex-db \
  --dest-server apex-sql-server-dr \
  --source-database /subscriptions/{sub}/resourceGroups/rg-apex-prod/providers/Microsoft.Sql/servers/apex-sql-server-prod/databases/apex-db
```

### Blob Storage Recovery

**Recover deleted blobs** (within soft delete retention period):

```bash
# List deleted blobs
az storage blob list \
  --account-name apexstorageprod \
  --container-name uploads \
  --include-deleted \
  --output table

# Undelete specific blob
az storage blob undelete \
  --account-name apexstorageprod \
  --container-name uploads \
  --name "uploads/project-123/document.pdf"
```

### Complete Environment Recovery

**Scenario**: Entire Azure region failure

**Recovery Steps**:

1. **Deploy infrastructure in secondary region** (~ 30 minutes):
   ```bash
   az deployment group create \
     --resource-group rg-apex-dr \
     --template-file infrastructure/bicep/main.bicep \
     --parameters environment=disaster-recovery
   ```

2. **Restore database** (~ 2-4 hours):
   ```bash
   az sql db geo-restore ...
   ```

3. **Sync blob storage** (~ 30 minutes):
   ```bash
   azcopy sync \
     "https://apexstorageprod.blob.core.windows.net/uploads" \
     "https://apexstoragedr.blob.core.windows.net/uploads" \
     --recursive
   ```

4. **Deploy application** (~ 15 minutes):
   ```bash
   az containerapp create ...
   ```

5. **Update DNS** (~ 5 minutes):
   - Point api.apex.company.com to DR region
   - Propagation time: 5-15 minutes

**Total RTO**: ~ 4 hours

---

## Maintenance Procedures

### Planned Maintenance Window

**Recommended**: Sundays 2:00 AM - 4:00 AM EST (low usage period)

**Pre-Maintenance Checklist**:
- [ ] Notify users 48 hours in advance
- [ ] Create database backup
- [ ] Test rollback procedure
- [ ] Update status page
- [ ] Have on-call engineer available

**During Maintenance**:
- [ ] Set maintenance mode (503 response)
- [ ] Stop incoming traffic (scale to 0 replicas)
- [ ] Apply database migrations
- [ ] Deploy new application version
- [ ] Run smoke tests
- [ ] Resume traffic

**Post-Maintenance**:
- [ ] Monitor error rates for 1 hour
- [ ] Verify all critical paths working
- [ ] Update status page (operational)
- [ ] Document changes in runbook

### Database Migrations

**Apply migration**:
```bash
# Connect to Container App and run:
kubectl exec -it apex-app-pod -- /bin/bash
alembic upgrade head

# Verify migration
alembic current
```

**Rollback migration**:
```bash
alembic downgrade -1  # Rollback one migration
alembic history  # View migration history
```

### Application Deployment

**Blue-Green Deployment** (zero downtime):

```bash
# 1. Deploy new version as revision
az containerapp revision copy \
  --name apex-app-prod \
  --resource-group rg-apex-prod \
  --image apexregistryprod.azurecr.io/apex:1.1.0

# 2. Test new revision (internal endpoint)
REVISION_URL=<new-revision-url>
curl $REVISION_URL/health/ready

# 3. Gradually shift traffic (10% → 50% → 100%)
az containerapp ingress traffic set \
  --name apex-app-prod \
  --resource-group rg-apex-prod \
  --revision-weight apex-app-prod--v1=90 apex-app-prod--v2=10

# Monitor for 15 minutes

az containerapp ingress traffic set \
  --name apex-app-prod \
  --resource-group rg-apex-prod \
  --revision-weight apex-app-prod--v1=0 apex-app-prod--v2=100

# 4. Deactivate old revision after 24 hours
az containerapp revision deactivate \
  --name apex-app-prod \
  --resource-group rg-apex-prod \
  --revision apex-app-prod--v1
```

### Certificate Renewal

**Azure Container Apps handles automatic certificate renewal for managed certificates.**

**Verify certificate expiration**:
```bash
az containerapp ingress show \
  --name apex-app-prod \
  --resource-group rg-apex-prod \
  --query "customDomains[0].{domain:name, expiry:certificateExpiry}"
```

---

## Troubleshooting Quick Reference

| Symptom | Likely Cause | Quick Fix |
|---------|--------------|-----------|
| 503 Service Unavailable | App not responding | Restart Container App |
| 500 Internal Server Error | Application bug or config error | Check logs, rollback if recent deploy |
| 429 Too Many Requests | Azure service rate limit | Wait or increase quota |
| Slow database queries | High DTU usage | Scale up database tier |
| Authentication failures | AAD misconfiguration | Check Managed Identity permissions |
| File upload failures | Blob storage permission issue | Grant Storage Blob Data Contributor role |
| Document parsing timeout | Large file or DI service slow | Retry or reduce file size |
| LLM validation slow | OpenAI deployment quota | Scale up deployment or wait |

---

## Escalation Contacts

| Issue Type | Contact | Method |
|------------|---------|--------|
| P0 Outage | On-Call Engineer | PagerDuty |
| Azure Platform Issues | Azure Support | Portal ticket (Severity A) |
| Database Issues | DBA Team | Slack #dba-oncall |
| Application Bugs | Development Team | Slack #apex-dev |
| Security Incident | Security Team | Email: security@company.com |

---

## Runbook Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-11-15 | Initial runbook creation |

---

**Maintained By**: DevOps Team
**Review Frequency**: Quarterly
**Last Reviewed**: 2025-11-15
