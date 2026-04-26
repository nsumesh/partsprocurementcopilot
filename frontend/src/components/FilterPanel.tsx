import type { FitmentConfidence } from "../types"

export interface FilterState {
  minPrice: string
  maxPrice: string
  minYear: string
  maxYear: string
  sources: string[]
  confidences: string[]
}

export const DEFAULT_FILTERS: FilterState = {
  minPrice: "",
  maxPrice: "",
  minYear: "",
  maxYear: "",
  sources: [],
  confidences: [],
}

interface Props {
  filters: FilterState
  onChange: (f: FilterState) => void
  total: number
  showing: number
}

const CONFIDENCES: FitmentConfidence[] = [
  "High Probability",
  "Medium Probability",
  "Low Probability",
  "No Fitment",
]

const CONF_DOT: Record<FitmentConfidence, string> = {
  "High Probability":   "bg-green-500",
  "Medium Probability": "bg-yellow-500",
  "Low Probability":    "bg-amber-500",
  "No Fitment":         "bg-red-500",
}

function toggle(arr: string[], val: string): string[] {
  return arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val]
}

export default function FilterPanel({ filters, onChange, total, showing }: Props) {
  const hasFilters =
    filters.minPrice || filters.maxPrice || filters.minYear || filters.maxYear ||
    filters.sources.length > 0 || filters.confidences.length > 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold text-zinc-500 uppercase tracking-widest">Filters</span>
        {hasFilters && (
          <button
            onClick={() => onChange(DEFAULT_FILTERS)}
            className="text-xs text-orange-500 hover:text-orange-400 font-semibold transition-colors"
          >
            Clear all
          </button>
        )}
      </div>

      {hasFilters && showing < total && (
        <p className="text-xs text-zinc-400 bg-zinc-800 rounded-lg px-3 py-2 border border-zinc-700">
          Showing <span className="font-bold text-white">{showing}</span> of{" "}
          <span className="font-bold text-white">{total}</span> parts
        </p>
      )}

      {/* Source */}
      <section>
        <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-3">Source</h3>
        <div className="space-y-3">
          {(["OE", "aftermarket"] as const).map(src => (
            <label key={src} className="flex items-center gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={filters.sources.includes(src)}
                onChange={() => onChange({ ...filters, sources: toggle(filters.sources, src) })}
                className="w-4 h-4 rounded border-zinc-600 bg-zinc-800 accent-orange-500 cursor-pointer"
              />
              <span className="flex-1 text-sm text-zinc-300 group-hover:text-white transition-colors font-medium">
                {src === "OE" ? "OEM" : "Aftermarket"}
              </span>
              <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${
                src === "OE"
                  ? "bg-blue-500/15 text-blue-400"
                  : "bg-violet-500/15 text-violet-400"
              }`}>
                {src}
              </span>
            </label>
          ))}
        </div>
      </section>

      {/* Fitment */}
      <section>
        <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-3">Fitment</h3>
        <div className="space-y-3">
          {CONFIDENCES.map(c => (
            <label key={c} className="flex items-center gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={filters.confidences.includes(c)}
                onChange={() => onChange({ ...filters, confidences: toggle(filters.confidences, c) })}
                className="w-4 h-4 rounded border-zinc-600 bg-zinc-800 accent-orange-500 cursor-pointer"
              />
              <span className="flex items-center gap-2 flex-1">
                <span className={`w-2 h-2 rounded-full shrink-0 ${CONF_DOT[c]}`} />
                <span className="text-sm text-zinc-300 group-hover:text-white transition-colors font-medium">
                  {c.replace(" Probability", "")}
                </span>
              </span>
            </label>
          ))}
        </div>
      </section>

      {/* Price */}
      <section>
        <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-3">Price (USD)</h3>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={0}
            placeholder="Min"
            value={filters.minPrice}
            onChange={e => onChange({ ...filters, minPrice: e.target.value })}
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-orange-500 focus:border-orange-500 transition-shadow"
          />
          <span className="text-zinc-600 text-sm shrink-0">–</span>
          <input
            type="number"
            min={0}
            placeholder="Max"
            value={filters.maxPrice}
            onChange={e => onChange({ ...filters, maxPrice: e.target.value })}
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-orange-500 focus:border-orange-500 transition-shadow"
          />
        </div>
      </section>

      {/* Year range */}
      <section>
        <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-3">Year Range</h3>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={1990}
            max={2030}
            placeholder="From"
            value={filters.minYear}
            onChange={e => onChange({ ...filters, minYear: e.target.value })}
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-orange-500 focus:border-orange-500 transition-shadow"
          />
          <span className="text-zinc-600 text-sm shrink-0">–</span>
          <input
            type="number"
            min={1990}
            max={2030}
            placeholder="To"
            value={filters.maxYear}
            onChange={e => onChange({ ...filters, maxYear: e.target.value })}
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-orange-500 focus:border-orange-500 transition-shadow"
          />
        </div>
        <p className="text-xs text-zinc-600 mt-2">Parts without year data are always shown</p>
      </section>
    </div>
  )
}
