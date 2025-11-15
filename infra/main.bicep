// APEX Infrastructure - Main Orchestrator
// Deploys all Azure resources with proper dependency ordering

targetScope = 'resourceGroup'

// Parameters
@description('The Azure region for all resources')
param location string = resourceGroup().location

@description('Environment name (dev, staging, prod)')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Project name for resource naming')
param projectName string = 'apex'

@description('Common tags for all resources')
param tags object = {
  Environment: environment
  Project: 'APEX'
  ManagedBy: 'Bicep'
  CostCenter: 'Engineering'
}

// Network Configuration
@description('VNet address prefix')
param vnetAddressPrefix string = '10.0.0.0/16'

@description('Container Apps subnet prefix')
param containerAppsSubnetPrefix string = '10.0.0.0/23'

@description('Private Endpoints subnet prefix')
param privateEndpointsSubnetPrefix string = '10.0.2.0/24'

// ============================================================================
// PHASE 1: Network Infrastructure
// ============================================================================

module network 'modules/network.bicep' = {
  name: 'network-deployment-${environment}'
  params: {
    location: location
    environment: environment
    projectName: projectName
    tags: tags
    vnetAddressPrefix: vnetAddressPrefix
    containerAppsSubnetPrefix: containerAppsSubnetPrefix
    privateEndpointsSubnetPrefix: privateEndpointsSubnetPrefix
  }
}

// ============================================================================
// PHASE 2: Identity
// ============================================================================

// User-Assigned Managed Identity for Container Apps
resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${projectName}-${environment}'
  location: location
  tags: tags
}

// ============================================================================
// PHASE 3: Data & Storage Services (depend on network)
// ============================================================================

module sql 'modules/sql.bicep' = {
  name: 'sql-deployment-${environment}'
  params: {
    location: location
    environment: environment
    projectName: projectName
    tags: tags
    privateEndpointsSubnetId: network.outputs.privateEndpointsSubnetId
    privateDnsZoneId: network.outputs.sqlPrivateDnsZoneId
    managedIdentityPrincipalId: managedIdentity.properties.principalId
  }
  dependsOn: [
    network
  ]
}

module storage 'modules/storage.bicep' = {
  name: 'storage-deployment-${environment}'
  params: {
    location: location
    environment: environment
    projectName: projectName
    tags: tags
    privateEndpointsSubnetId: network.outputs.privateEndpointsSubnetId
    privateDnsZoneId: network.outputs.storagePrivateDnsZoneId
  }
  dependsOn: [
    network
  ]
}

module keyVault 'modules/keyvault.bicep' = {
  name: 'keyvault-deployment-${environment}'
  params: {
    location: location
    environment: environment
    projectName: projectName
    tags: tags
    privateEndpointsSubnetId: network.outputs.privateEndpointsSubnetId
    privateDnsZoneId: network.outputs.keyVaultPrivateDnsZoneId
    managedIdentityPrincipalId: managedIdentity.properties.principalId
  }
  dependsOn: [
    network
  ]
}

// ============================================================================
// PHASE 4: AI Services (depend on network)
// ============================================================================

module openAi 'modules/openai.bicep' = {
  name: 'openai-deployment-${environment}'
  params: {
    location: location
    environment: environment
    projectName: projectName
    tags: tags
    privateEndpointsSubnetId: network.outputs.privateEndpointsSubnetId
    privateDnsZoneId: network.outputs.openAiPrivateDnsZoneId
    managedIdentityPrincipalId: managedIdentity.properties.principalId
  }
  dependsOn: [
    network
  ]
}

module documentIntelligence 'modules/documentintelligence.bicep' = {
  name: 'docIntelligence-deployment-${environment}'
  params: {
    location: location
    environment: environment
    projectName: projectName
    tags: tags
    privateEndpointsSubnetId: network.outputs.privateEndpointsSubnetId
    privateDnsZoneId: network.outputs.cognitiveServicesPrivateDnsZoneId
    managedIdentityPrincipalId: managedIdentity.properties.principalId
  }
  dependsOn: [
    network
  ]
}

// ============================================================================
// PHASE 5: Application Insights (no private endpoint needed)
// ============================================================================

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${projectName}-${environment}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    RetentionInDays: environment == 'prod' ? 90 : 30
    publicNetworkAccessForIngestion: 'Enabled' // Ingestion can remain public
    publicNetworkAccessForQuery: 'Disabled' // Query access private only
  }
}

// ============================================================================
// PHASE 6: Grant Managed Identity Access to Storage
// ============================================================================

// Storage Blob Data Contributor role for Container Apps to upload/download blobs
resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.outputs.storageAccountId, managedIdentity.id, 'Storage Blob Data Contributor')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    storage
  ]
}

// ============================================================================
// PHASE 7: Container Apps (depends on all services)
// ============================================================================

module containerApps 'modules/containerapps.bicep' = {
  name: 'containerapps-deployment-${environment}'
  params: {
    location: location
    environment: environment
    projectName: projectName
    tags: tags
    containerAppsSubnetId: network.outputs.containerAppsSubnetId
    keyVaultUri: keyVault.outputs.keyVaultUri
    managedIdentityId: managedIdentity.id
    managedIdentityClientId: managedIdentity.properties.clientId
    sqlServerFqdn: sql.outputs.sqlServerFqdn
    sqlDatabaseName: sql.outputs.sqlDatabaseName
    openAiEndpoint: openAi.outputs.openAiEndpoint
    openAiDeploymentName: openAi.outputs.gpt4DeploymentName
    documentIntelligenceEndpoint: documentIntelligence.outputs.documentIntelligenceEndpoint
    storageAccountName: storage.outputs.storageAccountName
    appInsightsConnectionString: appInsights.properties.ConnectionString
  }
  dependsOn: [
    network
    sql
    storage
    keyVault
    openAi
    documentIntelligence
    appInsights
    storageRoleAssignment
  ]
}

// ============================================================================
// Outputs
// ============================================================================

output resourceGroupName string = resourceGroup().name
output location string = location
output environment string = environment

// Network
output vnetId string = network.outputs.vnetId
output vnetName string = network.outputs.vnetName

// Identity
output managedIdentityId string = managedIdentity.id
output managedIdentityClientId string = managedIdentity.properties.clientId
output managedIdentityPrincipalId string = managedIdentity.properties.principalId

// SQL Database
output sqlServerName string = sql.outputs.sqlServerName
output sqlServerFqdn string = sql.outputs.sqlServerFqdn
output sqlDatabaseName string = sql.outputs.sqlDatabaseName
output sqlConnectionString string = sql.outputs.sqlConnectionString

// Storage
output storageAccountName string = storage.outputs.storageAccountName
output storageAccountId string = storage.outputs.storageAccountId
output blobEndpoint string = storage.outputs.blobEndpoint
output storageContainers object = storage.outputs.containers

// Key Vault
output keyVaultName string = keyVault.outputs.keyVaultName
output keyVaultId string = keyVault.outputs.keyVaultId
output keyVaultUri string = keyVault.outputs.keyVaultUri

// Azure OpenAI
output openAiName string = openAi.outputs.openAiName
output openAiEndpoint string = openAi.outputs.openAiEndpoint
output gpt4DeploymentName string = openAi.outputs.gpt4DeploymentName

// Document Intelligence
output documentIntelligenceName string = documentIntelligence.outputs.documentIntelligenceName
output documentIntelligenceEndpoint string = documentIntelligence.outputs.documentIntelligenceEndpoint

// Application Insights
output appInsightsName string = appInsights.name
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output appInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey

// Container Apps
output containerAppEnvironmentId string = containerApps.outputs.containerAppEnvironmentId
output containerAppId string = containerApps.outputs.containerAppId
output containerAppFqdn string = containerApps.outputs.containerAppFqdn
output logAnalyticsWorkspaceId string = containerApps.outputs.logAnalyticsWorkspaceId
