import { useEffect, useMemo, useState } from "react"
import { api } from "../lib/api"
import type { ChatResponse, Conversation, Message } from "../types/chat"

export function useChat() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [input, setInput] = useState("")
  const [search, setSearch] = useState("")
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const loadConversations = async () => {
      try {
        const response = await api.get<Conversation[]>("/conversations")
        const data = response.data
        setConversations(data)
        setActiveConversationId(data[0]?.id ?? null)
      } catch (error) {
        console.error("Erreur chargement conversations", error)
      }
    }

    loadConversations()
  }, [])

  const activeConversation = useMemo(() => {
    return conversations.find((c) => c.id === activeConversationId) ?? null
  }, [conversations, activeConversationId])

  const filteredConversations = useMemo(() => {
    const value = search.trim().toLowerCase()
    if (!value) return conversations

    return conversations.filter((conversation) => {
      const inTitle = conversation.title.toLowerCase().includes(value)
      const inMessages = conversation.messages.some((message) =>
        message.content.toLowerCase().includes(value)
      )
      return inTitle || inMessages
    })
  }, [conversations, search])

  const createNewConversation = async () => {
    const response = await api.post<Conversation>("/conversations", {})
    const created = response.data
    setConversations((prev) => [created, ...prev])
    setActiveConversationId(created.id)
  }

  const selectConversation = async (id: string) => {
    const response = await api.get<Conversation>(`/conversations/${id}`)
    const updated = response.data

    setConversations((prev) => {
      const others = prev.filter((conv) => conv.id !== updated.id)
      return [updated, ...others]
    })
    setActiveConversationId(updated.id)
  }

  const deleteConversation = async (id: string) => {
    await api.delete(`/conversations/${id}`)

    setConversations((prev) => {
      const remaining = prev.filter((conv) => conv.id !== id)
      if (activeConversationId === id) {
        setActiveConversationId(remaining[0]?.id ?? null)
      }
      return remaining
    })
  }
  const sendMessage = async () => {
  const content = input.trim()
  if (!content || loading) return

  let conversationId = activeConversationId

  if (!conversationId) {
    try {
      const createdResponse = await api.post<Conversation>("/conversations", {})
      const createdConversation = createdResponse.data

      setConversations((prev) => [createdConversation, ...prev])
      setActiveConversationId(createdConversation.id)

      conversationId = createdConversation.id
    } catch (error) {
      console.error("Erreur création conversation", error)
      return
    }
  }

  const optimisticUserMessage: Message = {
    id: crypto.randomUUID(),
    role: "user",
    content,
  }

  setConversations((prev) =>
    prev.map((conv) =>
      conv.id === conversationId
        ? {
            ...conv,
            title:
              conv.title === "Nouvelle conversation"
                ? content.slice(0, 36)
                : conv.title,
            messages: [...conv.messages, optimisticUserMessage],
          }
        : conv
    )
  )

  setInput("")
  setLoading(true)

  try {
    const response = await api.post<ChatResponse>("/chat", {
      message: content,
      conversation_id: conversationId,
    })

    const refreshed = await api.get<Conversation>(
      `/conversations/${response.data.conversation_id}`
    )

    const updatedConversation = refreshed.data

    setConversations((prev) => {
      const others = prev.filter((conv) => conv.id !== updatedConversation.id)
      return [updatedConversation, ...others]
    })

    setActiveConversationId(updatedConversation.id)
  } catch (error) {
    console.error("Erreur envoi message", error)
  } finally {
    setLoading(false)
  }
}
  

  return {
    conversations: filteredConversations,
    activeConversation,
    activeConversationId,
    input,
    setInput,
    loading,
    search,
    setSearch,
    createNewConversation,
    selectConversation,
    deleteConversation,
    sendMessage,
  }
}