import { MessageSquare, Plus, Search, Trash2 } from "lucide-react"
import { formatDateLabel } from "../../lib/utils"
import type { Conversation } from "../../types/chat"

type SidebarProps = {
  conversations: Conversation[]
  activeConversationId: string | null
  search: string
  onSearchChange: (value: string) => void
  onNewConversation: () => void
  onSelectConversation: (id: string) => void
  onDeleteConversation: (id: string) => void
}

export default function Sidebar({
  conversations,
  activeConversationId,
  search,
  onSearchChange,
  onNewConversation,
  onSelectConversation,
  onDeleteConversation,
}: SidebarProps) {
  return (
    <aside className="flex w-80 flex-col border-r border-zinc-800 bg-zinc-900/95 p-4">
      <button
        onClick={onNewConversation}
        className="mb-4 flex items-center justify-center gap-2 rounded-2xl bg-white px-4 py-3 text-sm font-medium text-black"
      >
        <Plus size={16} />
        Nouvelle conversation
      </button>

      

      <div className="flex-1 space-y-2 overflow-y-auto pr-1">
        {conversations.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-zinc-800 p-4 text-sm text-zinc-500">
            Aucune conversation trouvée.
          </div>
        ) : (
          conversations.map((conv) => {
            const isActive = conv.id === activeConversationId

            return (
              <div
                key={conv.id}
                className={`group rounded-2xl border px-3 py-3 transition ${
                  isActive
                    ? "border-zinc-700 bg-zinc-800"
                    : "border-transparent hover:border-zinc-800 hover:bg-zinc-800/60"
                }`}
              >
                <div className="flex items-start gap-3">
                  <button
                    onClick={() => onSelectConversation(conv.id)}
                    className="flex min-w-0 flex-1 items-start gap-3 text-left"
                  >
                    <MessageSquare size={16} className="mt-0.5 shrink-0 text-zinc-400" />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-white">
                        {conv.title}
                      </p>
                      <p className="mt-1 text-xs text-zinc-500">
                        {formatDateLabel(conv.updatedAt)}
                      </p>
                    </div>
                  </button>

                  <button
                    onClick={() => onDeleteConversation(conv.id)}
                    className="rounded-xl p-2 text-zinc-500 opacity-0 transition hover:bg-zinc-700 hover:text-white group-hover:opacity-100"
                    aria-label="Supprimer la conversation"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            )
          })
        )}
      </div>
    </aside>
  )
}