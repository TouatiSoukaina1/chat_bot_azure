import {
  ShieldCheck,
  Lock,
  Database,
  MessageSquareText,
  Sparkles,
  ArrowRight,
} from "lucide-react"
import AuthButtons from "../components/AuthButtons"

export default function AuthPage() {
  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      <div className="mx-auto grid min-h-screen max-w-7xl grid-cols-1 lg:grid-cols-2">
        <section className="flex flex-col justify-between border-b border-zinc-800 p-8 lg:border-b-0 lg:border-r lg:p-12 xl:p-16">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/70 px-3 py-1 text-xs text-zinc-300">
              <Sparkles className="h-3.5 w-3.5" />
              RAG Chat Platform
            </div>

            <div className="mt-10 max-w-xl">
              <h1 className="text-4xl font-semibold tracking-tight text-white sm:text-5xl">
                Connecte-toi pour accéder à ton espace RAG sécurisé
              </h1>
              <p className="mt-5 text-base leading-7 text-zinc-400 sm:text-lg">
                Interface conversationnelle multi-utilisateurs avec historique
                cloud, sources documentaires et authentification Microsoft Entra
                ID.
              </p>
            </div>

            <div className="mt-10 grid gap-4 sm:grid-cols-2">
              <FeatureCard
                icon={<ShieldCheck className="h-5 w-5" />}
                title="Accès sécurisé"
                description="Chaque utilisateur retrouve uniquement ses conversations et ses documents autorisés."
              />
              <FeatureCard
                icon={<Database className="h-5 w-5" />}
                title="Historique cloud"
                description="Les conversations sont persistées côté backend pour rester disponibles après reconnexion."
              />
              <FeatureCard
                icon={<MessageSquareText className="h-5 w-5" />}
                title="Expérience chat"
                description="Une interface inspirée de ChatGPT, pensée pour un usage RAG simple et fluide."
              />
              <FeatureCard
                icon={<Lock className="h-5 w-5" />}
                title="Identité centralisée"
                description="Authentification avec Microsoft Entra ID, sans gestion manuelle de mots de passe."
              />
            </div>
          </div>

          <div className="mt-12 rounded-3xl border border-zinc-800 bg-zinc-900/60 p-5">
            <p className="text-sm font-medium text-zinc-200">Flux utilisateur</p>
            <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-zinc-400">
              <Step label="Connexion" />
              <ArrowRight className="h-4 w-4 text-zinc-600" />
              <Step label="Chargement du profil" />
              <ArrowRight className="h-4 w-4 text-zinc-600" />
              <Step label="Récupération historique" />
              <ArrowRight className="h-4 w-4 text-zinc-600" />
              <Step label="Chat RAG" />
            </div>
          </div>
        </section>

        <section className="flex items-center justify-center p-8 lg:p-12 xl:p-16">
          <div className="w-full max-w-md">
            <div className="rounded-[32px] border border-zinc-800 bg-zinc-900/80 p-6 shadow-2xl shadow-black/30 backdrop-blur">
              <div className="mb-6 flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-zinc-900">
                  <ShieldCheck className="h-6 w-6" />
                </div>
                <div>
                  <p className="text-lg font-semibold text-white">
                    Authentification
                  </p>
                  <p className="text-sm text-zinc-400">
                    Connexion à l’espace conversationnel
                  </p>
                </div>
              </div>

              <div className="space-y-4">
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-4">
                  <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-zinc-500">
                    Organisation
                  </label>
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm text-zinc-300">
                    Tenant Microsoft Entra ID
                  </div>
                </div>

                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-4">
                  <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-zinc-500">
                    Type d’accès
                  </label>
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm text-zinc-300">
                    Utilisateur standard • Scope API RAG
                  </div>
                </div>
              </div>

              <div className="mt-6 flex justify-center">
                <AuthButtons />
              </div>

              <div className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-950/70 p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Ce qui se passe après connexion
                </p>
                <ul className="mt-3 space-y-2 text-sm text-zinc-400">
                  <li>• récupération de l’identité utilisateur</li>
                  <li>• chargement des conversations depuis Cosmos DB</li>
                  <li>• filtrage des données par utilisateur</li>
                  <li>• accès au chat RAG et aux sources</li>
                </ul>
              </div>

              <p className="mt-5 text-center text-xs leading-6 text-zinc-500">
                En te connectant, tu accèdes à ton historique personnel et à tes
                conversations sécurisées.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode
  title: string
  description: string
}) {
  return (
    <div className="rounded-3xl border border-zinc-800 bg-zinc-900/60 p-5">
      <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-zinc-800 text-zinc-100">
        {icon}
      </div>
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-zinc-400">{description}</p>
    </div>
  )
}

function Step({ label }: { label: string }) {
  return (
    <span className="rounded-full border border-zinc-800 bg-zinc-950 px-3 py-1 text-zinc-300">
      {label}
    </span>
  )
}