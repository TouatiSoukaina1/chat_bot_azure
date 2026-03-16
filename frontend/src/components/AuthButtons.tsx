import { useIsAuthenticated, useMsal } from "@azure/msal-react"
import { loginRequest } from "../auth/msal"

export default function AuthButtons() {
  const { instance, accounts } = useMsal()
  const isAuthenticated = useIsAuthenticated()

  const handleLogin = async () => {
    try {
      await instance.loginRedirect(loginRequest)
    } catch (error) {
      console.error("Erreur login Microsoft:", error)
    }
  }

  const handleLogout = async () => {
    await instance.logoutRedirect()
  }

  return (
    <div className="flex items-center gap-3">
      {isAuthenticated ? (
        <>
          <span className="text-sm text-zinc-400">
            {accounts[0]?.name ?? "Utilisateur connecté"}
          </span>
          <button
            onClick={handleLogout}
            className="rounded-xl border border-zinc-700 px-3 py-2 text-sm"
          >
            Se déconnecter
          </button>
        </>
      ) : (
        <button
          onClick={handleLogin}
          className="rounded-xl bg-white px-3 py-2 text-sm text-black"
        >
          Se connecter avec Microsoft
        </button>
      )}
    </div>
  )
}