import DocumentDetails from "../components/documents/DocumentDetails"
import DocumentList from "../components/documents/DocumentList"
import DocumentUpload from "../components/documents/DocumentUpload"
import { useDocuments } from "../hooks/useDocuments"

function feedbackClass(type?: string | null) {
  switch (type) {
    case "success":
      return "border border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
    case "error":
      return "border border-red-500/30 bg-red-500/10 text-red-300"
    case "info":
    default:
      return "border border-blue-500/30 bg-blue-500/10 text-blue-300"
  }
}

export default function DocumentsPage() {
  const {
    documents,
    selectedDocument,
    loading,
    uploading,
    feedbackMessage,
    feedbackType,
    clearFeedback,
    loadDocument,
    uploadDocument,
    deleteDocument,
  } = useDocuments()

  return (
    <div className="min-h-screen bg-zinc-950 p-6 text-white">
      <div className="mx-auto max-w-6xl space-y-6">
        <div>
          <h1 className="text-2xl font-semibold">Mes documents</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Consulte les documents privés disponibles dans ton espace.
          </p>
        </div>

        <div className="max-w-3xl">
          <DocumentUpload onUpload={uploadDocument} uploading={uploading} />
        </div>

        {feedbackMessage && (
          <div
            className={`flex items-start justify-between gap-4 rounded-2xl px-4 py-3 text-sm ${feedbackClass(
              feedbackType
            )}`}
          >
            <span>{feedbackMessage}</span>

            <button
              type="button"
              onClick={clearFeedback}
              className="shrink-0 text-xs opacity-80 transition hover:opacity-100"
            >
              Fermer
            </button>
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
          <div>
            {loading ? (
              <div className="rounded-3xl border border-zinc-800 bg-zinc-900 p-6 text-sm text-zinc-400">
                Chargement...
              </div>
            ) : (
              <DocumentList
                documents={documents}
                onSelect={loadDocument}
                onDelete={deleteDocument}
              />
            )}
          </div>

          <div>
            <DocumentDetails document={selectedDocument} />
          </div>
        </div>
      </div>
    </div>
  )
}