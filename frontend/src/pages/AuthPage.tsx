import {
  ShieldCheck,
  Lock,
  Database,
  MessageSquareText,
  Sparkles,
  ArrowRight,
  CheckCircle2,
} from "lucide-react"
import AuthButtons from "../components/AuthButtons"

export default function AuthPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-zinc-950 text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.08),transparent_30%),radial-gradient(circle_at_bottom_right,rgba(99,102,241,0.15),transparent_30%)]" />
      <div className="absolute inset-0 bg-[linear-gradient(to_bottom,rgba(24,24,27,0.25),rgba(9,9,11,0.92))]" />

      <div className="relative mx-auto grid min-h-screen max-w-7xl grid-cols-1 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="flex flex-col justify-center p-8 lg:p-12 xl:p-16">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-zinc-300 backdrop-blur">
              <Sparkles className="h-3.5 w-3.5" />
              Plateforme RAG sécurisée
            </div>

            <h1 className="mt-8 text-4xl font-semibold tracking-tight text-white sm:text-5xl xl:text-6xl">
              Connecte-toi avec Microsoft pour accéder à ton espace RAG
            </h1>

            {/* <p className="mt-5 max-w-xl text-base leading-7 text-zinc-400 sm:text-lg">
              Retrouve tes conversations, tes documents privés et ton assistant
              RAG dans un espace sécurisé connecté à Microsoft Entra ID.
            </p> */}

            {/* <div className="mt-8 flex flex-wrap gap-3">
              <Pill label="Historique cloud" />
              <Pill label="Documents privés" />
              <Pill label="Authentification Microsoft" />
              <Pill label="Sources RAG" />
            </div> */}

            <div className="mt-10 grid gap-4 sm:grid-cols-2">
              <FeatureCard
                icon={<ShieldCheck className="h-5 w-5" />}
                title="Accès sécurisé"
                description="Chaque utilisateur accède uniquement à ses conversations et à ses documents autorisés."
              />
              <FeatureCard
                icon={<Database className="h-5 w-5" />}
                title="Persistance cloud"
                description="Les échanges restent disponibles après reconnexion grâce au stockage côté backend."
              />
              <FeatureCard
                icon={<MessageSquareText className="h-5 w-5" />}
                title="Expérience fluide"
                description="Une interface pensée pour discuter naturellement avec tes connaissances métier."
              />
              <FeatureCard
                icon={<Lock className="h-5 w-5" />}
                title="Identité centralisée"
                description="Connexion via Microsoft Entra ID, sans gestion manuelle de mots de passe."
              />
            </div>

            {/* <div className="mt-10 rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur">
              <p className="text-sm font-medium text-zinc-200">
                Parcours utilisateur
              </p>
              <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-zinc-400">
                <Step label="Connexion" />
                <ArrowRight className="h-4 w-4 text-zinc-600" />
                <Step label="Chargement du profil" />
                <ArrowRight className="h-4 w-4 text-zinc-600" />
                <Step label="Historique" />
                <ArrowRight className="h-4 w-4 text-zinc-600" />
                <Step label="Chat RAG" />
              </div>
            </div> */}
          </div>
        </section>

        <section className="flex items-center justify-center p-8 lg:p-12 xl:p-16">
          <div className="w-full max-w-md">
            <div className="rounded-[32px] border border-white/10 bg-zinc-900/75 p-6 shadow-2xl shadow-black/40 backdrop-blur-xl">
              <div className="mb-6 flex items-center gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-zinc-950 shadow-lg shadow-white/10">
                  <ShieldCheck className="h-7 w-7" />
                </div>
                <div>
                  <p className="text-lg font-semibold text-white">
                    Connexion sécurisée
                  </p>
                  <p className="text-sm text-zinc-400">
                    Accède à ton espace conversationnel personnel
                  </p>
                </div>
              </div>


              <div className="mt-6 flex justify-center">
                <AuthButtons />
              </div>

              

              <p className="mt-5 text-center text-xs leading-6 text-zinc-500">
                En te connectant avec Microsoft, tu accèdes à ton espace
                personnel sécurisé et à ton historique conversationnel.
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
    <div className="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur">
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
    <span className="rounded-full border border-white/10 bg-zinc-950/80 px-3 py-1 text-zinc-300">
      {label}
    </span>
  )
}

function Pill({ label }: { label: string }) {
  return (
    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-sm text-zinc-300">
      {label}
    </span>
  )
}