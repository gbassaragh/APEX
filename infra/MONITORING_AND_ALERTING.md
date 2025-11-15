# APEX Monitoring and Alerting Configuration

**Version:** 1.0
**Last Updated:** 2024
**Owner:** DevOps Team / SRE Team
**Purpose:** Comprehensive observability configuration for production APEX platform

## Overview

This document defines monitoring, alerting, and observability configuration for the APEX platform. It ensures early detection of issues, enables rapid troubleshooting, and supports SLA compliance.

**Observability Stack:**
- **Application Insights** - Application performance monitoring, distributed tracing
- **Log Analytics** - Centralized log aggregation and querying
- **Azure Monitor** - Platform metrics, alert rules, action groups
- **Custom Dashboards** - Real-time operational visibility

**SLA Targets:**
- **Availability:** 99.9% (8.7 hours downtime/year max)
- **Response Time (P95):** <2 seconds
- **Response Time (P99):** <5 seconds
- **Error Rate:** <1%

---

## Table of Contents

1. [Application Insights Configuration](#application-insights-configuration)
2. [Alert Rules](#alert-rules)
3. [Log Analytics Queries](#log-analytics-queries)
4. [Dashboard Setup](#dashboard-setup)
5. [Alert Response Procedures](#alert-response-procedures)
6. [Performance Baselines](#performance-baselines)
7. [Monitoring Checklist](#monitoring-checklist)

---

## Application Insights Configuration

### 1.1 Workspace Setup

**Resource Details:**
- **Name:** `appi-apex-prod`
- **Resource Group:** `apex-rg-prod`
- **Workspace Mode:** Workspace-based (connected to Log Analytics)
- **Retention:** 90 days
- **Daily Cap:** 10 GB/day (with alert at 80%)

**Create Application Insights (if not exists):**

```bash
# Create Log Analytics Workspace (prerequisite)
az monitor log-analytics workspace create \
  --resource-group apex-rg-prod \
  --workspace-name law-apex-prod \
  --location eastus \
  --retention-time 90

# Get Workspace ID
export WORKSPACE_ID=$(az monitor log-analytics workspace show \
  --resource-group apex-rg-prod \
  --workspace-name law-apex-prod \
  --query id -o tsv)

# Create Application Insights
az monitor app-insights component create \
  --app appi-apex-prod \
  --location eastus \
  --resource-group apex-rg-prod \
  --workspace "$WORKSPACE_ID" \
  --application-type web \
  --retention-time 90

# Get Instrumentation Key and Connection String
az monitor app-insights component show \
  --app appi-apex-prod \
  --resource-group apex-rg-prod \
  --query "{InstrumentationKey: instrumentationKey, ConnectionString: connectionString}"
```

### 1.2 Container App Integration

**Environment Variable Configuration:**

```bash
# Update Container App with Application Insights connection string
export APPINSIGHTS_CONNSTRING=$(az monitor app-insights component show \
  --app appi-apex-prod \
  --resource-group apex-rg-prod \
  --query connectionString -o tsv)

az containerapp update \
  --name apex-backend-prod \
  --resource-group apex-rg-prod \
  --set-env-vars \
    AZURE_APPINSIGHTS_CONNECTION_STRING="$APPINSIGHTS_CONNSTRING" \
    LOG_LEVEL=INFO \
    ENVIRONMENT=production
```

**Python Application Configuration (already implemented in `config.py`):**

```python
# src/apex/config.py
AZURE_APPINSIGHTS_CONNECTION_STRING: Optional[str] = None

# src/apex/utils/logging.py
from opencensus.ext.azure.log_exporter import AzureLogHandler

if config.AZURE_APPINSIGHTS_CONNECTION_STRING:
    logger.addHandler(AzureLogHandler(
        connection_string=config.AZURE_APPINSIGHTS_CONNECTION_STRING
    ))
```

### 1.3 Telemetry Configuration

**Auto-Instrumentation (OpenCensus):**

```python
# Enable automatic dependency tracking
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace import config_integration

config_integration.trace_integrations(['requests', 'sqlalchemy', 'httplib'])

# Configure distributed tracing
tracer = Tracer(
    exporter=AzureExporter(connection_string=config.AZURE_APPINSIGHTS_CONNECTION_STRING),
    sampler=ProbabilitySampler(1.0),  # 100% sampling in production
)
```

**Custom Metrics (Example):**

```python
# Track LLM usage
from opencensus.stats import aggregation as aggregation_module
from opencensus.stats import measure as measure_module
from opencensus.stats import stats as stats_module

# Define custom metrics
llm_tokens_measure = measure_module.MeasureInt(
    "apex/llm/tokens",
    "Tokens used for LLM calls",
    "tokens"
)

# Record metric
stats_module.stats.view_manager.measure_to_view_map.register_view(
    view_module.View(
        "apex/llm/total_tokens",
        "Total LLM tokens used",
        [],
        llm_tokens_measure,
        aggregation_module.SumAggregation()
    )
)
```

---

## Alert Rules

### 2.1 Critical Alerts (PagerDuty / Immediate Response)

#### Alert 1: High Error Rate

**Condition:** Request failure rate >5% over 5 minutes

```bash
# Create metric alert rule
az monitor metrics alert create \
  --name "APEX-HighErrorRate-Critical" \
  --resource-group apex-rg-prod \
  --scopes "/subscriptions/<sub-id>/resourceGroups/apex-rg-prod/providers/Microsoft.Insights/components/appi-apex-prod" \
  --condition "avg requests/failed > 5" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --severity 0 \
  --description "Critical: Request error rate exceeds 5% threshold" \
  --action <action-group-id>
```

**Kusto Query (for query-based alert):**

```kusto
requests
| where timestamp > ago(5m)
| summarize
    TotalRequests = count(),
    FailedRequests = countif(success == false)
| extend ErrorRate = (FailedRequests * 100.0) / TotalRequests
| where ErrorRate > 5
```

#### Alert 2: Service Unavailable

**Condition:** Availability <99.9% over 5 minutes

```bash
az monitor metrics alert create \
  --name "APEX-LowAvailability-Critical" \
  --resource-group apex-rg-prod \
  --scopes "/subscriptions/<sub-id>/resourceGroups/apex-rg-prod/providers/Microsoft.Insights/components/appi-apex-prod" \
  --condition "avg availabilityResults/availabilityPercentage < 99.9" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --severity 0 \
  --description "Critical: Service availability below SLA threshold" \
  --action <action-group-id>
```

#### Alert 3: Container App Health Failure

**Condition:** All replicas unhealthy

```bash
az monitor metrics alert create \
  --name "APEX-ContainerUnhealthy-Critical" \
  --resource-group apex-rg-prod \
  --scopes "/subscriptions/<sub-id>/resourceGroups/apex-rg-prod/providers/Microsoft.App/containerApps/apex-backend-prod" \
  --condition "avg Replicas == 0" \
  --window-size 2m \
  --evaluation-frequency 1m \
  --severity 0 \
  --description "Critical: No healthy replicas available" \
  --action <action-group-id>
```

#### Alert 4: Database Connection Failures

**Condition:** Database errors >10 in 5 minutes

```kusto
exceptions
| where timestamp > ago(5m)
| where type contains "SqlException" or type contains "DatabaseError"
| summarize ErrorCount = count()
| where ErrorCount > 10
```

```bash
# Create log alert rule
az monitor scheduled-query create \
  --name "APEX-DatabaseErrors-Critical" \
  --resource-group apex-rg-prod \
  --scopes "/subscriptions/<sub-id>/resourceGroups/apex-rg-prod/providers/Microsoft.Insights/components/appi-apex-prod" \
  --condition "count > 10" \
  --condition-query "exceptions | where timestamp > ago(5m) | where type contains 'SqlException' | summarize ErrorCount = count()" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --severity 0 \
  --description "Critical: Database connection errors detected" \
  --action <action-group-id>
```

---

### 2.2 Warning Alerts (Email / Slack Notification)

#### Alert 5: Elevated Response Time

**Condition:** P95 response time >2 seconds over 10 minutes

```bash
az monitor metrics alert create \
  --name "APEX-SlowResponseTime-Warning" \
  --resource-group apex-rg-prod \
  --scopes "/subscriptions/<sub-id>/resourceGroups/apex-rg-prod/providers/Microsoft.Insights/components/appi-apex-prod" \
  --condition "avg requests/duration > 2000" \
  --window-size 10m \
  --evaluation-frequency 5m \
  --severity 2 \
  --description "Warning: API response time elevated above 2s threshold" \
  --action <action-group-id>
```

#### Alert 6: High Memory Usage

**Condition:** Container memory usage >80%

```bash
az monitor metrics alert create \
  --name "APEX-HighMemory-Warning" \
  --resource-group apex-rg-prod \
  --scopes "/subscriptions/<sub-id>/resourceGroups/apex-rg-prod/providers/Microsoft.App/containerApps/apex-backend-prod" \
  --condition "avg UsageNanoCores > 3200000000" \
  --window-size 10m \
  --evaluation-frequency 5m \
  --severity 2 \
  --description "Warning: Container memory usage exceeds 80%" \
  --action <action-group-id>
```

#### Alert 7: LLM Token Usage Spike

**Condition:** LLM tokens >100K in 1 hour (cost control)

```kusto
customEvents
| where timestamp > ago(1h)
| where name == "llm_call"
| extend tokens = toint(customDimensions["tokens_used"])
| summarize TotalTokens = sum(tokens)
| where TotalTokens > 100000
```

```bash
az monitor scheduled-query create \
  --name "APEX-LLMTokens-Warning" \
  --resource-group apex-rg-prod \
  --scopes "/subscriptions/<sub-id>/resourceGroups/apex-rg-prod/providers/Microsoft.Insights/components/appi-apex-prod" \
  --condition "count > 100000" \
  --condition-query "customEvents | where timestamp > ago(1h) | where name == 'llm_call' | extend tokens = toint(customDimensions['tokens_used']) | summarize TotalTokens = sum(tokens)" \
  --window-size 1h \
  --evaluation-frequency 15m \
  --severity 2 \
  --description "Warning: LLM token usage spike detected (cost control)" \
  --action <action-group-id>
```

#### Alert 8: Document Validation Failures

**Condition:** >20% of document validations failing in 30 minutes

```kusto
customEvents
| where timestamp > ago(30m)
| where name == "document_validation"
| extend status = tostring(customDimensions["validation_status"])
| summarize Total = count(), Failed = countif(status == "failed")
| extend FailureRate = (Failed * 100.0) / Total
| where FailureRate > 20
```

---

### 2.3 Action Groups

**Action Group 1: Critical Alerts (PagerDuty)**

```bash
# Create action group for critical alerts
az monitor action-group create \
  --name "APEX-Critical-ActionGroup" \
  --resource-group apex-rg-prod \
  --short-name "APEX-Crit" \
  --email-receiver \
    name="OnCallEmail" \
    email="oncall@company.com" \
    use-common-alert-schema=true \
  --webhook-receiver \
    name="PagerDuty" \
    service-uri="https://events.pagerduty.com/integration/<key>/enqueue" \
    use-common-alert-schema=true
```

**Action Group 2: Warning Alerts (Email + Slack)**

```bash
az monitor action-group create \
  --name "APEX-Warning-ActionGroup" \
  --resource-group apex-rg-prod \
  --short-name "APEX-Warn" \
  --email-receiver \
    name="OpsTeam" \
    email="ops-team@company.com" \
    use-common-alert-schema=true \
  --webhook-receiver \
    name="Slack" \
    service-uri="https://hooks.slack.com/services/<webhook>" \
    use-common-alert-schema=true
```

---

## Log Analytics Queries

### 3.1 Performance Queries

#### Request Performance Summary (Last Hour)

```kusto
requests
| where timestamp > ago(1h)
| summarize
    TotalRequests = count(),
    AvgDuration = avg(duration),
    P50Duration = percentile(duration, 50),
    P95Duration = percentile(duration, 95),
    P99Duration = percentile(duration, 99),
    FailureRate = (countif(success == false) * 100.0) / count()
| extend
    AvgDurationMs = round(AvgDuration, 2),
    P50DurationMs = round(P50Duration, 2),
    P95DurationMs = round(P95Duration, 2),
    P99DurationMs = round(P99Duration, 2),
    FailureRatePct = round(FailureRate, 2)
```

#### Slowest API Endpoints (Last 24 Hours)

```kusto
requests
| where timestamp > ago(24h)
| summarize
    CallCount = count(),
    AvgDuration = avg(duration),
    P95Duration = percentile(duration, 95)
    by name
| where CallCount > 10  // Only endpoints with significant traffic
| order by P95Duration desc
| take 20
| extend
    AvgDurationMs = round(AvgDuration, 2),
    P95DurationMs = round(P95Duration, 2)
```

#### Request Volume by Hour (Last 7 Days)

```kusto
requests
| where timestamp > ago(7d)
| summarize RequestCount = count() by bin(timestamp, 1h), resultCode
| render timechart
```

---

### 3.2 Error Queries

#### Top Exceptions (Last 24 Hours)

```kusto
exceptions
| where timestamp > ago(24h)
| summarize
    ExceptionCount = count(),
    AffectedUsers = dcount(user_Id),
    SampleMessage = any(outerMessage)
    by type, method
| order by ExceptionCount desc
| take 20
```

#### Failed Requests by Endpoint

```kusto
requests
| where timestamp > ago(24h) and success == false
| summarize FailureCount = count() by name, resultCode
| order by FailureCount desc
```

#### Error Rate Trend (Last 7 Days)

```kusto
requests
| where timestamp > ago(7d)
| summarize
    Total = count(),
    Failed = countif(success == false)
    by bin(timestamp, 1h)
| extend ErrorRate = (Failed * 100.0) / Total
| render timechart
```

---

### 3.3 Dependency Queries

#### External Dependency Performance

```kusto
dependencies
| where timestamp > ago(1h)
| summarize
    CallCount = count(),
    AvgDuration = avg(duration),
    P95Duration = percentile(duration, 95),
    FailureRate = (countif(success == false) * 100.0) / count()
    by target, type
| extend
    AvgDurationMs = round(AvgDuration, 2),
    P95DurationMs = round(P95Duration, 2),
    FailureRatePct = round(FailureRate, 2)
| order by CallCount desc
```

#### Azure SQL Database Performance

```kusto
dependencies
| where timestamp > ago(1h)
| where type == "SQL"
| summarize
    QueryCount = count(),
    AvgDuration = avg(duration),
    P95Duration = percentile(duration, 95)
    by name
| where QueryCount > 10
| order by P95Duration desc
| take 20
```

#### Azure OpenAI LLM Usage

```kusto
customEvents
| where timestamp > ago(24h)
| where name == "llm_call"
| extend
    model = tostring(customDimensions["model"]),
    tokens = toint(customDimensions["tokens_used"]),
    action = tostring(customDimensions["action"])
| summarize
    CallCount = count(),
    TotalTokens = sum(tokens),
    AvgTokens = avg(tokens)
    by model, action
| extend
    AvgTokensRounded = round(AvgTokens, 0)
| order by TotalTokens desc
```

#### Blob Storage Operations

```kusto
dependencies
| where timestamp > ago(1h)
| where type == "Azure blob"
| summarize
    UploadCount = countif(name contains "upload"),
    DownloadCount = countif(name contains "download"),
    DeleteCount = countif(name contains "delete"),
    AvgDuration = avg(duration)
    by bin(timestamp, 5m)
| render timechart
```

---

### 3.4 Business Metrics

#### Estimation Activity (Last 7 Days)

```kusto
customEvents
| where timestamp > ago(7d)
| where name in ("estimate_generated", "document_validated", "project_created")
| summarize EventCount = count() by name, bin(timestamp, 1d)
| render columnchart
```

#### Document Validation Success Rate

```kusto
customEvents
| where timestamp > ago(24h)
| where name == "document_validation"
| extend status = tostring(customDimensions["validation_status"])
| summarize
    Total = count(),
    Passed = countif(status == "passed"),
    Failed = countif(status == "failed"),
    ManualReview = countif(status == "manual_review")
| extend
    PassRate = round((Passed * 100.0) / Total, 2),
    FailRate = round((Failed * 100.0) / Total, 2),
    ManualReviewRate = round((ManualReview * 100.0) / Total, 2)
```

#### Average Estimation Generation Time

```kusto
customEvents
| where timestamp > ago(7d)
| where name == "estimate_generated"
| extend duration_seconds = toint(customDimensions["duration_seconds"])
| summarize
    Count = count(),
    AvgDuration = avg(duration_seconds),
    P50Duration = percentile(duration_seconds, 50),
    P95Duration = percentile(duration_seconds, 95)
| extend
    AvgDurationMin = round(AvgDuration / 60.0, 2),
    P95DurationMin = round(P95Duration / 60.0, 2)
```

---

### 3.5 User Activity Queries

#### Active Users (Last 24 Hours)

```kusto
requests
| where timestamp > ago(24h)
| where user_Id != ""
| summarize
    RequestCount = count(),
    UniqueEndpoints = dcount(name)
    by user_Id
| order by RequestCount desc
| take 50
```

#### Authentication Failures

```kusto
requests
| where timestamp > ago(24h)
| where resultCode == 401
| summarize FailureCount = count() by bin(timestamp, 1h), url
| render timechart
```

---

## Dashboard Setup

### 4.1 Production Operations Dashboard

**Dashboard Name:** APEX Production Operations

**Create Dashboard:**

```bash
# Create dashboard in Azure Portal
# Navigate to: Dashboard > New Dashboard > Blank Dashboard

# Or use Azure CLI to create dashboard JSON
```

**Dashboard Tiles:**

#### Tile 1: Request Rate (Requests/Minute)

```kusto
requests
| where timestamp > ago(30m)
| summarize RequestsPerMinute = count() by bin(timestamp, 1m)
| render timechart
```

**Visualization:** Line chart
**Refresh:** 1 minute

#### Tile 2: Error Rate (%)

```kusto
requests
| where timestamp > ago(30m)
| summarize
    Total = count(),
    Failed = countif(success == false)
    by bin(timestamp, 1m)
| extend ErrorRate = (Failed * 100.0) / Total
| project timestamp, ErrorRate
| render timechart
```

**Visualization:** Line chart with threshold line at 1%
**Refresh:** 1 minute

#### Tile 3: Response Time (P50, P95, P99)

```kusto
requests
| where timestamp > ago(30m)
| summarize
    P50 = percentile(duration, 50),
    P95 = percentile(duration, 95),
    P99 = percentile(duration, 99)
    by bin(timestamp, 1m)
| render timechart
```

**Visualization:** Multi-line chart
**Refresh:** 1 minute

#### Tile 4: Availability (%)

```kusto
availabilityResults
| where timestamp > ago(30m)
| summarize AvailabilityPct = avg(availabilityPercentage) by bin(timestamp, 1m)
| render timechart
```

**Visualization:** Line chart with threshold line at 99.9%
**Refresh:** 1 minute

#### Tile 5: Container App Health

```kusto
customMetrics
| where timestamp > ago(5m)
| where name == "Replicas"
| summarize HealthyReplicas = max(value)
| extend Status = iff(HealthyReplicas >= 2, "Healthy", "Degraded")
```

**Visualization:** Single value tile with color coding
**Refresh:** 1 minute

#### Tile 6: Top Exceptions

```kusto
exceptions
| where timestamp > ago(30m)
| summarize ExceptionCount = count() by type
| top 5 by ExceptionCount
| render barchart
```

**Visualization:** Bar chart
**Refresh:** 5 minutes

#### Tile 7: Database Performance

```kusto
dependencies
| where timestamp > ago(30m)
| where type == "SQL"
| summarize
    AvgDuration = avg(duration),
    P95Duration = percentile(duration, 95)
    by bin(timestamp, 1m)
| render timechart
```

**Visualization:** Line chart
**Refresh:** 1 minute

#### Tile 8: LLM Token Usage (Last Hour)

```kusto
customEvents
| where timestamp > ago(1h)
| where name == "llm_call"
| extend tokens = toint(customDimensions["tokens_used"])
| summarize TotalTokens = sum(tokens) by bin(timestamp, 5m)
| render timechart
```

**Visualization:** Area chart
**Refresh:** 5 minutes

#### Tile 9: Document Validation Status

```kusto
customEvents
| where timestamp > ago(24h)
| where name == "document_validation"
| extend status = tostring(customDimensions["validation_status"])
| summarize Count = count() by status
| render piechart
```

**Visualization:** Pie chart
**Refresh:** 5 minutes

#### Tile 10: Active Alerts

```kusto
AlertsManagementResources
| where type == "microsoft.alertsmanagement/alerts"
| where properties.essentials.severity in ("Sev0", "Sev1", "Sev2")
| where properties.essentials.monitorCondition == "Fired"
| summarize ActiveAlerts = count() by tostring(properties.essentials.severity)
```

**Visualization:** Single value tile
**Refresh:** 1 minute

---

### 4.2 Business Metrics Dashboard

**Dashboard Name:** APEX Business Metrics

**Tiles:**

1. **Projects Created (Last 7 Days)** - Trend chart
2. **Documents Uploaded (Last 7 Days)** - Trend chart
3. **Estimates Generated (Last 7 Days)** - Trend chart
4. **Document Validation Success Rate** - Gauge chart
5. **Average Estimation Time** - Single value
6. **Top Users (by Activity)** - Bar chart
7. **AACE Class Distribution** - Pie chart
8. **LLM Cost Estimate (Last 30 Days)** - Single value

---

## Alert Response Procedures

### 5.1 Critical Alert Response (Severity 0)

**Response Time:** Within 15 minutes
**Escalation:** Immediate PagerDuty notification

#### High Error Rate Alert

1. **Check Dashboard:** Review error rate trend and affected endpoints
2. **Query Exceptions:**
   ```kusto
   exceptions
   | where timestamp > ago(15m)
   | summarize count() by type, method
   | order by count_ desc
   ```
3. **Check Container Logs:**
   ```bash
   az containerapp logs show \
     --name apex-backend-prod \
     --resource-group apex-rg-prod \
     --tail 100
   ```
4. **Assess Impact:** Determine if issue affects all users or specific scenarios
5. **Decision:**
   - If >10% error rate for >5 minutes: Initiate rollback (see RUNBOOK.md)
   - If localized issue: Monitor and prepare fix
   - If external dependency: Contact vendor/escalate

#### Service Unavailable Alert

1. **Check Container Health:**
   ```bash
   az containerapp show \
     --name apex-backend-prod \
     --resource-group apex-rg-prod \
     --query "properties.runningStatus"
   ```
2. **Check Replica Count:**
   ```bash
   az containerapp revision show \
     --name apex-backend-prod \
     --resource-group apex-rg-prod \
     --revision <CURRENT_REVISION> \
     --query "properties.replicas"
   ```
3. **Decision:**
   - If replicas = 0: Restart Container App
   - If health checks failing: Investigate application logs
   - If infrastructure issue: Contact Azure Support

#### Database Connection Failures

1. **Verify Private Endpoint:**
   ```bash
   az network private-endpoint show \
     --name pe-sql-apex-prod \
     --resource-group apex-rg-prod \
     --query "privateLinkServiceConnections[0].privateLinkServiceConnectionState"
   ```
2. **Check SQL Server Status:**
   ```bash
   az sql server show \
     --name sql-apex-prod \
     --resource-group apex-rg-prod \
     --query "state"
   ```
3. **Decision:**
   - If Private Endpoint disconnected: Reconnect and test
   - If SQL Server unavailable: Contact Azure Support
   - If Managed Identity permissions lost: Re-assign RBAC

---

### 5.2 Warning Alert Response (Severity 2)

**Response Time:** Within 1 hour
**Escalation:** Email + Slack notification

#### Elevated Response Time Alert

1. **Identify Slow Endpoints:**
   ```kusto
   requests
   | where timestamp > ago(30m)
   | summarize P95Duration = percentile(duration, 95) by name
   | where P95Duration > 2000
   | order by P95Duration desc
   ```
2. **Check Dependencies:**
   ```kusto
   dependencies
   | where timestamp > ago(30m)
   | summarize P95Duration = percentile(duration, 95) by target
   | order by P95Duration desc
   ```
3. **Actions:**
   - If database queries slow: Review query performance, add indexes
   - If LLM calls slow: Check Azure OpenAI service health
   - If gradual degradation: Scale up Container App replicas

#### High Memory Usage Alert

1. **Check Container Metrics:**
   ```bash
   az monitor metrics list \
     --resource <container-app-resource-id> \
     --metric UsageNanoCores WorkingSetBytes \
     --start-time "$(date -u -d '30 minutes ago' '+%Y-%m-%dT%H:%M:%SZ')" \
     --interval PT1M
   ```
2. **Actions:**
   - If sustained high memory: Scale up CPU/memory limits
   - If memory leak suspected: Restart container, investigate code

---

## Performance Baselines

### 6.1 Expected Performance Metrics

**Production Baseline (Normal Load):**

| Metric | Baseline Value | Threshold (Alert) |
|--------|---------------|-------------------|
| Request Rate | 50-200 req/min | N/A |
| Error Rate | <0.5% | >1% (warning), >5% (critical) |
| Availability | 99.95% | <99.9% (critical) |
| Response Time (P50) | <300ms | >500ms (warning) |
| Response Time (P95) | <1s | >2s (warning), >5s (critical) |
| Response Time (P99) | <2s | >5s (warning), >10s (critical) |
| Database Query (P95) | <100ms | >500ms (warning) |
| LLM Call (P95) | <5s | >15s (warning) |
| Memory Usage | 40-60% | >80% (warning), >95% (critical) |
| CPU Usage | 20-40% | >70% (warning), >90% (critical) |

**Peak Load (End of Quarter, Regulatory Deadlines):**

| Metric | Peak Value |
|--------|------------|
| Request Rate | 500-1000 req/min |
| Error Rate | <1% |
| Response Time (P95) | <3s |
| Concurrent Users | 50-100 |

---

## Monitoring Checklist

### 7.1 Daily Monitoring Tasks

- [ ] Review dashboard (morning standup)
- [ ] Check for active alerts
- [ ] Review overnight error count
- [ ] Verify backup completion (see DISASTER_RECOVERY.md)
- [ ] Check LLM token usage (cost control)

### 7.2 Weekly Monitoring Tasks

- [ ] Review performance trends (week-over-week)
- [ ] Analyze slow queries and optimize
- [ ] Review top exceptions and create Jira tickets
- [ ] Check Application Insights data retention
- [ ] Verify alert rules are firing correctly (test alerts)

### 7.3 Monthly Monitoring Tasks

- [ ] Review SLA compliance (availability, response time, error rate)
- [ ] Analyze capacity trends and forecast scaling needs
- [ ] Review and update alert thresholds based on actual usage
- [ ] Conduct tabletop exercise for critical alerts
- [ ] Review monitoring costs (Application Insights ingestion)

---

## Appendix: Kusto Query Cheat Sheet

### Common Filters

```kusto
// Time filters
| where timestamp > ago(1h)
| where timestamp between (datetime(2024-01-01) .. datetime(2024-01-31))

// String filters
| where name contains "estimate"
| where name startswith "api/v1/"
| where resultCode in ("500", "503")

// Numeric filters
| where duration > 1000
| where resultCode >= 400 and resultCode < 500
```

### Aggregations

```kusto
// Count
| summarize count()
| summarize count() by name

// Percentiles
| summarize p50 = percentile(duration, 50), p95 = percentile(duration, 95)

// Distinct count
| summarize UniqueUsers = dcount(user_Id)

// Multiple aggregations
| summarize
    TotalRequests = count(),
    AvgDuration = avg(duration),
    MaxDuration = max(duration)
    by bin(timestamp, 5m)
```

### Visualization

```kusto
// Time series chart
| summarize count() by bin(timestamp, 1h)
| render timechart

// Bar chart
| summarize count() by resultCode
| render barchart

// Pie chart
| summarize count() by name
| render piechart
```

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024 | DevOps Team | Initial monitoring and alerting configuration |

**Approval:**
- SRE Lead: _______________
- Technical Lead: _______________
- Operations Manager: _______________

---

**END OF MONITORING AND ALERTING GUIDE**
