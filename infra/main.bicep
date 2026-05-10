targetScope = 'resourceGroup'

@description('Primary Azure region for backend resources')
param location string = resourceGroup().location

@description('Existing Container Apps environment name')
param existingContainerAppsEnvironmentName string

@description('ACR name')
param acrName string

@description('ACR SKU')
@allowed([
  'Basic'
  'Standard'
  'Premium'
])
param acrSku string = 'Basic'

@description('Backend Container App name')
param containerAppName string

@description('Backend container image')
param backendImage string

@description('Container CPU')
param containerCpu string = '0.5'

@description('Container memory')
param containerMemory string = '1Gi'

@description('Min replicas')
param minReplicas int = 1

@description('Max replicas')
param maxReplicas int = 1

@description('Backend environment variables')
param backendEnvVars array = []

resource existingContainerEnv 'Microsoft.App/managedEnvironments@2023-05-01' existing = {
  name: existingContainerAppsEnvironmentName
}

module acr './modules/acr.bicep' = {
  name: 'acr-deploy'
  params: {
    name: acrName
    location: location
    sku: acrSku
  }
}

module containerApp './modules/container-app.bicep' = {
  name: 'container-app-deploy'
  params: {
    name: containerAppName
    location: location
    managedEnvironmentId: existingContainerEnv.id
    image: backendImage
    acrLoginServer: acr.outputs.loginServer
    envVars: backendEnvVars
    cpu: containerCpu
    memory: containerMemory
    minReplicas: minReplicas
    maxReplicas: maxReplicas
  }
}

output acrId string = acr.outputs.id
output acrLoginServer string = acr.outputs.loginServer
output containerAppsEnvironmentId string = existingContainerEnv.id
output containerAppId string = containerApp.outputs.id
output containerAppPrincipalId string = containerApp.outputs.principalId
