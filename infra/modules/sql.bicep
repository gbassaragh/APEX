// Azure SQL Database module for APEX
// Creates SQL Server and Database with private endpoint

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

@description('Private DNS Zone ID for SQL')
param privateDnsZoneId string

@description('SQL Server administrator login')
@secure()
param sqlAdminLogin string

@description('SQL Server administrator password')
@secure()
param sqlAdminPassword string

// SKU configuration by environment
var skuByEnvironment = {
  dev: {
    name: 'Basic'
    tier: 'Basic'
    capacity: 5
  }
  staging: {
    name: 'S1'
    tier: 'Standard'
    capacity: 20
  }
  prod: {
    name: 'S2'
    tier: 'Standard'
    capacity: 50
  }
}

var sqlServerName = 'sql-${projectName}-${environment}'
var sqlDatabaseName = 'db-${projectName}-${environment}'
var privateEndpointName = 'pe-sql-${projectName}-${environment}'

// SQL Server
resource sqlServer 'Microsoft.Sql/servers@2023-05-01-preview' = {
  name: sqlServerName
  location: location
  tags: tags
  properties: {
    administratorLogin: sqlAdminLogin
    administratorLoginPassword: sqlAdminPassword
    version: '12.0'
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Disabled' // CRITICAL: No public access
    restrictOutboundNetworkAccess: 'Disabled'
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// SQL Database
resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-05-01-preview' = {
  parent: sqlServer
  name: sqlDatabaseName
  location: location
  tags: tags
  sku: skuByEnvironment[environment]
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    maxSizeBytes: 2147483648 // 2GB
    catalogCollation: 'SQL_Latin1_General_CP1_CI_AS'
    zoneRedundant: environment == 'prod' // Enable zone redundancy in production
    readScale: 'Disabled'
    requestedBackupStorageRedundancy: environment == 'prod' ? 'Geo' : 'Local'
  }
}

// Private Endpoint for SQL Server
resource sqlPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-05-01' = {
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
          privateLinkServiceId: sqlServer.id
          groupIds: [
            'sqlServer'
          ]
        }
      }
    ]
  }
}

// Private DNS Zone Group for automatic DNS registration
resource privateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-05-01' = {
  parent: sqlPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-database-windows-net'
        properties: {
          privateDnsZoneId: privateDnsZoneId
        }
      }
    ]
  }
}

// Enable Microsoft Entra authentication (Azure AD)
resource sqlServerAdministrator 'Microsoft.Sql/servers/administrators@2023-05-01-preview' = {
  parent: sqlServer
  name: 'ActiveDirectory'
  properties: {
    administratorType: 'ActiveDirectory'
    login: 'APEX-Admins' // This should match an Azure AD group
    sid: '00000000-0000-0000-0000-000000000000' // Replace with actual Azure AD group object ID
    tenantId: subscription().tenantId
  }
}

// Firewall rule - NONE (public access disabled)
// All access must be via private endpoint

// Outputs
output sqlServerName string = sqlServer.name
output sqlServerFqdn string = sqlServer.properties.fullyQualifiedDomainName
output sqlDatabaseName string = sqlDatabase.name
output sqlServerId string = sqlServer.id
output sqlDatabaseId string = sqlDatabase.id
output sqlServerIdentityPrincipalId string = sqlServer.identity.principalId
output connectionString string = 'Server=tcp:${sqlServer.properties.fullyQualifiedDomainName},1433;Database=${sqlDatabase.name};Authentication=Active Directory Managed Identity;'
