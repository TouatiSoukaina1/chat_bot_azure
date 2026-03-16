import { useEffect, useRef } from "react"
import type { Conversation } from "../../types/chat"
import ChatMessage from "./ChatMessage"

type ChatWindowProps = {
  conversation: Conversation | null
  loading: boolean
}

export default function ChatWindow({
  conversation,
  loading,
}: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [conversation?.messages.length, loading])

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        {conversation?.messages.length ? (
          conversation.messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))
        ) : (
          <div className="mt-20 text-center text-zinc-500">
            <p className="text-2xl font-semibold text-zinc-200">Bienvenue</p>
            <p className="mt-3 text-sm text-zinc-400">
              Pose une question à ton système RAG. Les réponses et leurs sources
              apparaîtront ici.
            </p>
          </div>
        )}

        {loading && (
          <div className="max-w-2xl rounded-3xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm text-zinc-300">
            Le backend réfléchit...
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}