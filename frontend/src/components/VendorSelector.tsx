import { useEffect, useState } from "react"
import { getVendorsForPart } from "../api/vendors"
import type { Part, VendorPart } from "../types"

interface Props {
  part: Part
  urgency: "standard" | "urgent"
  urgencyDeadline: string | null
  onSelect: (vendorPart: VendorPart, deadline: string | null) => void
  onClose: () => void
}

const RESPONSE_BADGE: Record<string, string> = {
  high:   "bg-green-500/10 text-green-400 ring-green-500/25",
  medium: "bg-yellow-500/10 text-yellow-400 ring-yellow-500/25",
  low:    "bg-red-500/10 text-red-400 ring-red-500/25",
}

function responseBadge(rate: number) {
  if (rate >= 0.85) return RESPONSE_BADGE.high
  if (rate >= 0.70) return RESPONSE_BADGE.medium
  return RESPONSE_BADGE.low
}

function minDeadline() {
  const d = new Date(Date.now() + 2 * 60 * 60 * 1000)
  return d.toISOString().slice(0, 16)
}

function fitsDeadline(deliveryHours: number | null, deadline: string | null) {
  if (!deadline || deliveryHours == null) return true
  const deadlineMs = new Date(deadline).getTime()
  const deliveryMs = Date.now() + deliveryHours * 60 * 60 * 1000
  return deliveryMs <= deadlineMs
}

export default function VendorSelector({ part, urgency, urgencyDeadline, onSelect, onClose }: Props) {
  const [vendors, setVendors] = useState<VendorPart[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deadline, setDeadline] = useState<string>(urgencyDeadline ?? minDeadline())

  useEffect(() => {
    getVendorsForPart(part.id)
      .then(setVendors)
      .catch(() => setError("Could not load vendors"))
      .finally(() => setLoading(false))
  }, [part.id])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4"
      onClick={onClose}
    >
      <div
        className="bg-zinc-900 border border-zinc-800 rounded-3xl shadow-2xl shadow-black/60 w-full max-w-lg p-7 animate-fade-up max-h-[85vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-1">
          <h2 className="text-xl font-bold text-white">Select Vendor</h2>
          <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-xl bg-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-700 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>
        <p className="text-sm text-zinc-400 mb-5 truncate">{part.name}</p>

        {urgency === "urgent" && (
          <div className="mb-5">
            <label className="block text-xs font-bold text-zinc-400 uppercase tracking-widest mb-2">
              Needed by
            </label>
            <input
              type="datetime-local"
              min={minDeadline()}
              value={deadline}
              onChange={e => setDeadline(e.target.value)}
              className="w-full px-4 py-2.5 bg-zinc-800 border border-zinc-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
            />
          </div>
        )}

        <div className="overflow-y-auto flex-1 space-y-3 pr-1">
          {loading && (
            <div className="text-sm text-zinc-500 py-8 text-center">Loading vendors…</div>
          )}
          {error && (
            <div className="text-sm text-red-400 py-4 text-center">{error}</div>
          )}
          {!loading && !error && vendors.map(vp => {
            const fits = fitsDeadline(vp.delivery_hours, urgency === "urgent" ? deadline : null)
            return (
              <button
                key={vp.id}
                onClick={() => onSelect(vp, urgency === "urgent" ? deadline : null)}
                className={`w-full text-left px-5 py-4 rounded-2xl border transition-all ${
                  fits
                    ? "bg-zinc-800 border-zinc-700 hover:border-orange-500/50 hover:bg-zinc-700"
                    : "bg-zinc-800/50 border-zinc-800 opacity-60"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-white text-sm">{vp.vendor?.name}</span>
                  <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full ring-1 ring-inset ${responseBadge(vp.vendor?.response_rate ?? 0)}`}>
                    {Math.round((vp.vendor?.response_rate ?? 0) * 100)}% response
                  </span>
                </div>
                <div className="flex items-center gap-4 text-xs text-zinc-400">
                  <span className="bg-zinc-700 px-2 py-0.5 rounded-md">{vp.vendor?.type}</span>
                  <span>{vp.delivery_estimate ?? "ETA unknown"}</span>
                  {vp.list_price != null && (
                    <span className="text-orange-400 font-bold ml-auto">${vp.list_price.toFixed(2)}</span>
                  )}
                </div>
                {urgency === "urgent" && !fits && (
                  <p className="text-xs text-amber-400 mt-2">May not meet deadline</p>
                )}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
