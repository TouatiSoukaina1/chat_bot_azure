import axios from "axios"
import { msalInstance, apiTokenRequest } from "../auth/msal"
import { entraConfig } from "../auth/config"

export const api = axios.create({
  baseURL: entraConfig.apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
})

api.interceptors.request.use(async (config) => {
  const account =
    msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0]

  if (!account) {
    console.error("Aucun compte actif MSAL")
    return config
  }

  try {
    const tokenResponse = await msalInstance.acquireTokenSilent({
      ...apiTokenRequest,
      account,
    })

    console.log("Access token acquired")
    console.log("audience scope demandée:", apiTokenRequest.scopes)

    config.headers = config.headers ?? {}
    config.headers.Authorization = `Bearer ${tokenResponse.accessToken}`

    return config
  } catch (error) {
    console.error("Erreur acquireTokenSilent:", error)
    return config
  }
})