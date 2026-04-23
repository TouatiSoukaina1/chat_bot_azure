export type DocumentStatus =
  | "idle"
  | "uploading"
  | "processing"
  | "ready"
  | "failed"
  
export type DocumentItem = {
  id: string
  title: string
  filename: string
  status: string
  created_at?: string
  updated_at?: string
  text_content?: string | null

  owner_user_id?: string | null
  path?: string
  file_type?: string
  scope?: string
  source_type?: string
  kb?: string
  mime_type?: string | null
  file_size?: number
  last_error?: string | null
  file_hash?: string | null

  chunk_count?: number
  document_chunks?: Array<{
    id: string
    content?: string
    status?: string
    order?: number
    section_title?: string
    doc_title?: string
  }>

  chunking_config?: {
    mode?: "auto" | "markdown" | "fixed" | string
    requested_mode?: "auto" | "markdown" | "fixed" | string
    effective_mode?: "markdown" | "fixed" | string | null
    chunk_size?: number
    overlap?: number
  }
}