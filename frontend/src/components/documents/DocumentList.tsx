import type { DocumentItem } from "../../types/documents"

type Props = {
  documents: DocumentItem[]
  onSelect: (documentId: string) => void | Promise<void>
  onDelete: (documentId: string) => void | Promise<void>
}

function getStatusLabel(status?: string) {
  switch (status) {
    case "uploading":
      return "Upload..."
    case "processing":
      return "Traitement..."
    case "parsed":
      return "Texte extrait"
    case "chunked":
      return "Indexation..."
    case "ready":
      return "Prêt"
    case "failed":
      return "Erreur"
    case "deleting":
      return "Suppression..."
    default:
      return "Inconnu"
  }
}

function getStatusClass(status?: string) {
  switch (status) {
    case "uploading":
    case "processing":
    case "parsed":
    case "chunked":
      return "border border-amber-500/30 bg-amber-500/10 text-amber-300"
    case "ready":
      return "border border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
    case "failed":
      return "border border-red-500/30 bg-red-500/10 text-red-300"
    case "deleting":
      return "border border-orange-500/30 bg-orange-500/10 text-orange-300"
    default:
      return "border border-zinc-700 bg-zinc-800 text-zinc-300"
  }
}

export default function DocumentList({ documents, onSelect, onDelete }: Props) {
  if (!documents.length) {
    return (
      <div className="rounded-3xl border border-zinc-800 bg-zinc-900 p-6 text-sm text-zinc-400">
        Aucun document disponible.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {documents.map((doc) => {
        const isDeleting = doc.status === "deleting"

        return (
          <button
            key={doc.id}
            type="button"
            disabled={isDeleting}
            onClick={() => {
              if (!isDeleting) {
                onSelect(doc.id)
              }
            }}
            className={`w-full rounded-3xl border border-zinc-800 bg-zinc-900 p-4 text-left transition ${
              isDeleting
                ? "cursor-not-allowed opacity-70"
                : "hover:border-zinc-700 hover:bg-zinc-800"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-white">
                  {doc.title || doc.filename || "Document sans titre"}
                </p>
                <p className="mt-1 truncate text-xs text-zinc-400">
                  {doc.filename}
                </p>
              </div>

              <div className="flex shrink-0 items-center gap-2">
                <span
                  className={`rounded-full px-2.5 py-1 text-[11px] ${getStatusClass(doc.status)}`}
                >
                  {getStatusLabel(doc.status)}
                </span>

                <span
                  onClick={(e) => {
                    e.stopPropagation()
                    if (!isDeleting) {
                      onDelete(doc.id)
                    }
                  }}
                  className={`rounded-xl px-2 py-1 text-xs ${
                    isDeleting
                      ? "cursor-not-allowed border border-zinc-700 text-zinc-500"
                      : "cursor-pointer border border-red-500/30 text-red-300 hover:bg-red-500/10"
                  }`}
                >
                  {isDeleting ? "Suppression..." : "Supprimer"}
                </span>
              </div>
            </div>
          </button>
        )
      })}
    </div>
  )
}