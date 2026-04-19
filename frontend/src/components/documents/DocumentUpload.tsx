type Props = {
  onUpload: (file: File) => Promise<void>
  uploading?: boolean
}

export default function DocumentUpload({ onUpload, uploading = false }: Props) {
  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    await onUpload(file)
    e.target.value = ""
  }

  return (
    <label className="inline-flex cursor-pointer items-center gap-2 rounded-2xl border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-white hover:bg-zinc-800">
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
      {uploading ? "Upload en cours..." : "Ajouter un document"}
    </label>
  )
}