import { useCallback, useEffect, useState } from "react"
import { api } from "../lib/api"

import type { DocumentItem } from "../types/documents"

export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [selectedDocument, setSelectedDocument] = useState<DocumentItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)

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
    async (file: File) => {
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
    //   const tempDoc: DocumentItem = {
    //     id: tempId,
    //     title: file.name,
    //     filename: file.name,
    //     status: "uploading",
    //     created_at: new Date().toISOString(),
    //   }

      setUploading(true)
      setDocuments((prev) => [tempDoc, ...prev])

      try {
        const formData = new FormData()
        formData.append("file", file)

        const res = await api.post("/documents/upload", formData, {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        })

        const realDoc = res.data.document

        setDocuments((prev) =>
          prev.map((doc) => (doc.id === tempId ? realDoc : doc))
        )

        if (realDoc?.id) {
          await loadDocument(realDoc.id)
        }
      } catch (error) {
        setDocuments((prev) =>
          prev.map((doc) =>
            doc.id === tempId ? { ...doc, status: "failed" } : doc
          )
        )
      } finally {
        setUploading(false)
      }
    },
    [loadDocument]
  )

  useEffect(() => {
    fetchDocuments()
  }, [fetchDocuments])

  useEffect(() => {
    const hasPending = documents.some((doc) =>
      ["uploading", "processing", "parsed", "chunked"].includes(doc.status || "")
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
    loadDocument,
    uploadDocument,
  }
}