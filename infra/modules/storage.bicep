// Azure Storage Account module for APEX
// Creates Storage Account with containers and private endpoint

@description('The Azure region for resources')
param location string

@description('Environment name (dev, staging, prod)')
param environment string

@description('Project name for resource naming')
param projectName string

@description('Tags to apply to all resources')
param tags object

@description('Subnet ID for private endpoint')
param privateEndpointsSubnetId string

@description('Private DNS Zone ID for Storage')
param privateDnsZoneId string

// Storage account requires globally unique name - remove hyphens and use uniqueString
var storageAccountName = 'st${projectName}${environment}${uniqueString(resourceGroup().id)}'
var privateEndpointName = 'pe-storage-${projectName}-${environment}'

// Container names
var containers = [
  'uploads' // User document uploads
  'processed' // Processed documents after parsing
  'dead-letter-queue' // Failed operations
  'risk-distributions' // Monte Carlo simulation results
]

// SKU configuration by environment
var skuByEnvironment = {
  dev: 'Standard_LRS'
  staging: 'Standard_GRS'
  prod: 'Standard_GZRS' // Geo-zone redundant for production
}

// Storage Account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: skuByEnvironment[environment]
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false // CRITICAL: No public blob access
    allowSharedKeyAccess: true // Required for some tools, but prefer Managed Identity
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Disabled' // CRITICAL: No public access
    networkAcls: {
      bypass: 'None' // No exceptions
      defaultAction: 'Deny' // Deny all
      ipRules: []
      virtualNetworkRules: []
    }
    encryption: {
      services: {
        blob: {
          enabled: true
          keyType: 'Account'
        }
        file: {
          enabled: true
          keyType: 'Account'
        }
      }
      keySource: 'Microsoft.Storage'
    }
  }
}

// Blob Service
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: environment == 'prod' ? 30 : 7 // Longer retention in production
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: environment == 'prod' ? 30 : 7
    }
    cors: {
      corsRules: []
    }
  }
}

// Create blob containers
resource blobContainers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = [for container in containers: {
  parent: blobService
  name: container
  properties: {
    publicAccess: 'None' // No public access
    metadata: {}
  }
}]

// Private Endpoint for Blob Storage
resource storagePrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-05-01' = {
  name: privateEndpointName
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointsSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: privateEndpointName
        properties: {
          privateLinkServiceId: storageAccount.id
          groupIds: [
            'blob' // Private endpoint for blob storage
          ]
        }
      }
    ]
  }
}

// Private DNS Zone Group for automatic DNS registration
resource privateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-05-01' = {
  parent: storagePrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-blob-core-windows-net'
        properties: {
          privateDnsZoneId: privateDnsZoneId
        }
      }
    ]
  }
}

// Outputs
output storageAccountName string = storageAccount.name
output storageAccountId string = storageAccount.id
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob
output containers object = {
  uploads: containers[0]
  processed: containers[1]
  deadLetterQueue: containers[2]
  riskDistributions: containers[3]
}
