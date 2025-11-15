// Azure AI Document Intelligence module for APEX
// Creates Document Intelligence (Form Recognizer) resource with private endpoint

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

@description('Private DNS Zone ID for Cognitive Services')
param privateDnsZoneId string

@description('Managed Identity principal ID for Container Apps')
param managedIdentityPrincipalId string

var docIntelligenceName = 'di-${projectName}-${environment}'
var privateEndpointName = 'pe-di-${projectName}-${environment}'

// SKU by environment
var skuByEnvironment = {
  dev: 'F0' // Free tier for development
  staging: 'S0' // Standard tier
  prod: 'S0' // Standard tier
}

// Document Intelligence Account
resource documentIntelligence 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: docIntelligenceName
  location: location
  tags: tags
  kind: 'FormRecognizer'
  sku: {
    name: skuByEnvironment[environment]
  }
  properties: {
    customSubDomainName: docIntelligenceName
    publicNetworkAccess: 'Disabled' // CRITICAL: No public access
    networkAcls: {
      defaultAction: 'Deny'
      ipRules: []
      virtualNetworkRules: []
    }
    disableLocalAuth: false // Keep key-based auth as fallback
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// Private Endpoint for Document Intelligence
resource docIntelligencePrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-05-01' = {
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
          privateLinkServiceId: documentIntelligence.id
          groupIds: [
            'account'
          ]
        }
      }
    ]
  }
}

// Private DNS Zone Group
resource privateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-05-01' = {
  parent: docIntelligencePrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-cognitiveservices-azure-com'
        properties: {
          privateDnsZoneId: privateDnsZoneId
        }
      }
    ]
  }
}

// RBAC: Grant Container Apps Managed Identity access to Document Intelligence
// Built-in role: Cognitive Services User (a97b65f3-24c7-4388-baec-2e87135dc908)
resource docIntelligenceUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(documentIntelligence.id, managedIdentityPrincipalId, 'Cognitive Services User')
  scope: documentIntelligence
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Outputs
output documentIntelligenceName string = documentIntelligence.name
output documentIntelligenceId string = documentIntelligence.id
output documentIntelligenceEndpoint string = documentIntelligence.properties.endpoint
