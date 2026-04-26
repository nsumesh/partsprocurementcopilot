import type { FitmentConfidence, SearchResultPart } from "../types"

const CONF: Record<FitmentConfidence, { ring: string; dot: string; label: string }> = {
  "High Probability":   { ring: "bg-green-500/10 text-green-400 ring-green-500/25",  dot: "bg-green-500",  label: "High fit" },
  "Medium Probability": { ring: "bg-yellow-500/10 text-yellow-400 ring-yellow-500/25",dot: "bg-yellow-500", label: "Medium fit" },
  "Low Probability":    { ring: "bg-amber-500/10 text-amber-400 ring-amber-500/25",   dot: "bg-amber-500",  label: "Low fit" },
  "No Fitment":         { ring: "bg-red-500/10 text-red-400 ring-red-500/25",         dot: "bg-red-500",    label: "No fit" },
}

interface Props {
  result: SearchResultPart
  onClick: () => void
}

export default function PartCard({ result, onClick }: Props) {
  const { part, fitment } = result
  const conf = CONF[fitment.confidence]

  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-zinc-900 border border-zinc-800 rounded-2xl px-6 py-5 hover:border-orange-500/40 hover:bg-zinc-800/70 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-black/40 active:translate-y-0 transition-all duration-150 animate-fade-in group"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-lg font-bold text-white leading-snug group-hover:text-orange-400 transition-colors duration-100 truncate">
            {part.name}
          </p>
          <p className="text-xs font-mono text-zinc-500 mt-1 tracking-wider">{part.part_number}</p>
        </div>
        <div className="shrink-0 text-right">
          {part.price_usd != null ? (
            <span className="text-xl font-black text-orange-400 tabular-nums">
              ${part.price_usd.toFixed(2)}
            </span>
          ) : (
            <span className="text-sm text-zinc-700">—</span>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 mt-4">
        <span className={`px-2.5 py-1 rounded-lg text-xs font-bold ring-1 ring-inset ${
          part.source === "OE"
            ? "bg-blue-500/10 text-blue-400 ring-blue-500/25"
            : "bg-violet-500/10 text-violet-400 ring-violet-500/25"
        }`}>
          {part.source === "OE" ? "OEM" : "Aftermarket"}
        </span>
        <span className="px-2.5 py-1 rounded-lg text-xs font-semibold ring-1 ring-inset bg-zinc-800 text-zinc-400 ring-zinc-700">
          {part.category}
        </span>
        {part.brand && (
          <span className="px-2.5 py-1 rounded-lg text-xs font-semibold ring-1 ring-inset bg-zinc-800 text-zinc-500 ring-zinc-700">
            {part.brand}
          </span>
        )}
        <span className={`ml-auto flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold ring-1 ring-inset ${conf.ring}`}>
          <span className={`w-2 h-2 rounded-full shrink-0 ${conf.dot}`} />
          {conf.label}
        </span>
      </div>
    </button>
  )
}
