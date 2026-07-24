// Documentation-grade Azure sketch for the Enterprise Knowledge Management Platform.
// Review and customize before deploying. This is not applied by CI.
//
// Expected resources (logical):
// - Log Analytics + Application Insights
// - Key Vault
// - Storage account (Blob)
// - Azure Database for PostgreSQL Flexible Server (enable pgvector after create)
// - Azure Container Registry
// - Container Apps Environment + API/frontend apps (wire images manually)

targetScope = 'resourceGroup'

@description('Azure region for resources')
param location string = resourceGroup().location

@description('Short name prefix, lowercase alphanumeric')
@minLength(3)
@maxLength(12)
param namePrefix string = 'ekpdemo'

@description('Administrator login for Flexible Server (password via Key Vault in real deploys)')
param postgresAdminLogin string = 'ekpadmin'

@secure()
@description('Postgres admin password — supply at deploy time, never commit')
param postgresAdminPassword string

@description('Whether to create a public storage account for demos (prefer private in production)')
param allowBlobPublicAccess bool = false

var kvName = '${namePrefix}-kv'
var stName = replace('${namePrefix}stor', '-', '')
var acrName = replace('${namePrefix}acr', '-', '')
var lawName = '${namePrefix}-law'
var aiName = '${namePrefix}-appi'
var pgName = '${namePrefix}-pg'
var caeName = '${namePrefix}-cae'

resource law 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: lawName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appi 'Microsoft.Insights/components@2020-02-02' = {
  name: aiName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: law.id
  }
}

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: kvName
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enableSoftDelete: true
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: stName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: allowBlobPublicAccess
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobServices 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource documentsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobServices
  name: 'documents'
  properties: {
    publicAccess: 'None'
  }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01-preview' = {
  name: pgName
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: postgresAdminPassword
    storage: {
      storageSizeGB: 32
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

resource cae 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: caeName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: law.properties.customerId
        sharedKey: law.listKeys().primarySharedKey
      }
    }
  }
}

output keyVaultName string = kv.name
output storageAccountName string = storage.name
output documentsContainerName string = documentsContainer.name
output acrLoginServer string = acr.properties.loginServer
output postgresFqdn string = postgres.properties.fullyQualifiedDomainName
output containerAppsEnvironmentId string = cae.id
output applicationInsightsConnectionString string = appi.properties.ConnectionString
output nextSteps string = 'Enable CREATE EXTENSION vector on Postgres, push images to ACR, create Container Apps for API/frontend, and map Key Vault secrets. See docs/azure.md.'
