import type { DocumentItem } from "../../types/documents"

type Props = {
  documents: DocumentItem[]
  onRemove: (id: string) => void
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function statusBadge(status: DocumentItem["status"]) {
  switch (status) {
    case "uploading":
      return "bg-blue-600/20 text-blue-300 border-blue-500/30"
    case "processing":
      return "bg-violet-600/20 text-violet-300 border-violet-500/30"
    case "ready":
      return "bg-green-600/20 text-green-300 border-green-500/30"
    case "failed":
      return "bg-red-600/20 text-red-300 border-red-500/30"
    default:
      return "bg-zinc-700/20 text-zinc-300 border-zinc-600/30"
  }
}

export default function DocumentList({ documents, onRemove }: Props) {
  if (documents.length === 0) {
    return (
      <div className="rounded-3xl border border-zinc-800 bg-zinc-900 p-6 text-sm text-zinc-400">
        Aucun document pour le moment.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {documents.map((doc) => (
        <div
          key={doc.id}
          className="rounded-3xl border border-zinc-800 bg-zinc-900 p-4"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-white">
                {doc.filename}
              </p>
              <p className="mt-1 text-xs text-zinc-400">
                {doc.fileType.toUpperCase()} • {formatSize(doc.fileSize)}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span
                className={`rounded-full border px-3 py-1 text-xs ${statusBadge(doc.status)}`}
              >
                {doc.status}
              </span>

              <button
                onClick={() => onRemove(doc.id)}
                className="rounded-lg px-2 py-1 text-xs text-zinc-400 hover:bg-zinc-800 hover:text-white"
              >
                Supprimer
              </button>
            </div>
          </div>

          {doc.error ? (
            <p className="mt-3 text-xs text-red-400">{doc.error}</p>
          ) : null}
        </div>
      ))}
    </div>
  )
}