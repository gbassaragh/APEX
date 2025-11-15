// APEX Development Environment Parameters
// Cost-optimized configuration for development and testing

using '../main.bicep'

// Environment Configuration
param location = 'eastus'
param environment = 'dev'
param projectName = 'apex'

// Resource Tags
param tags = {
  Environment: 'Development'
  Project: 'APEX'
  ManagedBy: 'Bicep'
  CostCenter: 'Engineering'
  Owner: 'DevTeam'
  Purpose: 'Development and Testing'
}

// Network Configuration
param vnetAddressPrefix = '10.0.0.0/16'
param containerAppsSubnetPrefix = '10.0.0.0/23'  // 512 IPs for Container Apps
param privateEndpointsSubnetPrefix = '10.0.2.0/24'  // 256 IPs for Private Endpoints

/*
  Development Environment Notes:

  - SQL: Basic tier (5 DTUs, 2GB max) - $4.90/month
  - Storage: LRS (Local Redundant) - ~$20/month for 100GB
  - Key Vault: Standard tier - $0.03/10K operations
  - OpenAI: 10K TPM (tokens per minute) capacity
  - Document Intelligence: F0 (Free tier) - 500 pages/month
  - Container Apps: 0.5 vCPU, 1Gi memory, 1 replica min

  Estimated Monthly Cost: ~$150-200

  Security:
  - All PaaS services behind private endpoints
  - Public network access disabled
  - Managed Identity for all authentication
  - NSG rules: Container Apps → Private Endpoints only

  Limitations:
  - No zone redundancy (single availability zone)
  - Shorter retention periods (30 days logs, 7 days soft delete)
  - Lower performance tiers (suitable for <10 concurrent users)
*/
