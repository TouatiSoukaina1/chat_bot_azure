import type { DocumentItem } from "../../types/documents"

type Props = {
  document: DocumentItem | null
}

function formatStatus(status?: string) {
  switch (status) {
    case "uploading":
      return "Upload..."
    case "processing":
      return "Traitement..."
    case "parsed":
      return "Texte extrait"
    case "chunked":
      return "Chunké"
    case "ready":
      return "Prêt"
    case "failed":
      return "Erreur"
    case "deleting":
      return "Suppression..."
    default:
      return status || "Inconnu"
  }
}

function formatChunkMode(mode?: string) {
  switch (mode) {
    case "auto":
      return "Automatique"
    case "markdown":
      return "Sections Markdown"
    case "fixed":
      return "Taille fixe"
    default:
      return mode || "Non défini"
  }
}

function chunkStatusClass(status?: string) {
  switch (status) {
    case "indexed":
      return "border border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
    case "chunked":
      return "border border-amber-500/30 bg-amber-500/10 text-amber-300"
    case "embedding_failed":
    case "index_failed":
    case "failed":
      return "border border-red-500/30 bg-red-500/10 text-red-300"
    default:
      return "border border-zinc-700 bg-zinc-800 text-zinc-300"
  }
}

export default function DocumentDetails({ document }: Props) {
  if (!document) {
    return (
      <div className="rounded-3xl border border-zinc-800 bg-zinc-900 p-6 text-sm text-zinc-400">
        Sélectionne un document pour voir son contenu.
      </div>
    )
  }

  const requestedMode =
  document.chunking_config?.requested_mode ||
  document.chunking_config?.mode

  const effectiveMode =
    document.chunking_config?.effective_mode ||
    document.chunking_config?.requested_mode ||
    document.chunking_config?.mode

  const showFixedValues =
    requestedMode === "fixed" || effectiveMode === "fixed"

  return (
    <div className="rounded-3xl border border-zinc-800 bg-zinc-900 p-6">
      <div className="mb-6 space-y-2">
        <h2 className="text-xl font-semibold text-white">
          {document.title || document.filename || "Document sans titre"}
        </h2>

        <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
          <span className="rounded-full border border-zinc-700 bg-zinc-800 px-2.5 py-1">
            {formatStatus(document.status)}
          </span>

          {document.file_type && (
            <span className="rounded-full border border-zinc-700 bg-zinc-800 px-2.5 py-1">
              {document.file_type.toUpperCase()}
            </span>
          )}
        </div>
      </div>

      {document.chunking_config && (
        <div className="mb-6 rounded-2xl border border-zinc-800 bg-zinc-950/70 p-4">
          <h3 className="mb-3 text-sm font-medium text-white">
            Configuration du chunking
          </h3>

          <div className="grid gap-3 sm:grid-cols-5">
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900 px-4 py-3">
              <p className="text-[11px] uppercase tracking-wide text-zinc-500">
                Mode demandé
              </p>
              <p className="mt-1 text-sm text-white">
                {formatChunkMode(requestedMode)}
              </p>
            </div>

            <div className="rounded-2xl border border-zinc-800 bg-zinc-900 px-4 py-3">
              <p className="text-[11px] uppercase tracking-wide text-zinc-500">
                Mode effectif
              </p>
              <p className="mt-1 text-sm text-white">
                {formatChunkMode(effectiveMode)}
              </p>
            </div>

            <div className="rounded-2xl border border-zinc-800 bg-zinc-900 px-4 py-3">
              <p className="text-[11px] uppercase tracking-wide text-zinc-500">
                Taille de chunk
              </p>
              <p className="mt-1 text-sm text-white">
                {showFixedValues ? (document.chunking_config.chunk_size ?? "—") : "—"}
              </p>
            </div>

            <div className="rounded-2xl border border-zinc-800 bg-zinc-900 px-4 py-3">
              <p className="text-[11px] uppercase tracking-wide text-zinc-500">
                Overlap
              </p>
              <p className="mt-1 text-sm text-white">
                {showFixedValues ? (document.chunking_config.overlap ?? "—") : "—"}
              </p>
            </div>

            <div className="rounded-2xl border border-zinc-800 bg-zinc-900 px-4 py-3">
              <p className="text-[11px] uppercase tracking-wide text-zinc-500">
                Nombre de chunks
              </p>
              <p className="mt-1 text-sm text-white">
                {document.chunk_count ?? "—"}
              </p>
            </div>
          </div>
        </div>
      )}

      {document.document_chunks && document.document_chunks.length > 0 && (
        <div className="mb-6 rounded-2xl border border-zinc-800 bg-zinc-950/70 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-medium text-white">Chunks générés</h3>
            <span className="text-xs text-zinc-500">
              {document.document_chunks.length} chunk(s)
            </span>
          </div>

          <div className="max-h-[360px] space-y-3 overflow-auto pr-1">
            {document.document_chunks.map((chunk, index) => (
              <div
                key={chunk.id}
                className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4"
              >
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-zinc-700 bg-zinc-800 px-2.5 py-1 text-[11px] text-zinc-300">
                      Chunk {chunk.order ?? index}
                    </span>

                    {chunk.section_title && (
                      <span className="rounded-full border border-zinc-700 bg-zinc-800 px-2.5 py-1 text-[11px] text-zinc-300">
                        {chunk.section_title}
                      </span>
                    )}
                  </div>

                  <span
                    className={`rounded-full px-2.5 py-1 text-[11px] ${chunkStatusClass(chunk.status)}`}
                  >
                    {chunk.status || "inconnu"}
                  </span>
                </div>

                <pre className="whitespace-pre-wrap break-words text-xs leading-6 text-zinc-300">
                  {(chunk.content || "").slice(0, 500)}
                  {(chunk.content || "").length > 500 ? "..." : ""}
                </pre>
              </div>
            ))}
          </div>
        </div>
      )}

      {document.last_error && (
        <div className="mb-6 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {document.last_error}
        </div>
      )}

      <div className="space-y-3">
        <h3 className="text-sm font-medium text-white">Contenu</h3>

        <div className="max-h-[600px] overflow-auto rounded-2xl border border-zinc-800 bg-zinc-950/70 p-4">
          <pre className="whitespace-pre-wrap break-words text-sm leading-6 text-zinc-200">
            {document.text_content || "Aucun contenu disponible."}
          </pre>
        </div>
      </div>
    </div>
  )
}