import { useState } from "react"
import {
  AuthenticatedTemplate,
  UnauthenticatedTemplate,
} from "@azure/msal-react"

import AuthPage from "./pages/AuthPage"
import DocumentsPage from "./pages/DocumentsPage"
import ChatInput from "./components/chat/ChatInput"
import ChatWindow from "./components/chat/ChatWindow"
import Sidebar from "./components/layout/Sidebar"
import Topbar from "./components/layout/Topbar"
import AuthButtons from "./components/AuthButtons"
import { useChat } from "./hooks/useChat"

function AuthenticatedApp() {
  const [view, setView] = useState<"chat" | "documents">("chat")

  const {
    conversations,
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
  } = useChat()

  if (view === "documents") {
    return (
      <div className="min-h-screen bg-zinc-950 text-white">
        <div className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setView("chat")}
              className="rounded-xl border border-zinc-700 px-3 py-2 text-sm"
            >
              Chat
            </button>
            <button
              onClick={() => setView("documents")}
              className="rounded-xl bg-white px-3 py-2 text-sm text-black"
            >
              Documents
            </button>
          </div>

          <AuthButtons />
        </div>

        <DocumentsPage />
      </div>
    )
  }

  return (
    <div className="flex h-screen bg-zinc-950 text-white">
      <Sidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        search={search}
        onSearchChange={setSearch}
        onNewConversation={createNewConversation}
        onSelectConversation={selectConversation}
        onDeleteConversation={deleteConversation}
      />

      <main className="flex flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
          <div className="flex items-center gap-3">
            <Topbar title={activeConversation?.title ?? "RAG Chat UI"} />
            <button
              onClick={() => setView("chat")}
              className="rounded-xl bg-white px-3 py-2 text-sm text-black"
            >
              Chat
            </button>
            <button
              onClick={() => setView("documents")}
              className="rounded-xl border border-zinc-700 px-3 py-2 text-sm"
            >
              Documents
            </button>
          </div>

          <AuthButtons />
        </div>

        <ChatWindow conversation={activeConversation} loading={loading} />

        <ChatInput
          value={input}
          onChange={setInput}
          onSend={sendMessage}
          disabled={loading}
        />
      </main>
    </div>
  )
}

export default function App() {
  return (
    <>
      <UnauthenticatedTemplate>
        <AuthPage />
      </UnauthenticatedTemplate>

      <AuthenticatedTemplate>
        <AuthenticatedApp />
      </AuthenticatedTemplate>
    </>
  )
}