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
  mime_type?: string
  file_size?: number
  last_error?: string | null
}