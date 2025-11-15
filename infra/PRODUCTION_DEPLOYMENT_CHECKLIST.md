# APEX Production Deployment Checklist

**Version:** 1.0
**Last Updated:** 2024
**Owner:** DevOps Team
**Compliance:** ISO/IEC 27001, ISO-NE Regulatory Requirements

## Overview

This checklist orchestrates all production deployment activities for the APEX (AI-Powered Estimation Expert) platform. Every production deployment must follow this checklist and obtain all required sign-offs.

**Target Environments:**
- Production (apex-rg-prod)

**Deployment Strategy:**
- Blue-Green deployment with zero downtime
- Database migrations run before application deployment
- Automatic rollback on health check failure
- 24-hour validation period before decommissioning old revision

**Reference Documents:**
- [RUNBOOK.md](./RUNBOOK.md) - Detailed step-by-step procedures
- [SECURITY_VALIDATION.md](./SECURITY_VALIDATION.md) - Security validation procedures
- [MONITORING_AND_ALERTING.md](./MONITORING_AND_ALERTING.md) - Observability setup
- [INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md) - Troubleshooting procedures
- [DISASTER_RECOVERY.md](./DISASTER_RECOVERY.md) - Backup and recovery

---

## Pre-Deployment Phase

### 1. Change Approval ✅

**Requirement:** All production deployments require formal change approval.

- [ ] Change Request (CR) created in change management system
- [ ] CR includes: deployment plan, risk assessment, rollback plan
- [ ] CR approved by:
  - Technical Lead
  - Operations Manager
  - Security Team (for security-related changes)
- [ ] Deployment window scheduled (must be during approved maintenance window)
- [ ] Stakeholder notification sent (estimators, managers, auditors)

**Evidence:** CR number and approval documentation

---

### 2. Code Quality and Testing ✅

**Requirement:** All quality gates must pass before production deployment.

- [ ] All unit tests passing (`pytest tests/unit/ -v`)
  - **Minimum coverage:** 80% for unit tests
- [ ] All integration tests passing (`pytest tests/integration/ -v`)
  - **Minimum coverage:** 70% for integration tests
- [ ] Code quality checks passed:
  - [ ] Black formatting (`black src/ tests/ --check --line-length 100`)
  - [ ] Import sorting (`isort src/ tests/ --check --profile black`)
  - [ ] Linting (`flake8 src/ tests/`)
- [ ] Security scans completed:
  - [ ] Bandit security scan (no high/medium severity issues)
  - [ ] Docker image vulnerability scan with Trivy (no critical/high CVEs)
- [ ] CI/CD pipeline passing on `main` branch

**Evidence:** CI/CD pipeline run URL, test coverage reports, security scan results

**Command:**
```bash
# Run all checks locally before deployment
pytest tests/ --cov=apex --cov-report=term-missing
black src/ tests/ --check --line-length 100
isort src/ tests/ --check --profile black
flake8 src/ tests/
bandit -r src/ -f json -o bandit-report.json
```

---

### 3. Security Validation ✅

**Requirement:** All security controls must be validated before production deployment.

- [ ] Run security validation script:
  ```bash
  cd /home/gbass/MyProjects/APEX/infra
  chmod +x security-validation.sh
  ./security-validation.sh prod > security-validation-results.txt
  ```

- [ ] Verify all 10 security controls pass:
  - [ ] 1. VNet Architecture (vnet-apex-prod exists with correct address space)
  - [ ] 2. NSG Rules (container-apps-nsg and private-endpoint-nsg configured)
  - [ ] 3. Private Endpoints (5 endpoints: SQL, Storage, OpenAI, DI, Key Vault)
  - [ ] 4. Private DNS Zones (5 zones configured for A records)
  - [ ] 5. Container Apps VNet Injection (deployed into vnet-apex-prod)
  - [ ] 6. Public Network Access Disabled (all PaaS services)
  - [ ] 7. Managed Identity Configured (User-assigned identity with RBAC)
  - [ ] 8. RBAC Assignments (identity has required roles on all resources)
  - [ ] 9. Network Flow Tests (connectivity via private endpoints)
  - [ ] 10. Azure Security Center (no critical/high security alerts)

**Evidence:** `security-validation-results.txt` with all checks passing

**ISO/IEC 27001 Compliance:**
- A.13.1.1 - Network Controls ✅
- A.13.1.2 - Security of Network Services ✅
- A.13.1.3 - Segregation in Networks ✅
- A.13.2.1 - Information Transfer Policies ✅

---

### 4. Configuration Validation ✅

**Requirement:** All configuration secrets must be deployed to Azure Key Vault.

- [ ] Verify Key Vault exists: `kv-apex-prod`
- [ ] Verify all required secrets are set:
  ```bash
  az keyvault secret list --vault-name kv-apex-prod --query "[].name" -o table
  ```

**Required Secrets:**
- [ ] `AZURE-SQL-CONNECTION-STRING` (with Managed Identity)
- [ ] `AZURE-OPENAI-API-KEY` (if not using Managed Identity)
- [ ] `AZURE-AD-CLIENT-SECRET` (if using client credentials flow)
- [ ] `APPLICATION-INSIGHTS-CONNECTION-STRING`

**Configuration Files:**
- [ ] `infra/parameters/prod.bicepparam` reviewed and approved
- [ ] Environment variables validated in `.env.example`

**Evidence:** Screenshot of Key Vault secrets (names only, not values)

---

### 5. Database Migration Validation ✅

**Requirement:** Database migrations must be tested in staging before production.

- [ ] Staging database migration completed successfully
- [ ] Staging application running with new schema
- [ ] Staging integration tests passing
- [ ] Database backup taken before production migration:
  ```bash
  az sql db export \
    --resource-group apex-rg-prod \
    --server sql-apex-prod \
    --name apex-db-prod \
    --storage-key-type SharedAccessKey \
    --storage-key <SAS-TOKEN> \
    --storage-uri "https://stapexprod.blob.core.windows.net/backups/pre-migration-$(date +%Y%m%d-%H%M%S).bacpac"
  ```

- [ ] Alembic migration script reviewed:
  ```bash
  alembic history
  alembic current
  alembic upgrade head --sql  # Generate SQL for review
  ```

**Evidence:** Staging migration log, database backup confirmation, SQL review

---

### 6. Deployment Artifacts ✅

**Requirement:** All deployment artifacts must be available and verified.

- [ ] Docker image built and pushed to Azure Container Registry:
  - **Image:** `apexacr.azurecr.io/apex-backend:<version-tag>`
  - **Tag:** Semantic version (e.g., `v1.2.3`) or commit SHA
- [ ] Image vulnerability scan passed (Trivy)
- [ ] Bicep templates validated:
  ```bash
  az deployment group validate \
    --resource-group apex-rg-prod \
    --template-file infra/main.bicep \
    --parameters infra/parameters/prod.bicepparam
  ```

**Evidence:** Container Registry image details, vulnerability scan results, Bicep validation output

---

### 7. Monitoring and Alerting Setup ✅

**Requirement:** Monitoring must be configured before deployment.

- [ ] Application Insights workspace created (`appi-apex-prod`)
- [ ] Log Analytics workspace linked
- [ ] Alert rules configured (see [MONITORING_AND_ALERTING.md](./MONITORING_AND_ALERTING.md)):
  - [ ] High error rate (>5% in 5 minutes)
  - [ ] High response time (P95 >2s for 5 minutes)
  - [ ] Low availability (<99.9% in 5 minutes)
  - [ ] Failed requests spike (>10 in 5 minutes)
  - [ ] Container restart events
- [ ] Notification channels configured:
  - [ ] Email: ops-team@company.com
  - [ ] PagerDuty/Slack integration (if applicable)
- [ ] Azure Monitor dashboard created

**Evidence:** Screenshot of alert rules, notification test confirmation

---

### 8. Rollback Plan ✅

**Requirement:** Rollback procedures must be documented and tested.

- [ ] Previous production revision identified:
  ```bash
  az containerapp revision list \
    --name apex-backend-prod \
    --resource-group apex-rg-prod \
    --query "[?properties.active==\`true\`].name" -o table
  ```

- [ ] Rollback procedure documented (see [RUNBOOK.md](./RUNBOOK.md#rollback-procedure))
- [ ] Rollback decision criteria defined:
  - Health checks failing for >5 minutes
  - Error rate >10% for >5 minutes
  - Critical bug identified impacting estimation accuracy
  - Security vulnerability discovered

**Evidence:** Current revision name, rollback procedure confirmation

---

### 9. Team Readiness ✅

**Requirement:** Operations team must be prepared for deployment and incident response.

- [ ] On-call engineer identified and available
- [ ] Deployment team assembled (minimum 2 engineers)
- [ ] Incident response team on standby
- [ ] Communication channels ready:
  - [ ] War room / Slack channel: #apex-deployment
  - [ ] Escalation contacts documented
- [ ] Runbook reviewed by deployment team

**Evidence:** Team roster, on-call schedule confirmation

---

### 10. Pre-Deployment Sign-Off ✅

**Requirement:** Final approval before deployment execution.

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Technical Lead |  |  |  |
| Operations Manager |  |  |  |
| Security Team |  |  |  |
| Deployment Engineer |  |  |  |

**Deployment Authorized:** ☐ Yes ☐ No

---

## Deployment Execution Phase

### 11. Infrastructure Deployment ✅

**Procedure:** See [RUNBOOK.md](./RUNBOOK.md#infrastructure-deployment)

- [ ] Start deployment window
- [ ] Announce deployment start (Slack, email)
- [ ] Deploy infrastructure using `deploy.sh`:
  ```bash
  cd /home/gbass/MyProjects/APEX/infra
  ./deploy.sh prod apex-rg-prod
  ```

- [ ] Deployment script confirmations:
  - [ ] Change approval confirmation: `yes`
  - [ ] Production confirmation: `DEPLOY-TO-PRODUCTION`
- [ ] What-if analysis reviewed (no unexpected changes)
- [ ] Infrastructure deployment completed successfully
- [ ] Deployment outputs recorded:
  - Container Apps FQDN
  - SQL Server FQDN
  - Storage Account name
  - Key Vault URI

**Duration:** ~15-20 minutes

**Evidence:** Deployment script output, Azure Portal confirmation

---

### 12. Database Migration ✅

**Procedure:** See [RUNBOOK.md](./RUNBOOK.md#database-migration)

- [ ] Connect to Azure SQL via private endpoint (from jump box or VPN)
- [ ] Verify current Alembic revision:
  ```bash
  alembic current
  ```

- [ ] Run database migrations:
  ```bash
  alembic upgrade head
  ```

- [ ] Verify migration success:
  ```bash
  alembic current  # Should show latest revision
  ```

- [ ] Test database connectivity from Container App:
  ```bash
  az containerapp exec \
    --name apex-backend-prod \
    --resource-group apex-rg-prod \
    --command "python -c 'from apex.database.connection import engine; engine.connect()'"
  ```

**Duration:** ~5-10 minutes

**Evidence:** Alembic output, database version confirmation

**Rollback:** If migration fails, restore from pre-migration backup (see Step 5)

---

### 13. Application Deployment ✅

**Procedure:** See [RUNBOOK.md](./RUNBOOK.md#application-deployment)

- [ ] Update Container App with new image:
  ```bash
  az containerapp update \
    --name apex-backend-prod \
    --resource-group apex-rg-prod \
    --image apexacr.azurecr.io/apex-backend:<version-tag> \
    --set-env-vars \
      ENVIRONMENT=production \
      AZURE_SQL_SERVER=sql-apex-prod.database.windows.net \
      AZURE_SQL_DATABASE=apex-db-prod \
      # ... other environment variables
  ```

- [ ] New revision created automatically
- [ ] Health check endpoint responding:
  ```bash
  curl https://apex-backend-prod.azurecontainerapps.io/health/live
  # Expected: {"status": "alive", "timestamp": "..."}
  ```

- [ ] Readiness check passing:
  ```bash
  curl https://apex-backend-prod.azurecontainerapps.io/health/ready
  # Expected: {"status": "ready", "checks": {...}, "timestamp": "..."}
  ```

**Duration:** ~5-10 minutes

**Evidence:** Container App revision ID, health check responses

---

### 14. Smoke Tests ✅

**Procedure:** See [RUNBOOK.md](./RUNBOOK.md#smoke-tests)

Run comprehensive smoke tests to validate critical functionality:

- [ ] **Authentication Test:**
  ```bash
  # Obtain Azure AD token
  export TOKEN=$(az account get-access-token --resource <CLIENT_ID> --query accessToken -o tsv)

  # Test authenticated endpoint
  curl -H "Authorization: Bearer $TOKEN" \
    https://apex-backend-prod.azurecontainerapps.io/api/v1/projects/ \
    | jq .

  # Expected: HTTP 200, paginated project list
  ```

- [ ] **Project Creation Test:**
  ```bash
  curl -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"project_number":"SMOKE-TEST-001","project_name":"Smoke Test Project","voltage_level":345}' \
    https://apex-backend-prod.azurecontainerapps.io/api/v1/projects/

  # Expected: HTTP 201, project created with ID
  ```

- [ ] **Document Upload Test:**
  ```bash
  curl -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@test-document.pdf" \
    -F "project_id=<PROJECT_ID>" \
    -F "document_type=scope" \
    https://apex-backend-prod.azurecontainerapps.io/api/v1/documents/upload

  # Expected: HTTP 201, document uploaded to blob storage
  ```

- [ ] **Azure Service Integration Tests:**
  - [ ] Blob Storage: Document upload successful (check Azure Portal)
  - [ ] Azure SQL: Project persisted in database (query via SQL client)
  - [ ] Azure OpenAI: LLM call succeeds (check Application Insights traces)
  - [ ] Document Intelligence: PDF parsing succeeds (validate document endpoint)
  - [ ] Key Vault: Secrets accessible (check Container App logs)

- [ ] **Performance Baseline:**
  ```bash
  # Measure API response times
  for i in {1..10}; do
    curl -w "@curl-format.txt" -o /dev/null -s \
      -H "Authorization: Bearer $TOKEN" \
      https://apex-backend-prod.azurecontainerapps.io/api/v1/projects/
  done

  # Expected: P95 <500ms for list operations
  ```

**Duration:** ~10-15 minutes

**Evidence:** Smoke test output, performance metrics, Application Insights traces

**Failure Criteria:** If ANY smoke test fails, STOP and initiate rollback

---

### 15. Traffic Shifting ✅

**Procedure:** Blue-Green traffic shift

- [ ] Verify new revision health:
  ```bash
  az containerapp revision show \
    --name apex-backend-prod \
    --resource-group apex-rg-prod \
    --revision <NEW_REVISION_NAME> \
    --query "properties.healthState"

  # Expected: "Healthy"
  ```

- [ ] Enable traffic splitting (canary):
  ```bash
  az containerapp ingress traffic set \
    --name apex-backend-prod \
    --resource-group apex-rg-prod \
    --revision-weight <NEW_REVISION>=10 <OLD_REVISION>=90
  ```

- [ ] Monitor for 10 minutes:
  - [ ] Error rate within normal range (<1%)
  - [ ] Response time within SLA (P95 <2s)
  - [ ] No critical alerts triggered

- [ ] Shift 100% traffic to new revision:
  ```bash
  az containerapp ingress traffic set \
    --name apex-backend-prod \
    --resource-group apex-rg-prod \
    --revision-weight <NEW_REVISION>=100
  ```

- [ ] **DO NOT deactivate old revision yet** (keep for 24h rollback window)

**Duration:** ~15-20 minutes (including monitoring)

**Evidence:** Traffic distribution confirmation, monitoring dashboard screenshots

---

## Post-Deployment Validation Phase

### 16. End-to-End Testing ✅

**Requirement:** Full workflow validation in production.

- [ ] **Complete Estimation Workflow:**
  1. Create project (via API or UI)
  2. Upload scope document (PDF)
  3. Validate document (Azure DI + LLM)
  4. Upload engineering drawings (PDF)
  5. Validate drawings
  6. Generate estimate (LLM + Monte Carlo)
  7. View estimate (narrative, assumptions, exclusions, line items)
  8. Export estimate (PDF report)

- [ ] **Access Control Testing:**
  - [ ] Estimator role: Can create projects, upload documents, generate estimates
  - [ ] Manager role: Can update project status, approve estimates
  - [ ] Auditor role: Read-only access to projects and estimates
  - [ ] Unauthorized access: 403 Forbidden for users without project access

- [ ] **AACE Classification Testing:**
  - [ ] CLASS_5 estimate generated for conceptual project
  - [ ] CLASS_3 estimate generated for budget project
  - [ ] CLASS_2 estimate generated for bid document validation

**Duration:** ~30-45 minutes

**Evidence:** End-to-end test results, screenshots, API responses

---

### 17. Performance Validation ✅

**Requirement:** Performance must meet SLA targets.

- [ ] Application Insights metrics reviewed (last 30 minutes):
  - [ ] **Availability:** ≥99.9%
  - [ ] **Response Time (P50):** <500ms
  - [ ] **Response Time (P95):** <2s
  - [ ] **Response Time (P99):** <5s
  - [ ] **Error Rate:** <1%
  - [ ] **Failed Requests:** <10 per hour

- [ ] Load test (optional, for major releases):
  ```bash
  # Run load test with 50 concurrent users
  locust -f tests/load/locustfile.py --host https://apex-backend-prod.azurecontainerapps.io
  ```

**Evidence:** Application Insights dashboard screenshots, load test results (if applicable)

---

### 18. Security Posture Validation ✅

**Requirement:** Security controls remain in place after deployment.

- [ ] Re-run security validation script:
  ```bash
  ./security-validation.sh prod > post-deployment-security-validation.txt
  ```

- [ ] Verify all 10 security controls still pass
- [ ] Azure Security Center review:
  - [ ] No new critical/high severity alerts
  - [ ] Secure Score unchanged or improved
- [ ] Verify no public endpoints exposed:
  ```bash
  nslookup sql-apex-prod.database.windows.net
  # Expected: Private IP (10.0.x.x), NOT public IP
  ```

**Evidence:** `post-deployment-security-validation.txt`, Security Center screenshots

---

### 19. Monitoring Dashboard Validation ✅

**Procedure:** See [MONITORING_AND_ALERTING.md](./MONITORING_AND_ALERTING.md#dashboard-setup)

- [ ] Azure Monitor dashboard displaying:
  - [ ] Request rate (requests/minute)
  - [ ] Response time (P50, P95, P99)
  - [ ] Error rate (%)
  - [ ] Availability (%)
  - [ ] Container App health status
  - [ ] Database DTU usage
  - [ ] Blob storage operations
  - [ ] LLM call rate and token usage

- [ ] Alert rules active and firing test (optional):
  ```bash
  # Trigger test alert (if safe in production)
  # Verify notification received within 5 minutes
  ```

**Evidence:** Dashboard screenshots, alert test confirmation

---

### 20. Documentation Updates ✅

**Requirement:** Production documentation must be current.

- [ ] Update production inventory:
  - [ ] Container App revision ID
  - [ ] Docker image version
  - [ ] Database schema version (Alembic revision)
  - [ ] Infrastructure deployment date
  - [ ] Configuration changes

- [ ] Update runbook with lessons learned (if any)
- [ ] Update incident response procedures (if any changes)
- [ ] Tag Git repository with release version:
  ```bash
  git tag -a v1.2.3 -m "Production deployment $(date +%Y-%m-%d)"
  git push origin v1.2.3
  ```

**Evidence:** Updated documentation, Git tag

---

### 21. Stakeholder Notification ✅

**Requirement:** Notify stakeholders of successful deployment.

- [ ] Send deployment success notification:
  - **To:** Estimator team, managers, auditors, IT leadership
  - **Subject:** APEX Production Deployment Complete - v1.2.3
  - **Content:**
    - Deployment date and time
    - Version deployed
    - New features / bug fixes
    - Known issues (if any)
    - Support contact information

- [ ] Update status page (if applicable)

**Evidence:** Email confirmation, status page update

---

### 22. Post-Deployment Sign-Off ✅

**Requirement:** Final validation that deployment is successful.

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Deployment Engineer |  |  |  |
| Technical Lead |  |  |  |
| Operations Manager |  |  |  |

**Deployment Status:** ☐ Success ☐ Partial Success ☐ Failed

**Notes:**

---

## Rollback Phase (If Required)

### 23. Rollback Decision ✅

**Trigger Conditions:**
- Health checks failing for >5 minutes
- Error rate >10% for >5 minutes
- Critical bug impacting estimation accuracy
- Security vulnerability discovered
- Stakeholder request

**Decision Authority:**
- Technical Lead (during deployment)
- On-call Engineer (after deployment)
- Operations Manager (escalation)

- [ ] Rollback decision made by: _______________
- [ ] Reason for rollback: _______________
- [ ] Timestamp: _______________

---

### 24. Execute Rollback ✅

**Procedure:** See [RUNBOOK.md](./RUNBOOK.md#rollback-procedure)

- [ ] Shift traffic back to previous revision:
  ```bash
  az containerapp ingress traffic set \
    --name apex-backend-prod \
    --resource-group apex-rg-prod \
    --revision-weight <OLD_REVISION>=100 <NEW_REVISION>=0
  ```

- [ ] Verify old revision is healthy:
  ```bash
  curl https://apex-backend-prod.azurecontainerapps.io/health/ready
  ```

- [ ] If database migration was applied, rollback database:
  ```bash
  # Option 1: Alembic downgrade
  alembic downgrade -1

  # Option 2: Restore from backup (if migration cannot be rolled back)
  # See DISASTER_RECOVERY.md
  ```

- [ ] Run smoke tests on rolled-back revision
- [ ] Notify stakeholders of rollback

**Duration:** ~5-10 minutes

**Evidence:** Traffic distribution confirmation, health check response, stakeholder notification

---

### 25. Post-Rollback Analysis ✅

**Requirement:** Root cause analysis for failed deployment.

- [ ] Incident report created
- [ ] Root cause analysis completed (5 Whys, Fishbone diagram)
- [ ] Application Insights logs reviewed
- [ ] Database logs reviewed
- [ ] Security logs reviewed
- [ ] Action items identified for remediation
- [ ] Timeline for re-deployment established

**Evidence:** Incident report, RCA documentation

---

## 24-Hour Stability Window

### 26. Continuous Monitoring ✅

**Requirement:** Monitor production for 24 hours after deployment.

**Hours 0-8 (Critical Monitoring):**
- [ ] On-call engineer actively monitoring every 30 minutes
- [ ] No critical alerts triggered
- [ ] Error rate within normal range (<1%)
- [ ] Response time within SLA (P95 <2s)

**Hours 8-24 (Active Monitoring):**
- [ ] On-call engineer monitoring every 2 hours
- [ ] Automated alerts configured and working
- [ ] No degradation in performance

**Evidence:** Monitoring log, incident log (if any)

---

### 27. Deactivate Old Revision ✅

**Requirement:** After 24-hour stability window, deactivate old revision.

- [ ] 24-hour stability window completed successfully
- [ ] No rollback required during stability window
- [ ] Deactivate old revision:
  ```bash
  az containerapp revision deactivate \
    --name apex-backend-prod \
    --resource-group apex-rg-prod \
    --revision <OLD_REVISION_NAME>
  ```

- [ ] Verify only new revision is active:
  ```bash
  az containerapp revision list \
    --name apex-backend-prod \
    --resource-group apex-rg-prod \
    --query "[?properties.active==\`true\`].name" -o table
  ```

**Evidence:** Revision status confirmation

---

## Post-Deployment Review

### 28. Deployment Retrospective ✅

**Requirement:** Team retrospective within 48 hours of deployment.

- [ ] Retrospective meeting scheduled
- [ ] Attendees: Deployment team, Technical Lead, Operations Manager
- [ ] Discussion topics:
  - What went well?
  - What could be improved?
  - Deployment duration vs. estimate
  - Issues encountered and resolutions
  - Process improvements for next deployment

**Evidence:** Meeting notes, action items

---

### 29. Deployment Metrics ✅

**Requirement:** Track deployment metrics for continuous improvement.

| Metric | Value |
|--------|-------|
| Total Deployment Duration |  |
| Infrastructure Deployment Time |  |
| Database Migration Time |  |
| Application Deployment Time |  |
| Smoke Test Duration |  |
| Issues Encountered (count) |  |
| Rollback Required? | ☐ Yes ☐ No |
| Downtime (minutes) |  |
| Change Approval to Deployment (days) |  |

---

### 30. Closure ✅

**Requirement:** Formal closure of deployment activity.

- [ ] All checklist items completed
- [ ] All evidence collected and archived
- [ ] Change Request updated to "Closed - Successful"
- [ ] Deployment artifacts archived (logs, screenshots, reports)
- [ ] Lessons learned documented in runbook
- [ ] Next deployment scheduled (if applicable)

**Deployment Closed By:** _______________
**Date:** _______________

---

## Appendix A: Contact Information

### Escalation Paths

| Issue Type | Primary Contact | Escalation Contact |
|------------|-----------------|-------------------|
| Deployment Issues | Deployment Engineer | Technical Lead |
| Database Issues | DBA Team | Database Manager |
| Security Issues | Security Team | CISO |
| Infrastructure Issues | Cloud Team | Cloud Architect |
| Application Issues | Development Team | Engineering Manager |

### On-Call Schedule

| Week | On-Call Engineer | Backup |
|------|------------------|--------|
|  |  |  |

---

## Appendix B: Reference Links

- **Infrastructure as Code:** `/infra/main.bicep`, `/infra/deploy.sh`
- **CI/CD Pipeline:** `/.github/workflows/ci-cd.yml`
- **Security Validation:** `/infra/SECURITY_VALIDATION.md`, `/infra/security-validation.sh`
- **Application Code:** `/src/apex/`
- **Database Migrations:** `/alembic/versions/`
- **Docker Image:** `/Dockerfile`
- **Azure Portal:** https://portal.azure.com
- **Azure DevOps:** (if applicable)
- **Container Registry:** https://apexacr.azurecr.io

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024 | DevOps Team | Initial production deployment checklist |

**Approval:**
- Technical Lead: _______________
- Operations Manager: _______________
- Security Team: _______________

---

**END OF CHECKLIST**
