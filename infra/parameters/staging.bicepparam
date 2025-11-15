// APEX Infrastructure Parameters - Staging Environment
// Mid-tier configuration for testing production-like scenarios

using '../main.bicep'

// ============================================================================
// Basic Configuration
// ============================================================================

param location = 'eastus'
param environment = 'staging'

// ============================================================================
// Network Configuration
// ============================================================================

param vnetAddressPrefix = '10.1.0.0/16'
param containerAppsSubnetPrefix = '10.1.0.0/23'
param privateEndpointSubnetPrefix = '10.1.2.0/24'

// ============================================================================
// Azure SQL Database
// ============================================================================

param sqlSkuName = 'S1'           // Standard tier, 20 DTUs (~$30/month)
param sqlSkuTier = 'Standard'
param sqlMaxSizeBytes = 10737418240  // 10 GB
param sqlZoneRedundant = false       // Save cost, not critical for staging

// ============================================================================
// Storage Account
// ============================================================================

param storageAccountSku = 'Standard_GRS'  // Geo-redundant (~$40/month)

// ============================================================================
// Azure OpenAI
// ============================================================================

param openAiSkuName = 'S0'
param openAiDeployments = [
  {
    name: 'gpt-4'
    model: {
      format: 'OpenAI'
      name: 'gpt-4'
      version: '0613'
    }
    sku: {
      name: 'Standard'
      capacity: 40  // 40K TPM
    }
  }
]

// ============================================================================
// Document Intelligence
// ============================================================================

param documentIntelligenceSkuName = 'S0'  // Standard tier

// ============================================================================
// Key Vault
// ============================================================================

param keyVaultSku = 'standard'
param keyVaultRetentionDays = 30  // Soft-delete retention
param keyVaultPurgeProtection = false  // Allow purge for staging cleanup

// ============================================================================
// Container Apps
// ============================================================================

param containerCpuCores = '0.75'
param containerMemory = '1.5Gi'
param containerMinReplicas = 1
param containerMaxReplicas = 5

// ============================================================================
// Application Insights
// ============================================================================

param appInsightsRetentionDays = 60  // 2 months

// ============================================================================
// Tags
// ============================================================================

param tags = {
  Environment: 'Staging'
  Project: 'APEX'
  ManagedBy: 'Bicep'
  CostCenter: 'Engineering'
  Owner: 'APEX-Team'
}

// ============================================================================
// Estimated Monthly Cost: ~$400-600
// ============================================================================
// SQL Database (S1):           $30/month
// Storage (GRS):                $40/month
// Azure OpenAI (40K TPM):       $60/month
// Document Intelligence (S0):   $150/month (pay-per-use)
// Container Apps:               $80/month (0.75 vCPU, 1.5Gi, 1-5 replicas)
// Key Vault:                    $1/month
// Application Insights:         $30/month (moderate usage)
// Network (VNet, Private Endpoints): $10/month
// ============================================================================
