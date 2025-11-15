// Network infrastructure module for APEX
// Creates VNet, subnets, NSGs, and Private DNS zones

@description('The Azure region for resources')
param location string

@description('Environment name (dev, staging, prod)')
param environment string

@description('Project name for resource naming')
param projectName string

@description('Tags to apply to all resources')
param tags object

// VNet configuration
var vnetName = 'vnet-${projectName}-${environment}'
var vnetAddressPrefix = '10.0.0.0/16'

// Subnet configuration
var containerAppsSubnetName = 'snet-containerapps'
var containerAppsSubnetPrefix = '10.0.0.0/23' // 512 IPs for Container Apps scaling
var privateEndpointsSubnetName = 'snet-privateendpoints'
var privateEndpointsSubnetPrefix = '10.0.2.0/24' // 256 IPs for private endpoints

// NSG names
var containerAppsNsgName = 'nsg-containerapps-${environment}'
var privateEndpointsNsgName = 'nsg-privateendpoints-${environment}'

// Private DNS zone names
var privateDnsZones = [
  'privatelink.database.windows.net' // SQL Database
  'privatelink.blob.${az.environment().suffixes.storage}' // Storage Account
  'privatelink.vaultcore.azure.net' // Key Vault
  'privatelink.openai.azure.com' // Azure OpenAI
  'privatelink.cognitiveservices.azure.com' // Document Intelligence
]

// NSG for Container Apps subnet
resource containerAppsNsg 'Microsoft.Network/networkSecurityGroups@2023-05-01' = {
  name: containerAppsNsgName
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'AllowPrivateEndpoints'
        properties: {
          description: 'Allow traffic to private endpoints'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: containerAppsSubnetPrefix
          destinationAddressPrefix: privateEndpointsSubnetPrefix
          access: 'Allow'
          priority: 100
          direction: 'Outbound'
        }
      }
      {
        name: 'AllowAzureServices'
        properties: {
          description: 'Allow outbound to Azure services for monitoring'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRanges: [
            '443'
            '80'
          ]
          sourceAddressPrefix: containerAppsSubnetPrefix
          destinationAddressPrefix: 'AzureCloud'
          access: 'Allow'
          priority: 110
          direction: 'Outbound'
        }
      }
      {
        name: 'DenyAllOutbound'
        properties: {
          description: 'Deny all other outbound traffic'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
          access: 'Deny'
          priority: 4096
          direction: 'Outbound'
        }
      }
    ]
  }
}

// NSG for Private Endpoints subnet
resource privateEndpointsNsg 'Microsoft.Network/networkSecurityGroups@2023-05-01' = {
  name: privateEndpointsNsgName
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'AllowContainerAppsInbound'
        properties: {
          description: 'Allow inbound from Container Apps subnet'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: containerAppsSubnetPrefix
          destinationAddressPrefix: privateEndpointsSubnetPrefix
          access: 'Allow'
          priority: 100
          direction: 'Inbound'
        }
      }
      {
        name: 'DenyAllInbound'
        properties: {
          description: 'Deny all other inbound traffic'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
          access: 'Deny'
          priority: 4096
          direction: 'Inbound'
        }
      }
    ]
  }
}

// Virtual Network
resource vnet 'Microsoft.Network/virtualNetworks@2023-05-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    subnets: [
      {
        name: containerAppsSubnetName
        properties: {
          addressPrefix: containerAppsSubnetPrefix
          networkSecurityGroup: {
            id: containerAppsNsg.id
          }
          delegations: [
            {
              name: 'Microsoft.App.environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
          serviceEndpoints: []
          privateEndpointNetworkPolicies: 'Enabled'
        }
      }
      {
        name: privateEndpointsSubnetName
        properties: {
          addressPrefix: privateEndpointsSubnetPrefix
          networkSecurityGroup: {
            id: privateEndpointsNsg.id
          }
          privateEndpointNetworkPolicies: 'Disabled' // Required for private endpoints
        }
      }
    ]
  }
}

// Private DNS Zones
resource privateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = [for zone in privateDnsZones: {
  name: zone
  location: 'global'
  tags: tags
}]

// Link Private DNS Zones to VNet
resource privateDnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = [for (zone, i) in privateDnsZones: {
  parent: privateDnsZone[i]
  name: '${vnetName}-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}]

// Outputs
output vnetId string = vnet.id
output vnetName string = vnet.name
output containerAppsSubnetId string = vnet.properties.subnets[0].id
output privateEndpointsSubnetId string = vnet.properties.subnets[1].id
output privateDnsZoneIds object = {
  sql: privateDnsZone[0].id
  storage: privateDnsZone[1].id
  keyvault: privateDnsZone[2].id
  openai: privateDnsZone[3].id
  cognitiveservices: privateDnsZone[4].id
}
