param name string
param location string
param managedEnvironmentId string
param image string
param acrLoginServer string
param envVars array = []
param cpu string = '0.5'
param memory string = '1Gi'
param minReplicas int = 1
param maxReplicas int = 1

resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: name
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: managedEnvironmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: name
          image: image
          env: [
            for item in envVars: {
              name: item.name
              value: item.value
            }
          ]
          resources: {
            cpu: json(cpu)
            memory: memory
          }
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

output id string = containerApp.id
output name string = containerApp.name
output principalId string = containerApp.identity.principalId
