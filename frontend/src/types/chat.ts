export type SourceItem = {
  title: string
  excerpt: string
}

export type Message = {
  id: string
  role: "user" | "assistant"
  content: string
  sources?: SourceItem[]
  createdAt?: string
}

export type Conversation = {
  id: string
  title: string
  messages: Message[]
  createdAt: string
  updatedAt: string
}

export type ChatRequest = {
  message: string
  conversation_id?: string
}

export type ChatResponse = {
  answer: string
  conversation_id: string
  sources: SourceItem[]
}