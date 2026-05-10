param name string
param location string

resource managedEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: name
  location: location
  properties: {}
}

output id string = managedEnvironment.id
output name string = managedEnvironment.name
