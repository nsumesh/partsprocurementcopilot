import { useState } from "react"
import { decodeVin } from "../api/vin"
import type { VINSpec } from "../types"

interface Props {
  onSearch: (vin: string, query: string, urgency: "standard" | "urgent", urgency_deadline: string | null) => void
  isLoading: boolean
}

function minDeadline(): string {
  const d = new Date(Date.now() + 2 * 60 * 60 * 1000)
  return d.toISOString().slice(0, 16)
}

export default function SearchBar({ onSearch, isLoading }: Props) {
  const [vin, setVin] = useState("")
  const [query, setQuery] = useState("")
  const [urgency, setUrgency] = useState<"standard" | "urgent">("standard")
  const [urgencyDeadline, setUrgencyDeadline] = useState<string>("")
  const [vinSpec, setVinSpec] = useState<VINSpec | null>(null)
  const [vinChecking, setVinChecking] = useState(false)
  const [vinError, setVinError] = useState(false)

  async function handleVinBlur() {
    const v = vin.trim()
    if (v.length !== 17) return
    setVinChecking(true)
    setVinError(false)
    const spec = await decodeVin(v)
    const label = spec ? [spec.year, spec.make, spec.model].filter(Boolean).join(" ") : ""
    if (!spec || !label) {
      setVinSpec(null)
      setVinError(true)
    } else {
      setVinSpec(spec)
    }
    setVinChecking(false)
  }

  function handleSetUrgent() {
    setUrgency("urgent")
    if (!urgencyDeadline) setUrgencyDeadline(minDeadline())
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!vin.trim() || !query.trim() || isLoading) return
    onSearch(vin.trim(), query.trim(), urgency, urgency === "urgent" ? (urgencyDeadline || null) : null)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* VIN */}
      <div>
        <label className="block text-sm font-semibold text-zinc-300 mb-2">
          Vehicle VIN
        </label>
        <input
          type="text"
          value={vin}
          onChange={e => { setVin(e.target.value); setVinSpec(null); setVinError(false) }}
          onBlur={handleVinBlur}
          placeholder="17-character VIN"
          maxLength={17}
          className="w-full px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-xl font-mono text-base text-white placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-shadow"
        />
        {vinChecking && (
          <p className="mt-2 text-xs text-zinc-500 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-pulse" />
            Looking up vehicle…
          </p>
        )}
        {vinSpec && !vinChecking && (
          <p className="mt-2 text-xs text-orange-400 font-semibold flex items-center gap-1.5">
            <span className="text-orange-500">✓</span>
            {[vinSpec.year, vinSpec.make, vinSpec.model].filter(Boolean).join(" ")}
            {vinSpec.engine ? ` — ${vinSpec.engine}` : ""}
          </p>
        )}
        {vinError && !vinChecking && (
          <p className="mt-2 text-xs text-red-400 font-medium flex items-center gap-1.5">
            <span>✗</span> VIN not recognized — check the number and try again
          </p>
        )}
      </div>

      {/* Query */}
      <div>
        <label className="block text-sm font-semibold text-zinc-300 mb-2">
          What do you need?
        </label>
        <textarea
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="e.g. oil filter, fuel filter replacement, slack adjuster"
          rows={3}
          className="w-full px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-xl text-base text-white placeholder:text-zinc-500 resize-none focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-shadow"
        />
      </div>

      {/* Urgency + Submit */}
      <div className="flex items-center gap-3">
        <div className="inline-flex rounded-xl border border-zinc-700 overflow-hidden shrink-0 bg-zinc-900">
          <button
            type="button"
            onClick={() => setUrgency("standard")}
            className={`px-5 py-2.5 text-sm font-semibold transition-colors ${
              urgency === "standard"
                ? "bg-zinc-700 text-white"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            Standard
          </button>
          <button
            type="button"
            onClick={handleSetUrgent}
            className={`px-5 py-2.5 text-sm font-semibold transition-colors ${
              urgency === "urgent"
                ? "bg-orange-500 text-white"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            Urgent
          </button>
        </div>

        <button
          type="submit"
          disabled={isLoading || vin.trim().length !== 17 || !query.trim()}
          className="flex-1 py-2.5 bg-orange-500 text-white text-base font-bold rounded-xl hover:bg-orange-400 disabled:opacity-30 disabled:cursor-not-allowed active:scale-[0.98] transition-all duration-100 shadow-lg shadow-orange-500/20"
        >
          {isLoading ? "Searching…" : "Find Parts →"}
        </button>
      </div>

      {/* Deadline picker — shown only when urgent */}
      {urgency === "urgent" && (
        <div className="pt-1">
          <label className="block text-xs font-semibold text-orange-400 mb-1.5">
            Needed by
          </label>
          <input
            type="datetime-local"
            value={urgencyDeadline}
            min={minDeadline()}
            onChange={e => setUrgencyDeadline(e.target.value)}
            className="w-full px-4 py-2.5 bg-zinc-800 border border-orange-500/40 rounded-xl text-sm text-white focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-shadow"
          />
        </div>
      )}
    </form>
  )
}
