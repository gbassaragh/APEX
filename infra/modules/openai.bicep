// Azure OpenAI module for APEX
// Creates Azure OpenAI resource with GPT-4 deployment and private endpoint

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

@description('Private DNS Zone ID for OpenAI')
param privateDnsZoneId string

@description('Managed Identity principal ID for Container Apps')
param managedIdentityPrincipalId string

var openAiName = 'openai-${projectName}-${environment}'
var privateEndpointName = 'pe-openai-${projectName}-${environment}'

// GPT-4 deployment configuration
var gpt4DeploymentName = 'gpt-4'
var gpt4ModelName = 'gpt-4'
var gpt4ModelVersion = '0613' // Stable version

// Capacity by environment (TPM - Tokens Per Minute)
var capacityByEnvironment = {
  dev: 10 // 10K TPM
  staging: 40 // 40K TPM
  prod: 80 // 80K TPM
}

// Azure OpenAI Account
resource openAi 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: openAiName
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0' // Standard tier
  }
  properties: {
    customSubDomainName: openAiName
    publicNetworkAccess: 'Disabled' // CRITICAL: No public access
    networkAcls: {
      defaultAction: 'Deny'
      ipRules: []
      virtualNetworkRules: []
    }
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// GPT-4 Model Deployment
resource gpt4Deployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = {
  parent: openAi
  name: gpt4DeploymentName
  sku: {
    name: 'Standard'
    capacity: capacityByEnvironment[environment]
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: gpt4ModelName
      version: gpt4ModelVersion
    }
    raiPolicyName: 'Microsoft.Default' // Responsible AI policy
  }
}

// Private Endpoint for Azure OpenAI
resource openAiPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-05-01' = {
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
          privateLinkServiceId: openAi.id
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
  parent: openAiPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-openai-azure-com'
        properties: {
          privateDnsZoneId: privateDnsZoneId
        }
      }
    ]
  }
}

// RBAC: Grant Container Apps Managed Identity access to OpenAI
// Built-in role: Cognitive Services OpenAI User (5e0bd9bd-7b93-4f28-af87-19fc36ad61bd)
resource openAiUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAi.id, managedIdentityPrincipalId, 'Cognitive Services OpenAI User')
  scope: openAi
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Outputs
output openAiName string = openAi.name
output openAiId string = openAi.id
output openAiEndpoint string = openAi.properties.endpoint
output gpt4DeploymentName string = gpt4Deployment.name
