export type DocumentStatus =
  | "idle"
  | "uploading"
  | "processing"
  | "ready"
  | "failed"

export type DocumentItem = {
  id: string
  filename: string
  fileType: string
  fileSize: number
  uploadedAt: string
  status: DocumentStatus
  error?: string | null
}