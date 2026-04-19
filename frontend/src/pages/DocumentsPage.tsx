import DocumentDetails from "../components/documents/DocumentDetails"
import DocumentList from "../components/documents/DocumentList"
import DocumentUpload from "../components/documents/DocumentUpload"
import { useDocuments } from "../hooks/useDocuments"

export default function DocumentsPage() {
  const {
    documents,
    selectedDocument,
    loading,
    uploading,
    loadDocument,
    uploadDocument,
  } = useDocuments()

  return (
    <div className="min-h-screen bg-zinc-950 p-6 text-white">
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Mes documents</h1>
            <p className="text-sm text-zinc-400">
              Consulte les documents privés disponibles dans ton espace.
            </p>
          </div>

          <DocumentUpload onUpload={uploadDocument} uploading={uploading} />
        </div>

        <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
          <div>
            {loading ? (
              <div className="rounded-3xl border border-zinc-800 bg-zinc-900 p-6 text-sm text-zinc-400">
                Chargement...
              </div>
            ) : (
              <DocumentList documents={documents} onSelect={loadDocument} />
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