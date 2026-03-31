import { useEffect, useState } from "react"
import { api } from "../lib/api"
import type { DocumentItem } from "../types/documents"

function mapBackendDocument(doc: any): DocumentItem {
  return {
    id: doc.id,
    filename: doc.filename,
    fileType: doc.file_type,
    fileSize: doc.file_size ?? 0,
    uploadedAt: doc.created_at,
    status:
      doc.status === "ready"
        ? "ready"
        : doc.status === "failed"
        ? "failed"
        : doc.status === "processing"
        ? "processing"
        : doc.status === "parsed" || doc.status === "chunked" || doc.status === "indexed"
        ? "processing"
        : "idle",
    error: doc.last_error ?? null,
  }
}

export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentItem[]>([])

  const loadDocuments = async () => {
    try {
      const response = await api.get("/documents")
      setDocuments(response.data.map(mapBackendDocument))
    } catch (error) {
      console.error("Erreur chargement documents:", error)
    }
  }

  const uploadDocument = async (file: File) => {
    const tempId = crypto.randomUUID()

    setDocuments((prev) => [
      {
        id: tempId,
        filename: file.name,
        fileType: file.name.split(".").pop()?.toLowerCase() || "file",
        fileSize: file.size,
        uploadedAt: new Date().toISOString(),
        status: "uploading",
      },
      ...prev,
    ])

    try {
      const formData = new FormData()
      formData.append("file", file)

      await api.post("/documents/upload", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      })

      await loadDocuments()
    } catch (error) {
      console.error("Erreur upload document:", error)

      setDocuments((prev) =>
        prev.map((doc) =>
          doc.id === tempId
            ? {
                ...doc,
                status: "failed",
                error: error instanceof Error ? error.message : "Erreur inconnue",
              }
            : doc
        )
      )
    }
  }

  const removeDocument = (id: string) => {
    setDocuments((prev) => prev.filter((doc) => doc.id !== id))
  }

  useEffect(() => {
    loadDocuments()
  }, [])

  return {
    documents,
    uploadDocument,
    removeDocument,
    reloadDocuments: loadDocuments,
  }
}