type TopbarProps = {
  title?: string
}

export default function Topbar({ title = "RAG Chat UI" }: TopbarProps) {
  return (
    <header className="border-b border-zinc-800 bg-zinc-950/90 px-6 py-4 backdrop-blur">
      <h1 className="text-sm font-semibold text-white">{title}</h1>
      <p className="text-xs text-zinc-400">
        Interface conversationnelle style ChatGPT
      </p>
    </header>
  )
}