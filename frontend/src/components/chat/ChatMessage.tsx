import ReactMarkdown from "react-markdown"
import type { Message } from "../../types/chat"
import SourceList from "./SourceList"

type ChatMessageProps = {
  message: Message
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user"

  return (
    <div className="w-full">
      <div
        className={`rounded-3xl px-4 py-3 text-sm leading-7 shadow-sm ${
          isUser
            ? "ml-auto max-w-2xl bg-white text-black"
            : "max-w-2xl border border-zinc-800 bg-zinc-900 text-white"
        }`}
      >
        {isUser ? (
          <div className="whitespace-pre-wrap">{message.content}</div>
        ) : (
          <div className="prose prose-invert max-w-none prose-p:my-2 prose-ul:my-2 prose-li:my-1 prose-strong:text-white">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}
      </div>

      {!isUser && <SourceList sources={message.sources} />}
    </div>
  )
}