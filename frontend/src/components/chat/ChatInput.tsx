type ChatInputProps = {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  disabled?: boolean
}

export default function ChatInput({
  value,
  onChange,
  onSend,
  disabled = false,
}: ChatInputProps) {
  return (
    <div className="border-t border-zinc-800 bg-zinc-950 px-6 py-4">
      <div className="mx-auto flex max-w-3xl gap-3">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Pose une question sur tes documents..."
          disabled={disabled}
          className="min-h-[56px] flex-1 resize-none rounded-3xl border border-zinc-700 bg-zinc-900 px-4 py-4 text-sm text-white outline-none disabled:opacity-60"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault()
              onSend()
            }
          }}
        />
        <button
          onClick={onSend}
          disabled={disabled}
          className="rounded-3xl bg-white px-5 py-3 text-sm font-medium text-black disabled:cursor-not-allowed disabled:opacity-60"
        >
          Envoyer
        </button>
      </div>
    </div>
  )
}