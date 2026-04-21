import { useCallback, useEffect, useState } from "react"
import { api } from "../lib/api"
import type { DocumentItem } from "../types/documents"
import type { ChunkingOptions } from "../components/documents/DocumentUpload"

export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [selectedDocument, setSelectedDocument] = useState<DocumentItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)

  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null)
  const [feedbackType, setFeedbackType] = useState<"error" | "success" | "info" | null>(null)

  const showFeedback = useCallback(
    (message: string, type: "error" | "success" | "info" = "info") => {
      setFeedbackMessage(message)
      setFeedbackType(type)
    },
    []
  )

  const clearFeedback = useCallback(() => {
    setFeedbackMessage(null)
    setFeedbackType(null)
  }, [])

  const fetchDocuments = useCallback(async () => {
    const res = await api.get("/documents")
    setDocuments(res.data)
    setLoading(false)
  }, [])

  const loadDocument = useCallback(async (documentId: string) => {
    const res = await api.get(`/documents/${documentId}`)
    setSelectedDocument(res.data)
  }, [])

  const uploadDocument = useCallback(
    async (file: File, options: ChunkingOptions) => {
      const normalizedName = file.name.trim().toLowerCase()

      const alreadyExistsByName = documents.some(
        (doc) =>
          (doc.filename || "").trim().toLowerCase() === normalizedName &&
          doc.status !== "failed" &&
          doc.status !== "deleting"
      )

      if (alreadyExistsByName) {
        showFeedback(
          "Un document avec le même nom existe déjà dans votre espace.",
          "info"
        )
        return
      }

      const tempId = `temp-${Date.now()}`

      const tempDoc: DocumentItem = {
        id: tempId,
        title: file.name,
        filename: file.name,
        status: "uploading",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        text_content: "",
        owner_user_id: null,
        path: "",
        file_type: file.name.split(".").pop()?.toLowerCase() || "",
        scope: "private",
        source_type: "user_upload",
        kb: "user",
      }

      setUploading(true)
      clearFeedback()
      setDocuments((prev) => [tempDoc, ...prev])

      try {
        const formData = new FormData()
        formData.append("file", file)
        formData.append("chunk_mode", options.chunkMode)
        formData.append("chunk_size", String(options.chunkSize))
        formData.append("overlap", String(options.overlap))

        const res = await api.post("/documents/upload", formData, {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        })

        const realDoc = res.data.document

        setDocuments((prev) =>
          prev.map((doc) => (doc.id === tempId ? realDoc : doc))
        )

        showFeedback("Document ajouté avec succès.", "success")

        if (realDoc?.id) {
          await loadDocument(realDoc.id)
        }
      } catch (error: any) {
        const detail = error?.response?.data?.detail
        showFeedback(detail || "Échec de l'upload du document.", "error")

        setDocuments((prev) => prev.filter((doc) => doc.id !== tempId))
      } finally {
        setUploading(false)
      }
    },
    [documents, loadDocument, showFeedback, clearFeedback]
  )

  const deleteDocument = useCallback(
    async (documentId: string) => {
      const confirmed = window.confirm("Supprimer ce document ?")
      if (!confirmed) return

      const previousDocuments = documents
      const previousSelected = selectedDocument

      clearFeedback()

      setDocuments((prev) =>
        prev.map((doc) =>
          doc.id === documentId ? { ...doc, status: "deleting" } : doc
        )
      )

      setSelectedDocument((prev) =>
        prev?.id === documentId ? { ...prev, status: "deleting" } : prev
      )

      try {
        await api.delete(`/documents/${documentId}`)

        setDocuments((prev) => prev.filter((doc) => doc.id !== documentId))
        setSelectedDocument((prev) => (prev?.id === documentId ? null : prev))
        showFeedback("Document supprimé avec succès.", "success")
      } catch (error: any) {
        const detail = error?.response?.data?.detail

        setDocuments(previousDocuments)
        setSelectedDocument(previousSelected)
        showFeedback(detail || "Échec de la suppression du document.", "error")
      }
    },
    [documents, selectedDocument, showFeedback, clearFeedback]
  )

  useEffect(() => {
    fetchDocuments()
  }, [fetchDocuments])

  useEffect(() => {
    const hasPending = documents.some((doc) =>
      ["uploading", "processing", "parsed", "chunked", "deleting"].includes(doc.status || "")
    )

    if (!hasPending) return

    const interval = setInterval(() => {
      fetchDocuments()
    }, 3000)

    return () => clearInterval(interval)
  }, [documents, fetchDocuments])

  return {
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
  }
}