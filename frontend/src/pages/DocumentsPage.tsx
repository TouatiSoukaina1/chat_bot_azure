import DocumentList from "../components/documents/DocumentList"
import DocumentUpload from "../components/documents/DocumentUpload"
import { useDocuments } from "../hooks/useDocuments"

export default function DocumentsPage() {
  const { documents, uploadDocument, removeDocument } = useDocuments()

  return (
    <div className="flex min-h-screen bg-zinc-950 text-white">
      <main className="mx-auto w-full max-w-5xl p-6">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold">Mes documents</h1>
          <p className="mt-2 text-sm text-zinc-400">
            Ajoute des fichiers qui seront utilisés plus tard dans ton espace documentaire privé.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
          <div>
            <DocumentUpload onUpload={uploadDocument} />
          </div>

          <div>
            <DocumentList documents={documents} onRemove={removeDocument} />
          </div>
        </div>
      </main>
    </div>
  )
}