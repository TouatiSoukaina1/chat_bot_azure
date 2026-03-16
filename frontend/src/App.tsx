import {
  AuthenticatedTemplate,
  UnauthenticatedTemplate,
} from "@azure/msal-react"

import AuthPage from "./pages/AuthPage"
import ChatInput from "./components/chat/ChatInput"
import ChatWindow from "./components/chat/ChatWindow"
import Sidebar from "./components/layout/Sidebar"
import Topbar from "./components/layout/Topbar"
import AuthButtons from "./components/AuthButtons"
import { useChat } from "./hooks/useChat"

function AuthenticatedApp() {
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
          <Topbar title={activeConversation?.title ?? "RAG Chat UI"} />
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