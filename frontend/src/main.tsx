import React from "react"
import ReactDOM from "react-dom/client"
import { MsalProvider } from "@azure/msal-react"

import App from "./App"
import "./index.css"
import { msalInstance } from "./auth/msal"

async function bootstrap() {
  await msalInstance.initialize()

  const redirectResult = await msalInstance.handleRedirectPromise()

  if (redirectResult?.account) {
    msalInstance.setActiveAccount(redirectResult.account)
    window.history.replaceState({}, document.title, window.location.pathname)
  } else {
    const accounts = msalInstance.getAllAccounts()
    if (accounts.length > 0) {
      msalInstance.setActiveAccount(accounts[0])
    }
  }

  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <MsalProvider instance={msalInstance}>
        <App />
      </MsalProvider>
    </React.StrictMode>
  )
}

bootstrap()