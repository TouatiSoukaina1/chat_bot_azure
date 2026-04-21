import { useState } from "react"

export type ChunkMode = "auto" | "markdown" | "fixed"

export type ChunkingOptions = {
  chunkMode: ChunkMode
  chunkSize: number
  overlap: number
}

type Props = {
  onUpload: (file: File, options: ChunkingOptions) => Promise<void>
  uploading?: boolean
}

export default function DocumentUpload({
  onUpload,
  uploading = false,
}: Props) {
  const [chunkMode, setChunkMode] = useState<ChunkMode>("auto")
  const [chunkSize, setChunkSize] = useState(1500)
  const [overlap, setOverlap] = useState(150)

  const isChunkParamsDisabled = chunkMode === "markdown"

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    await onUpload(file, {
      chunkMode,
      chunkSize,
      overlap,
    })

    e.target.value = ""
  }

  return (
    <div className="rounded-3xl border border-zinc-800 bg-zinc-900/80 p-4">
      <div className="mb-4 flex flex-col gap-1">
        <p className="text-sm font-medium text-white">Ajouter un document</p>
        <p className="text-xs text-zinc-400">
          Choisis le mode de découpage avant l’indexation.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr_auto] lg:items-end">
        <div>
          <label className="mb-2 block text-xs font-medium text-zinc-300">
            Mode de chunking
          </label>
          <select
            value={chunkMode}
            onChange={(e) => setChunkMode(e.target.value as ChunkMode)}
            disabled={uploading}
            className="w-full rounded-2xl border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm text-white outline-none transition focus:border-zinc-500"
          >
            <option value="auto">Automatique</option>
            <option value="markdown">Par sections Markdown (#, ##, ###)</option>
            <option value="fixed">Par taille fixe</option>
          </select>

          <p className="mt-2 text-[11px] leading-relaxed text-zinc-500">
            {chunkMode === "auto" &&
              "Utilise les sections Markdown si elles existent, sinon applique la taille fixe."}
            {chunkMode === "markdown" &&
              "Découpage basé sur les titres Markdown. Les paramètres numériques ne sont pas utilisés."}
            {chunkMode === "fixed" &&
              "Découpage par taille fixe avec overlap entre les morceaux."}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-2 block text-xs font-medium text-zinc-300">
              Taille chunk
            </label>
            <input
              type="number"
              min={100}
              step={50}
              value={chunkSize}
              onChange={(e) => setChunkSize(Number(e.target.value))}
              disabled={uploading || isChunkParamsDisabled}
              className="w-full rounded-2xl border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm text-white outline-none transition focus:border-zinc-500 disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>

          <div>
            <label className="mb-2 block text-xs font-medium text-zinc-300">
              Overlap
            </label>
            <input
              type="number"
              min={0}
              step={10}
              value={overlap}
              onChange={(e) => setOverlap(Number(e.target.value))}
              disabled={uploading || isChunkParamsDisabled}
              className="w-full rounded-2xl border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm text-white outline-none transition focus:border-zinc-500 disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>
        </div>

        <div>
          <label
            className={`inline-flex w-full items-center justify-center gap-2 rounded-2xl border px-4 py-3 text-sm transition lg:min-w-[180px] ${
              uploading
                ? "cursor-not-allowed border-zinc-700 bg-zinc-800 text-zinc-400"
                : "cursor-pointer border-zinc-700 bg-zinc-950 text-white hover:bg-zinc-800"
            }`}
          >
            <input
              type="file"
              className="hidden"
              onChange={handleChange}
              disabled={uploading}
            />
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${
                uploading ? "animate-pulse bg-amber-400" : "bg-emerald-400"
              }`}
            />
            {uploading ? "Upload..." : "Choisir un fichier"}
          </label>
        </div>
      </div>
    </div>
  )
}