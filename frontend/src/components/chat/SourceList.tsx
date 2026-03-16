import type { SourceItem } from "../../types/chat"

type SourceListProps = {
  sources?: SourceItem[]
}

export default function SourceList({ sources = [] }: SourceListProps) {
  if (sources.length === 0) return null

  return (
    <div className="mt-3 space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
        Sources utilisées
      </p>

      {sources.map((source, index) => (
        <div
          key={`${source.title}-${index}`}
          className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-3"
        >
          <p className="mb-1 text-xs font-semibold text-zinc-300">
            {source.title}
          </p>
          <p className="text-xs leading-6 text-zinc-400">{source.excerpt}</p>
        </div>
      ))}
    </div>
  )
}