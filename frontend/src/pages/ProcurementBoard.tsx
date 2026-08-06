import { createClient } from "@supabase/supabase-js"
import type { SupabaseClient } from "@supabase/supabase-js"
import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { getProcurementJobs } from "../api/procurement"
import ProcurementJobRow from "../components/ProcurementJobRow"
import VendorOutreachPanel from "../components/VendorOutreachPanel"
import type { ProcurementJob } from "../types"

// Lazily constructed so a missing env var degrades gracefully instead of
// throwing at module load and white-screening the whole SPA.
let supabaseClient: SupabaseClient | null = null
let supabaseInitialized = false

function getSupabase(): SupabaseClient | null {
  if (!supabaseInitialized) {
    supabaseInitialized = true
    const url = import.meta.env.VITE_SUPABASE_URL as string | undefined
    const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined
    if (url && anonKey) {
      try {
        supabaseClient = createClient(url, anonKey)
      } catch {
        supabaseClient = null
      }
    }
  }
  return supabaseClient
}

export default function ProcurementBoard() {
  const navigate = useNavigate()
  const [jobs, setJobs] = useState<ProcurementJob[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<ProcurementJob | null>(null)
  const [realtimeUnavailable, setRealtimeUnavailable] = useState(false)

  useEffect(() => {
    getProcurementJobs()
      .then(setJobs)
      .catch(() => setError("Failed to load jobs"))
      .finally(() => setLoading(false))

    const supabase = getSupabase()
    if (!supabase) {
      setRealtimeUnavailable(true)
      return
    }

    const channel = supabase
      .channel("procurement_jobs_realtime")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "procurement_jobs" },
        payload => {
          // Realtime payloads are raw Postgres rows — no vendor join, no events array.
          const raw = payload.new as ProcurementJob | undefined
          if (!raw?.id) return
          setJobs(prev => {
            const exists = prev.some(j => j.id === raw.id)
            if (exists) return prev.map(j => j.id === raw.id ? { ...j, ...raw } : j)
            const inserted: ProcurementJob = { ...raw, events: raw.events ?? [], vendor: raw.vendor ?? null }
            return [inserted, ...prev]
          })
          setSelected(prev => prev?.id === raw.id ? { ...prev, ...raw } : prev)
        }
      )
      .subscribe()

    return () => { supabase.removeChannel(channel) }
  }, [])

  function handleJobUpdate(updated: ProcurementJob) {
    setJobs(prev => prev.map(j => j.id === updated.id ? { ...j, ...updated } : j))
    setSelected(prev => prev ? { ...prev, ...updated } : updated)
  }

  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Header */}
      <header className="sticky top-0 z-30 bg-zinc-950/95 backdrop-blur border-b border-zinc-800">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center gap-1">
          <span className="text-sm font-black text-white mr-4">
            HeaviAI <span className="text-orange-500">·</span>
          </span>
          <button
            onClick={() => navigate("/")}
            className="px-4 py-1.5 rounded-lg text-sm font-semibold text-zinc-500 hover:text-white hover:bg-zinc-800/60 transition-colors"
          >
            Search
          </button>
          <button
            onClick={() => navigate("/orders")}
            className="px-4 py-1.5 rounded-lg text-sm font-semibold text-zinc-500 hover:text-white hover:bg-zinc-800/60 transition-colors"
          >
            Orders
          </button>
          <button
            onClick={() => navigate("/procurement")}
            className="px-4 py-1.5 rounded-lg text-sm font-semibold bg-zinc-800 text-white"
          >
            Procurement
          </button>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-7">
        {realtimeUnavailable && (
          <div className="mb-5 bg-amber-500/10 border border-amber-500/25 rounded-xl px-4 py-3 text-sm text-amber-400">
            Realtime updates unavailable — Supabase env vars not configured
          </div>
        )}
        {loading && (
          <div className="text-sm text-zinc-500 py-16 text-center">Loading jobs…</div>
        )}
        {error && (
          <div className="text-sm text-red-400 py-16 text-center">{error}</div>
        )}
        {!loading && !error && jobs.length === 0 && (
          <div className="text-center py-24">
            <p className="text-zinc-600 text-base">No procurement jobs yet.</p>
            <button
              onClick={() => navigate("/")}
              className="mt-3 text-sm text-orange-500 hover:text-orange-400 font-semibold transition-colors"
            >
              Search for parts →
            </button>
          </div>
        )}
        {!loading && jobs.length > 0 && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="px-6 py-4 text-left text-xs font-bold text-zinc-500 uppercase tracking-widest">Part</th>
                  <th className="px-6 py-4 text-left text-xs font-bold text-zinc-500 uppercase tracking-widest">Vendor</th>
                  <th className="px-6 py-4 text-left text-xs font-bold text-zinc-500 uppercase tracking-widest">Status</th>
                  <th className="px-6 py-4 text-left text-xs font-bold text-zinc-500 uppercase tracking-widest">Elapsed</th>
                  <th className="px-6 py-4 text-left text-xs font-bold text-zinc-500 uppercase tracking-widest">Last Action</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map(job => (
                  <ProcurementJobRow
                    key={job.id}
                    job={job}
                    onClick={() => setSelected(job)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selected && (
        <VendorOutreachPanel
          job={selected}
          onClose={() => setSelected(null)}
          onJobUpdate={handleJobUpdate}
        />
      )}
    </div>
  )
}
