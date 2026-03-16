import { PublicClientApplication, type Configuration } from "@azure/msal-browser"
import { entraConfig } from "./config"

const config: Configuration = {
  auth: {
    clientId: entraConfig.clientId,
    authority: `https://login.microsoftonline.com/${entraConfig.tenantId}`,
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: "sessionStorage",
  },
}

export const msalInstance = new PublicClientApplication(config)

export const loginRequest = {
  scopes: ["openid", "profile", "email", entraConfig.apiScope],
}

export const apiTokenRequest = {
  scopes: [entraConfig.apiScope],
}