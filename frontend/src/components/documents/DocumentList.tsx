import type { DocumentItem } from "../../types/documents"

type Props = {
  documents: DocumentItem[]
  onSelect: (documentId: string) => void | Promise<void>
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
    default:
      return "border border-zinc-700 bg-zinc-800 text-zinc-300"
  }
}

export default function DocumentList({ documents, onSelect }: Props) {
  if (!documents.length) {
    return (
      <div className="rounded-3xl border border-zinc-800 bg-zinc-900 p-6 text-sm text-zinc-400">
        Aucun document disponible.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {documents.map((doc) => (
        <button
          key={doc.id}
          onClick={() => onSelect(doc.id)}
          className="w-full rounded-3xl border border-zinc-800 bg-zinc-900 p-4 text-left transition hover:border-zinc-700 hover:bg-zinc-800"
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

            <span
              className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] ${getStatusClass(doc.status)}`}
            >
              {getStatusLabel(doc.status)}
            </span>
          </div>
        </button>
      ))}
    </div>
  )
}