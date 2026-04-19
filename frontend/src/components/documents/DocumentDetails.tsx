import type { DocumentItem } from "../../types/documents"

type Props = {
  document: DocumentItem | null
}

export default function DocumentDetails({ document }: Props) {
  if (!document) {
    return (
      <div className="rounded-3xl border border-zinc-800 bg-zinc-900 p-6 text-sm text-zinc-400">
        Sélectionne un document pour voir son contenu.
      </div>
    )
  }

  return (
    <div className="rounded-3xl border border-zinc-800 bg-zinc-900 p-6">
      <div className="mb-4 border-b border-zinc-800 pb-4">
        <h2 className="text-lg font-semibold text-white">
          {document.title || document.filename}
        </h2>
        <p className="mt-1 text-xs text-zinc-400">
          {document.file_type?.toUpperCase()} • {document.status} • {document.scope}
        </p>
      </div>

      <pre className="whitespace-pre-wrap text-sm text-zinc-200">
        {document.text_content || "Aucun contenu extrait"}
      </pre>
    </div>
  )
}