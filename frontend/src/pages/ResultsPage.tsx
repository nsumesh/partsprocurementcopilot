import { useEffect, useRef, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { streamSearch } from "../api/search"
import PartCard from "../components/PartCard"
import PartDetail from "../components/PartDetail"
import OrderConfirm from "../components/OrderConfirm"
import FilterPanel, { DEFAULT_FILTERS } from "../components/FilterPanel"
import type { FilterState } from "../components/FilterPanel"
import type { Order, SearchResultPart } from "../types"

interface LocationState {
  vin: string
  query: string
  urgency: "standard" | "urgent"
}

function extractYearRange(fit_notes: Record<string, unknown>): { min: number; max: number } | null {
  const yr = fit_notes.year_range
  if (!yr) return null
  if (typeof yr === "object" && yr !== null && "min" in yr && "max" in yr) {
    const o = yr as Record<string, unknown>
    return { min: Number(o.min), max: Number(o.max) }
  }
  if (typeof yr === "string") {
    const p = yr.split("-")
    if (p.length === 2) return { min: parseInt(p[0]), max: parseInt(p[1]) }
  }
  return null
}

function applyFilters(results: SearchResultPart[], f: FilterState): SearchResultPart[] {
  return results.filter(r => {
    const p = r.part
    const minP = parseFloat(f.minPrice)
    const maxP = parseFloat(f.maxPrice)
    if (!isNaN(minP) && (p.price_usd == null || p.price_usd < minP)) return false
    if (!isNaN(maxP) && (p.price_usd == null || p.price_usd > maxP)) return false
    if (f.sources.length > 0 && !f.sources.includes(p.source)) return false
    if (f.confidences.length > 0 && !f.confidences.includes(r.fitment.confidence)) return false
    const minY = parseInt(f.minYear)
    const maxY = parseInt(f.maxYear)
    if (!isNaN(minY) || !isNaN(maxY)) {
      const yr = extractYearRange(p.fit_notes)
      if (yr) {
        if (!isNaN(minY) && yr.max < minY) return false
        if (!isNaN(maxY) && yr.min > maxY) return false
      }
    }
    return true
  })
}

export default function ResultsPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const state = location.state as LocationState | null

  const abortRef = useRef<AbortController | null>(null)
  const [results, setResults] = useState<SearchResultPart[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [clarifyQuestion, setClarifyQuestion] = useState<string | null>(null)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [selectedResult, setSelectedResult] = useState<SearchResultPart | null>(null)
  const [confirmTarget, setConfirmTarget] = useState<SearchResultPart | null>(null)
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS)

  useEffect(() => {
    if (!state?.vin || !state?.query) {
      navigate("/", { replace: true })
      return
    }
    setIsStreaming(true)
    abortRef.current = streamSearch(
      { vin: state.vin, query: state.query, urgency: state.urgency },
      part => setResults(prev => [...prev, part]),
      question => { setResults([]); setClarifyQuestion(question); setIsStreaming(false) },
      () => setIsStreaming(false),
      msg => { setSearchError(msg); setIsStreaming(false) },
    )
    return () => { abortRef.current?.abort() }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (!state) return null

  const filtered = applyFilters(results, filters)

  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Sticky header */}
      <header className="sticky top-0 z-30 bg-zinc-950/95 backdrop-blur border-b border-zinc-800">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center gap-4">
          <button
            onClick={() => navigate("/")}
            className="text-sm text-zinc-500 hover:text-white font-semibold transition-colors flex items-center gap-1.5 shrink-0"
          >
            ← Back
          </button>
          <div className="w-px h-5 bg-zinc-800 shrink-0" />
          {/* Brand mark */}
          <span className="text-sm font-black text-white shrink-0 hidden sm:block">
            HeaviAI <span className="text-orange-500">·</span>
          </span>
          <div className="flex-1 min-w-0 flex items-center gap-2">
            <span className="text-sm font-bold text-zinc-300 truncate">"{state.query}"</span>
            <span className="text-zinc-700 shrink-0 hidden md:block">·</span>
            <span className="text-xs font-mono text-zinc-600 truncate hidden md:block">{state.vin}</span>
          </div>
          <div className="shrink-0 flex items-center gap-3">
            <button
              onClick={() => navigate("/orders")}
              className="text-xs text-zinc-500 hover:text-orange-400 font-semibold transition-colors hidden sm:block"
            >
              Orders
            </button>
            {isStreaming ? (
              <span className="text-xs text-orange-500 font-bold flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse" />
                Searching…
              </span>
            ) : (
              <span className="text-xs text-zinc-500 font-semibold tabular-nums">{results.length} parts</span>
            )}
            <span className={`px-2.5 py-1 rounded-lg text-xs font-bold ${
              state.urgency === "urgent"
                ? "bg-orange-500/15 text-orange-400"
                : "bg-zinc-800 text-zinc-500"
            }`}>
              {state.urgency}
            </span>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-7 flex gap-7 items-start">
        {/* Filter sidebar */}
        <aside className="w-64 shrink-0 hidden md:block">
          <div className="sticky top-24 bg-zinc-900 rounded-2xl border border-zinc-800 p-5">
            <FilterPanel
              filters={filters}
              onChange={setFilters}
              total={results.length}
              showing={filtered.length}
            />
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 min-w-0">
          {clarifyQuestion && (
            <div className="bg-orange-500/10 border border-orange-500/25 rounded-xl px-5 py-4 mb-5 animate-fade-in">
              <p className="text-sm text-orange-300">
                <span className="font-bold text-orange-400">Clarification needed: </span>
                {clarifyQuestion}
              </p>
              <button
                onClick={() => navigate("/")}
                className="mt-3 text-xs font-bold text-orange-500 hover:text-orange-400 transition-colors"
              >
                ← Refine your search
              </button>
            </div>
          )}

          {searchError && (
            <div className="bg-red-500/10 border border-red-500/25 rounded-xl px-5 py-4 mb-5 text-sm text-red-400 animate-fade-in">
              {searchError}
            </div>
          )}

          {/* Skeleton */}
          {isStreaming && results.length === 0 && (
            <div className="space-y-3">
              {[0, 1, 2, 3].map(i => (
                <div
                  key={i}
                  className="bg-zinc-900 border border-zinc-800 rounded-2xl px-6 py-5 animate-pulse"
                  style={{ animationDelay: `${i * 80}ms`, opacity: 1 - i * 0.18 }}
                >
                  <div className="flex justify-between mb-3">
                    <div className="h-5 bg-zinc-800 rounded-lg w-2/3" />
                    <div className="h-5 bg-zinc-800 rounded-lg w-20" />
                  </div>
                  <div className="h-3 bg-zinc-800/70 rounded-lg w-1/4 mb-4" />
                  <div className="flex gap-2">
                    <div className="h-6 bg-zinc-800/70 rounded-lg w-16" />
                    <div className="h-6 bg-zinc-800/70 rounded-lg w-24" />
                    <div className="h-6 bg-zinc-800/70 rounded-lg w-18 ml-auto" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Results */}
          <div className="space-y-3">
            {filtered.map(r => (
              <PartCard key={r.part.id} result={r} onClick={() => setSelectedResult(r)} />
            ))}
          </div>

          {/* Streaming dots */}
          {isStreaming && results.length > 0 && (
            <div className="flex items-center justify-center gap-1.5 py-6">
              {[0, 1, 2].map(i => (
                <span
                  key={i}
                  className="w-2 h-2 rounded-full bg-orange-500/50 animate-bounce"
                  style={{ animationDelay: `${i * 150}ms` }}
                />
              ))}
            </div>
          )}

          {!isStreaming && !clarifyQuestion && !searchError && filtered.length === 0 && results.length > 0 && (
            <div className="text-center py-20 animate-fade-in">
              <p className="text-zinc-500 text-sm">No parts match the current filters.</p>
              <button
                onClick={() => setFilters(DEFAULT_FILTERS)}
                className="mt-3 text-sm text-orange-500 hover:text-orange-400 font-semibold transition-colors"
              >
                Clear all filters
              </button>
            </div>
          )}

          {!isStreaming && !clarifyQuestion && !searchError && results.length === 0 && (
            <div className="text-center py-20 animate-fade-in">
              <p className="text-zinc-600 text-base">No parts found for this query.</p>
              <button
                onClick={() => navigate("/")}
                className="mt-3 text-sm text-orange-500 hover:text-orange-400 font-semibold transition-colors"
              >
                Try a different search →
              </button>
            </div>
          )}
        </main>
      </div>

      {selectedResult && (
        <PartDetail
          result={selectedResult}
          onOrder={() => { setConfirmTarget(selectedResult); setSelectedResult(null) }}
          onClose={() => setSelectedResult(null)}
        />
      )}

      {confirmTarget && (
        <OrderConfirm
          result={confirmTarget}
          vin={state.vin}
          query={state.query}
          urgency={state.urgency}
          onConfirm={(_order: Order) => { setConfirmTarget(null); navigate("/orders") }}
          onCancel={() => setConfirmTarget(null)}
        />
      )}
    </div>
  )
}
