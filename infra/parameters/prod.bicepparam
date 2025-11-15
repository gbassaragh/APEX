// APEX Production Environment Parameters
// Enterprise-grade configuration with high availability and compliance

using '../main.bicep'

// Environment Configuration
param location = 'eastus'
param environment = 'prod'
param projectName = 'apex'

// Resource Tags
param tags = {
  Environment: 'Production'
  Project: 'APEX'
  ManagedBy: 'Bicep'
  CostCenter: 'Operations'
  Owner: 'Platform Team'
  Compliance: 'ISO-27001'
  DataClassification: 'Confidential'
  BusinessCriticality: 'High'
  DisasterRecovery: 'Required'
}

// Network Configuration
param vnetAddressPrefix = '10.0.0.0/16'
param containerAppsSubnetPrefix = '10.0.0.0/23'  // 512 IPs for Container Apps (zone redundant)
param privateEndpointsSubnetPrefix = '10.0.2.0/24'  // 256 IPs for Private Endpoints

/*
  Production Environment Notes:

  - SQL: S2 tier (50 DTUs, 250GB max) with zone redundancy - $150/month
  - Storage: GZRS (Geo-Zone Redundant) - ~$80/month for 500GB
  - Key Vault: Premium tier with purge protection - $0.03/10K operations
  - OpenAI: 80K TPM (tokens per minute) capacity - Usage-based pricing
  - Document Intelligence: S0 (Standard) - $1.50/1K pages
  - Container Apps: 1.0 vCPU, 2Gi memory, 2-10 replicas with auto-scaling

  Estimated Monthly Cost: ~$1,200-1,800 (usage-dependent)

  High Availability & Disaster Recovery:
  - Zone redundancy enabled on all supported services
  - Geo-redundant storage with read access (RA-GZRS)
  - 90-day retention on logs and backups
  - 30-day soft delete with purge protection on Key Vault
  - Multi-replica Container Apps with health checks
  - Automated failover capabilities

  Security & Compliance:
  - All PaaS services behind private endpoints (Zero Trust)
  - Public network access completely disabled
  - Managed Identity for all authentication (no secrets)
  - NSG rules: Deny all except Container Apps → Private Endpoints
  - ISO 27001 policy initiative applied at resource group level
  - All data encrypted at rest and in transit (TLS 1.2+)
  - Comprehensive audit logging to Application Insights
  - RBAC with principle of least privilege

  Performance & Scalability:
  - Auto-scaling: 2-10 Container App replicas based on load (50 concurrent requests/replica)
  - SQL: 50 DTUs supports ~30-50 concurrent estimators
  - OpenAI: 80K TPM supports ~20-30 concurrent LLM operations
  - Storage: Premium performance tier with lifecycle management

  Monitoring & Observability:
  - Application Insights with 90-day retention
  - Log Analytics workspace with structured logging
  - Custom alerts for critical operations
  - Performance metrics and distributed tracing

  Network Topology:
  - VNet: 10.0.0.0/16 (65,536 IPs)
  - Container Apps: 10.0.0.0/23 (512 IPs, zone-redundant)
  - Private Endpoints: 10.0.2.0/24 (256 IPs)
  - Reserved: 10.0.3.0/24 - 10.0.255.0/24 for future expansion
*/
