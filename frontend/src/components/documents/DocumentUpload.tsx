import { useRef, useState } from "react"

type Props = {
  onUpload: (file: File) => Promise<void>
}

export default function DocumentUpload({ onUpload }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [dragging, setDragging] = useState(false)

  const handlePick = () => {
    inputRef.current?.click()
  }

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return

    for (const file of Array.from(files)) {
      await onUpload(file)
    }
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={async (e) => {
        e.preventDefault()
        setDragging(false)
        await handleFiles(e.dataTransfer.files)
      }}
      className={`rounded-3xl border border-dashed p-6 transition ${
        dragging
          ? "border-white bg-zinc-800"
          : "border-zinc-700 bg-zinc-900"
      }`}
    >
      <div className="flex flex-col items-center justify-center gap-3 text-center">
        <div className="text-sm text-zinc-300">
          Glisse-dépose tes fichiers ici
        </div>

        <div className="text-xs text-zinc-500">
          Formats recommandés : .txt, .md, .markdown, .pdf
        </div>

        <button
          onClick={handlePick}
          className="rounded-xl bg-white px-4 py-2 text-sm font-medium text-black"
        >
          Choisir un fichier
        </button>

        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".txt,.md,.markdown,.pdf"
          className="hidden"
          onChange={async (e) => {
            await handleFiles(e.target.files)
            e.target.value = ""
          }}
        />
      </div>
    </div>
  )
}