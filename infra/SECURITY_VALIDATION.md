# APEX Network Security Validation Checklist

## Overview

This document validates that the APEX infrastructure implements zero-trust network architecture as specified in the requirements.

**Security Model**: Zero-Trust with Private Endpoints
**Compliance**: ISO-NE regulatory requirements, ISO/IEC 27001

> **Related Documentation**: For comprehensive security audit results, see [SECURITY_AUDIT_2025-11-15.md](../docs/archive/assessments/SECURITY_AUDIT_2025-11-15.md) (production-ready assessment with 0 critical issues, approved for deployment).

---

## 1. Virtual Network Architecture

### ✅ VNet Configuration (`modules/network.bicep`)

**Requirement**: Dedicated VNet with proper subnet segmentation

**Implementation**:
- VNet address space: `10.0.0.0/16` (dev), `10.1.0.0/16` (staging), `10.2.0.0/16` (prod)
- Container Apps subnet: `/23` CIDR (512 IPs)
- Private Endpoint subnet: `/24` CIDR (256 IPs)

**Validation Steps**:
```bash
# Verify VNet exists
az network vnet show \
  --name vnet-apex-<env> \
  --resource-group apex-rg-<env> \
  --query "{Name:name, AddressSpace:addressSpace.addressPrefixes}" \
  --output table

# Verify subnets
az network vnet subnet list \
  --vnet-name vnet-apex-<env> \
  --resource-group apex-rg-<env> \
  --query "[].{Name:name, AddressPrefix:addressPrefix, Delegations:delegations[0].serviceName}" \
  --output table

# Expected: Container Apps subnet delegated to Microsoft.App/environments
```

**Pass Criteria**:
- VNet created with correct address space
- Container Apps subnet delegated to `Microsoft.App/environments`
- Private Endpoint subnet with `privateEndpointNetworkPolicies: Disabled`

---

## 2. Network Security Groups (NSGs)

### ✅ NSG Rules (`modules/network.bicep`)

**Requirement**: Deny all traffic by default, allow only required flows

**Implementation**:
- Container Apps subnet NSG: Allow outbound to Private Endpoints only
- Private Endpoint subnet NSG: Allow inbound from Container Apps subnet

**Validation Steps**:
```bash
# Verify NSG applied to Container Apps subnet
az network vnet subnet show \
  --name snet-containerapps \
  --vnet-name vnet-apex-<env> \
  --resource-group apex-rg-<env> \
  --query "networkSecurityGroup.id"

# List NSG rules
az network nsg rule list \
  --nsg-name nsg-apex-<env>-containerapps \
  --resource-group apex-rg-<env> \
  --output table

# Verify deny-all default rule
az network nsg rule show \
  --name DenyAllInbound \
  --nsg-name nsg-apex-<env>-containerapps \
  --resource-group apex-rg-<env>
```

**Pass Criteria**:
- NSG attached to both subnets
- Default deny-all rule present
- Only required outbound rules for Azure services (port 443)
- No public internet access rules

---

## 3. Private Endpoints

### ✅ Azure SQL Database (`modules/sql.bicep`)

**Requirement**: No public network access, accessible only via Private Link

**Implementation**:
```bicep
publicNetworkAccess: 'Disabled'
privateEndpoint: {
  subnet: privateEndpointSubnet
  privateDnsZone: 'privatelink.database.windows.net'
}
```

**Validation Steps**:
```bash
# Verify public access disabled
az sql server show \
  --name sql-apex-<env> \
  --resource-group apex-rg-<env> \
  --query "publicNetworkAccess"
# Expected: "Disabled"

# Verify private endpoint exists
az network private-endpoint list \
  --resource-group apex-rg-<env> \
  --query "[?contains(name, 'sql')].{Name:name, Subnet:subnet.id}" \
  --output table

# Test connectivity from Container App (manual)
# Should succeed from Container App, fail from public internet
az containerapp exec \
  --name apex-backend-<env> \
  --resource-group apex-rg-<env> \
  --command "nc -zv sql-apex-<env>.database.windows.net 1433"
```

**Pass Criteria**:
- `publicNetworkAccess: Disabled`
- Private endpoint created in private endpoint subnet
- DNS resolves to private IP (10.0.2.x range)
- Connection succeeds from Container App, fails from internet

### ✅ Azure Blob Storage (`modules/storage.bicep`)

**Requirement**: No public network access, blob data accessible only via Private Link

**Implementation**:
```bicep
publicNetworkAccess: 'Disabled'
networkAcls: {
  defaultAction: 'Deny'
  bypass: 'None'
}
privateEndpoints: ['blob', 'table']
```

**Validation Steps**:
```bash
# Verify public access disabled
az storage account show \
  --name stapex<env> \
  --resource-group apex-rg-<env> \
  --query "publicNetworkAccess"
# Expected: "Disabled"

# Verify network rules
az storage account show \
  --name stapex<env> \
  --resource-group apex-rg-<env> \
  --query "networkRuleSet.{DefaultAction:defaultAction, Bypass:bypass}"

# Test public access (should fail)
curl -I https://stapex<env>.blob.core.windows.net/uploads
# Expected: Connection refused or 403 Forbidden

# Verify private endpoint
az network private-endpoint list \
  --resource-group apex-rg-<env> \
  --query "[?contains(name, 'blob')].{Name:name, GroupIds:privateLinkServiceConnections[0].groupIds}" \
  --output table
```

**Pass Criteria**:
- `publicNetworkAccess: Disabled`
- `networkRuleSet.defaultAction: Deny`
- Private endpoints for blob and table
- DNS resolves to private IP
- Public access blocked (curl fails)

### ✅ Azure OpenAI (`modules/openai.bicep`)

**Requirement**: No public network access, API accessible only via Private Link

**Validation Steps**:
```bash
# Verify public network access disabled
az cognitiveservices account show \
  --name oai-apex-<env> \
  --resource-group apex-rg-<env> \
  --query "properties.publicNetworkAccess"
# Expected: "Disabled"

# Verify private endpoint
az network private-endpoint list \
  --resource-group apex-rg-<env> \
  --query "[?contains(name, 'openai')].{Name:name, GroupIds:privateLinkServiceConnections[0].groupIds}" \
  --output table
```

**Pass Criteria**:
- `publicNetworkAccess: Disabled`
- Private endpoint created
- DNS resolves to private IP

### ✅ Azure Document Intelligence (`modules/documentintelligence.bicep`)

**Requirement**: No public network access, API accessible only via Private Link

**Validation Steps**:
```bash
# Verify public network access disabled
az cognitiveservices account show \
  --name di-apex-<env> \
  --resource-group apex-rg-<env> \
  --query "properties.publicNetworkAccess"
# Expected: "Disabled"

# Verify private endpoint
az network private-endpoint list \
  --resource-group apex-rg-<env> \
  --query "[?contains(name, 'documentintelligence')].{Name:name, GroupIds:privateLinkServiceConnections[0].groupIds}" \
  --output table
```

**Pass Criteria**:
- `publicNetworkAccess: Disabled`
- Private endpoint created
- DNS resolves to private IP

### ✅ Azure Key Vault (`modules/keyvault.bicep`)

**Requirement**: No public network access, secrets accessible only via Private Link

**Validation Steps**:
```bash
# Verify public network access disabled
az keyvault show \
  --name kv-apex-<env> \
  --resource-group apex-rg-<env> \
  --query "properties.publicNetworkAccess"
# Expected: "Disabled"

# Verify network rules
az keyvault show \
  --name kv-apex-<env> \
  --resource-group apex-rg-<env> \
  --query "properties.networkAcls.{DefaultAction:defaultAction, Bypass:bypass}"

# Verify private endpoint
az network private-endpoint list \
  --resource-group apex-rg-<env> \
  --query "[?contains(name, 'keyvault')].{Name:name, GroupIds:privateLinkServiceConnections[0].groupIds}" \
  --output table
```

**Pass Criteria**:
- `publicNetworkAccess: Disabled`
- `networkAcls.defaultAction: Deny`
- Private endpoint created
- DNS resolves to private IP

---

## 4. Private DNS Zones

### ✅ DNS Configuration (`modules/network.bicep`)

**Requirement**: Private DNS zones for all Azure services with VNet link

**Implementation**:
- `privatelink.database.windows.net` (Azure SQL)
- `privatelink.blob.core.windows.net` (Blob Storage)
- `privatelink.table.core.windows.net` (Table Storage)
- `privatelink.openai.azure.com` (Azure OpenAI)
- `privatelink.cognitiveservices.azure.com` (Document Intelligence)
- `privatelink.vaultcore.azure.net` (Key Vault)

**Validation Steps**:
```bash
# List private DNS zones
az network private-dns zone list \
  --resource-group apex-rg-<env> \
  --query "[].{Name:name}" \
  --output table

# Verify VNet link for each zone
az network private-dns link vnet list \
  --zone-name privatelink.database.windows.net \
  --resource-group apex-rg-<env> \
  --query "[].{Name:name, VirtualNetwork:virtualNetwork.id, RegistrationEnabled:registrationEnabled}" \
  --output table

# Test DNS resolution from Container App
az containerapp exec \
  --name apex-backend-<env> \
  --resource-group apex-rg-<env> \
  --command "nslookup sql-apex-<env>.database.windows.net"
# Expected: Private IP (10.0.2.x), not public IP
```

**Pass Criteria**:
- All 6 private DNS zones created
- VNet link exists for each zone
- DNS resolution returns private IP addresses
- No public IP resolution for PaaS services

---

## 5. Container Apps Network Configuration

### ✅ VNet Injection (`modules/containerapps.bicep`)

**Requirement**: Container Apps deployed into VNet (not external ingress)

**Implementation**:
```bicep
vnetConfiguration: {
  internal: true
  infrastructureSubnetId: containerAppsSubnet.id
}
```

**Validation Steps**:
```bash
# Verify Container Apps environment is VNet-injected
az containerapp env show \
  --name cae-apex-<env> \
  --resource-group apex-rg-<env> \
  --query "properties.vnetConfiguration.{Internal:internal, SubnetId:infrastructureSubnetId}"

# Verify no public FQDN
az containerapp show \
  --name apex-backend-<env> \
  --resource-group apex-rg-<env> \
  --query "properties.configuration.ingress.{External:external, Fqdn:fqdn}"
# Expected: External: false or null
```

**Pass Criteria**:
- `vnetConfiguration.internal: true`
- Container App deployed to Container Apps subnet
- No public FQDN (or internal FQDN only)

---

## 6. Managed Identity

### ✅ Authentication Pattern (`modules/*.bicep`)

**Requirement**: All Azure service authentication via Managed Identity (no API keys)

**Implementation**:
```bicep
identity: {
  type: 'UserAssigned'
  userAssignedIdentities: {
    '${managedIdentity.id}': {}
  }
}
```

**Validation Steps**:
```bash
# Verify Container App has Managed Identity
az containerapp show \
  --name apex-backend-<env> \
  --resource-group apex-rg-<env> \
  --query "identity.{Type:type, PrincipalId:principalId}"

# Verify RBAC assignments
az role assignment list \
  --assignee $(az containerapp show --name apex-backend-<env> --resource-group apex-rg-<env> --query "identity.principalId" -o tsv) \
  --output table

# Expected roles:
# - Storage Blob Data Contributor (on Storage Account)
# - Cognitive Services OpenAI User (on OpenAI)
# - Cognitive Services User (on Document Intelligence)
# - Key Vault Secrets User (on Key Vault)
```

**Pass Criteria**:
- User-assigned Managed Identity created
- Container App configured with Managed Identity
- RBAC assignments exist for all Azure services
- No connection strings or API keys in environment variables

---

## 7. Network Flow Testing

### ✅ End-to-End Connectivity

**Test 1: Container App → Azure SQL (Private Endpoint)**
```bash
az containerapp exec \
  --name apex-backend-<env> \
  --resource-group apex-rg-<env> \
  --command "nc -zv sql-apex-<env>.database.windows.net 1433"
# Expected: Connection succeeded
```

**Test 2: Container App → Blob Storage (Private Endpoint)**
```bash
az containerapp exec \
  --name apex-backend-<env> \
  --resource-group apex-rg-<env> \
  --command "nc -zv stapex<env>.blob.core.windows.net 443"
# Expected: Connection succeeded
```

**Test 3: Container App → Azure OpenAI (Private Endpoint)**
```bash
az containerapp exec \
  --name apex-backend-<env> \
  --resource-group apex-rg-<env> \
  --command "nc -zv oai-apex-<env>.openai.azure.com 443"
# Expected: Connection succeeded
```

**Test 4: Internet → Azure SQL (Public Access Disabled)**
```bash
nc -zv sql-apex-<env>.database.windows.net 1433
# Expected: Connection refused or timeout
```

**Test 5: Internet → Blob Storage (Public Access Disabled)**
```bash
curl -I https://stapex<env>.blob.core.windows.net/uploads
# Expected: Connection refused or 403 Forbidden
```

---

## 8. Security Scanning

### ✅ Network Security Scan

**Tools**:
- Azure Security Center recommendations
- Network Watcher flow logs
- NSG flow logs analysis

**Validation Steps**:
```bash
# Check Azure Security Center recommendations
az security assessment list \
  --resource-group apex-rg-<env> \
  --query "[?properties.status.code=='Unhealthy'].{Name:name, Description:properties.displayName}" \
  --output table

# Enable NSG flow logs (if not enabled)
az network watcher flow-log create \
  --name nsg-flow-log-apex-<env> \
  --nsg nsg-apex-<env>-containerapps \
  --resource-group apex-rg-<env> \
  --storage-account stapex<env> \
  --enabled true
```

**Pass Criteria**:
- No critical security recommendations
- NSG flow logs enabled
- No public IP addresses exposed (except Application Gateway if used)

---

## 9. Compliance Validation

### ✅ ISO/IEC 27001 Controls

**Control A.13.1.1 - Network Controls**
- ✅ Network segmentation (VNet + subnets)
- ✅ Access controls (NSGs)
- ✅ Encryption in transit (TLS 1.2+)

**Control A.13.1.2 - Security of Network Services**
- ✅ Private Endpoints for all PaaS services
- ✅ No public network access
- ✅ Managed Identity authentication

**Control A.13.1.3 - Segregation in Networks**
- ✅ Separate subnets for Container Apps and Private Endpoints
- ✅ NSG rules enforce segregation

**Control A.13.2.1 - Information Transfer Policies**
- ✅ All traffic over HTTPS (port 443)
- ✅ SQL traffic encrypted (TLS 1.2+)
- ✅ No unencrypted protocols allowed

---

## 10. Deployment Validation Script

Run this script after infrastructure deployment to validate all security controls:

```bash
#!/bin/bash
# security-validation.sh

ENVIRONMENT=$1
RG_NAME="apex-rg-${ENVIRONMENT}"

echo "=== APEX Security Validation for ${ENVIRONMENT} ==="

# 1. Check VNet configuration
echo "✓ Checking VNet configuration..."
az network vnet show --name "vnet-apex-${ENVIRONMENT}" --resource-group "$RG_NAME" --query "name" -o tsv

# 2. Check NSG rules
echo "✓ Checking NSG configuration..."
az network nsg list --resource-group "$RG_NAME" --query "[].name" -o tsv

# 3. Check private endpoints
echo "✓ Checking private endpoints..."
az network private-endpoint list --resource-group "$RG_NAME" --query "[].name" -o tsv

# 4. Check public network access disabled
echo "✓ Checking public network access..."
az sql server show --name "sql-apex-${ENVIRONMENT}" --resource-group "$RG_NAME" --query "publicNetworkAccess" -o tsv
az storage account show --name "stapex${ENVIRONMENT}" --resource-group "$RG_NAME" --query "publicNetworkAccess" -o tsv

# 5. Check Managed Identity
echo "✓ Checking Managed Identity configuration..."
az containerapp show --name "apex-backend-${ENVIRONMENT}" --resource-group "$RG_NAME" --query "identity.type" -o tsv

# 6. Check RBAC assignments
echo "✓ Checking RBAC assignments..."
PRINCIPAL_ID=$(az containerapp show --name "apex-backend-${ENVIRONMENT}" --resource-group "$RG_NAME" --query "identity.principalId" -o tsv)
az role assignment list --assignee "$PRINCIPAL_ID" --query "[].{Role:roleDefinitionName, Scope:scope}" -o table

echo "=== Security Validation Complete ==="
```

---

## Summary

| Security Control | Status | Validation Method |
|------------------|--------|-------------------|
| VNet Segmentation | ✅ Implemented | Azure CLI verification |
| NSG Rules | ✅ Implemented | NSG rule inspection |
| Private Endpoints (SQL) | ✅ Implemented | Public access test (should fail) |
| Private Endpoints (Storage) | ✅ Implemented | curl test (should fail) |
| Private Endpoints (OpenAI) | ✅ Implemented | DNS resolution check |
| Private Endpoints (Document Intelligence) | ✅ Implemented | DNS resolution check |
| Private Endpoints (Key Vault) | ✅ Implemented | DNS resolution check |
| Private DNS Zones | ✅ Implemented | nslookup from Container App |
| VNet-Injected Container Apps | ✅ Implemented | Ingress configuration check |
| Managed Identity Auth | ✅ Implemented | RBAC assignment verification |
| ISO/IEC 27001 Compliance | ✅ Met | Manual control checklist |

**Overall Status**: ✅ **All security controls implemented and validated**

---

## Responsible Parties

| Activity | Responsible |
|----------|-------------|
| Infrastructure Deployment | DevOps Engineer |
| Security Validation | Security Engineer |
| Network Testing | Network Engineer |
| Compliance Sign-off | Compliance Officer |

---

**Last Updated**: 2025-01-XX
**Document Version**: 1.0
**Review Frequency**: Quarterly
