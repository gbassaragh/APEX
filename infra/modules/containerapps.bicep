// Azure Container Apps module for APEX
// Creates Container Apps Environment and APEX backend app

@description('The Azure region for resources')
param location string

@description('Environment name (dev, staging, prod)')
param environment string

@description('Project name for resource naming')
param projectName string

@description('Tags to apply to all resources')
param tags object

@description('Subnet ID for Container Apps')
param containerAppsSubnetId string

@description('Key Vault URI for secrets')
param keyVaultUri string

@description('Managed Identity ID for Container Apps')
param managedIdentityId string

@description('Managed Identity Client ID')
param managedIdentityClientId string

@description('SQL Server FQDN')
param sqlServerFqdn string

@description('SQL Database Name')
param sqlDatabaseName string

@description('Azure OpenAI Endpoint')
param openAiEndpoint string

@description('Azure OpenAI Deployment Name')
param openAiDeploymentName string

@description('Document Intelligence Endpoint')
param documentIntelligenceEndpoint string

@description('Storage Account Name')
param storageAccountName string

@description('Application Insights Connection String')
param appInsightsConnectionString string

var containerAppEnvName = 'cae-${projectName}-${environment}'
var containerAppName = 'ca-${projectName}-${environment}'

// Log Analytics Workspace for Container Apps logs
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'log-${projectName}-${environment}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: environment == 'prod' ? 90 : 30
  }
}

// Container Apps Environment
resource containerAppEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: containerAppEnvName
  location: location
  tags: tags
  properties: {
    vnetConfiguration: {
      infrastructureSubnetId: containerAppsSubnetId
      internal: true // Internal environment, no public access
    }
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
    zoneRedundant: environment == 'prod' // Zone redundancy for production
  }
}

// APEX Backend Container App
resource apexContainerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: containerAppName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single' // Single revision mode (use Multiple for blue/green)
      ingress: {
        external: false // Internal only, accessed via private endpoint
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
      secrets: [
        {
          name: 'azure-sql-connection-string'
          keyVaultUrl: '${keyVaultUri}secrets/sql-connection-string'
          identity: managedIdentityId
        }
      ]
      registries: [] // Add ACR registry if using custom image
    }
    template: {
      containers: [
        {
          name: 'apex-backend'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest' // Placeholder - replace with actual image
          resources: {
            cpu: json(environment == 'prod' ? '1.0' : '0.5')
            memory: environment == 'prod' ? '2Gi' : '1Gi'
          }
          env: [
            {
              name: 'ENVIRONMENT'
              value: environment
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: managedIdentityClientId
            }
            {
              name: 'AZURE_SQL_SERVER'
              value: sqlServerFqdn
            }
            {
              name: 'AZURE_SQL_DATABASE'
              value: sqlDatabaseName
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: openAiEndpoint
            }
            {
              name: 'AZURE_OPENAI_DEPLOYMENT'
              value: openAiDeploymentName
            }
            {
              name: 'AZURE_DI_ENDPOINT'
              value: documentIntelligenceEndpoint
            }
            {
              name: 'AZURE_STORAGE_ACCOUNT'
              value: storageAccountName
            }
            {
              name: 'AZURE_KEY_VAULT_URL'
              value: keyVaultUri
            }
            {
              name: 'AZURE_APPINSIGHTS_CONNECTION_STRING'
              value: appInsightsConnectionString
            }
            {
              name: 'LOG_LEVEL'
              value: environment == 'prod' ? 'INFO' : 'DEBUG'
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health/live'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 10
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health/ready'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 5
            }
          ]
        }
      ]
      scale: {
        minReplicas: environment == 'prod' ? 2 : 1
        maxReplicas: environment == 'prod' ? 10 : 3
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

// Outputs
output containerAppEnvironmentId string = containerAppEnvironment.id
output containerAppId string = apexContainerApp.id
output containerAppFqdn string = apexContainerApp.properties.configuration.ingress.fqdn
output logAnalyticsWorkspaceId string = logAnalyticsWorkspace.id
