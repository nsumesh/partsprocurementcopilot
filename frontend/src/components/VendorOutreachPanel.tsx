import { useState } from "react"
import { acceptJob, confirmParsedFields, rejectJob, sendFollowup } from "../api/procurement"
import type { ProcurementJob } from "../types"

interface Props {
  job: ProcurementJob
  onClose: () => void
  onJobUpdate: (job: ProcurementJob) => void
}

const STATUS_LABEL: Record<string, string> = {
  created:              "Created",
  outreach_sent:        "Awaiting Response",
  response_received:    "Response Received",
  parsed:               "Awaiting Confirmation",
  follow_up_required:   "Follow-Up Required",
  follow_up_sent:       "Awaiting Follow-Up Response",
  confirmed:            "Confirmed",
  ranked:               "Ranked",
  accepted:             "Accepted",
  rejected:             "Rejected",
}

const STATUS_COLOR: Record<string, string> = {
  created:              "bg-zinc-700 text-zinc-300",
  outreach_sent:        "bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/25",
  response_received:    "bg-indigo-500/10 text-indigo-400 ring-1 ring-indigo-500/25",
  parsed:               "bg-yellow-500/10 text-yellow-400 ring-1 ring-yellow-500/25",
  follow_up_required:   "bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/25",
  follow_up_sent:       "bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/25",
  confirmed:            "bg-green-500/10 text-green-400 ring-1 ring-green-500/25",
  ranked:               "bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/25",
  accepted:             "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-400/40",
  rejected:             "bg-red-500/10 text-red-400 ring-1 ring-red-500/25",
}

function elapsed(isoString: string) {
  const diff = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000)
  if (diff < 60) return `${diff}s`
  if (diff < 3600) return `${Math.floor(diff / 60)}m`
  return `${Math.floor(diff / 3600)}h ${Math.floor((diff % 3600) / 60)}m`
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-zinc-400">{label}</span>
        <span className="text-zinc-300 font-semibold">{(value * 100).toFixed(0)}%</span>
      </div>
      <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div className="h-full bg-orange-500 rounded-full" style={{ width: `${value * 100}%` }} />
      </div>
    </div>
  )
}

export default function VendorOutreachPanel({ job, onClose, onJobUpdate }: Props) {
  const [followUpText, setFollowUpText] = useState(job.follow_up_email ?? "")
  const [acting, setActing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [outreachOpen, setOutreachOpen] = useState(false)

  const lastEvent = job.events[job.events.length - 1]
  const lastEventTime = lastEvent?.created_at

  async function act(fn: () => Promise<ProcurementJob>) {
    setActing(true)
    setError(null)
    try {
      const updated = await fn()
      onJobUpdate(updated)
    } catch (err) {
      setError(String(err))
    } finally {
      setActing(false)
    }
  }

  const maxPrice = Math.max(job.parsed_unit_price ?? 0, 500)
  const priceScore  = job.parsed_unit_price != null ? 1 - job.parsed_unit_price / maxPrice : null
  const deliveryScore = job.parsed_delivery_hours != null ? 1 - job.parsed_delivery_hours / 720 : null

  return (
    <div className="fixed inset-0 z-40 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-lg bg-zinc-900 border-l border-zinc-800 shadow-2xl flex flex-col h-full overflow-y-auto animate-slide-in-right"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-zinc-900/95 backdrop-blur border-b border-zinc-800 px-6 py-5 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="text-xl font-bold text-white leading-snug">{job.part_name}</h2>
            <p className="text-xs font-mono text-zinc-500 mt-1 tracking-wider">{job.part_number}</p>
            <div className="flex items-center gap-3 mt-2 flex-wrap">
              <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${STATUS_COLOR[job.status] ?? "bg-zinc-700 text-zinc-300"}`}>
                {STATUS_LABEL[job.status] ?? job.status}
              </span>
              {lastEventTime && (
                <span className="text-xs text-zinc-500">{elapsed(lastEventTime)} in this state</span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 w-9 h-9 flex items-center justify-center rounded-xl bg-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-700 transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 px-6 py-6 space-y-7">

          {/* Vendor info */}
          {job.vendor && (
            <section>
              <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-3">Vendor</h3>
              <div className="bg-zinc-800 rounded-xl px-4 py-3 text-sm space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-zinc-400">Name</span>
                  <span className="text-white font-semibold">{job.vendor.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Type</span>
                  <span className="text-zinc-300">{job.vendor.type}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Response rate</span>
                  <span className="text-zinc-300">{Math.round(job.vendor.response_rate * 100)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Contact</span>
                  <span className="text-zinc-300 text-xs">{job.vendor.email}</span>
                </div>
              </div>
            </section>
          )}

          {/* Outreach email (collapsible) */}
          {job.outreach_email && (
            <section>
              <button
                className="flex items-center gap-2 text-xs font-bold text-zinc-500 uppercase tracking-widest mb-3 hover:text-zinc-300 transition-colors"
                onClick={() => setOutreachOpen(o => !o)}
              >
                Outreach Email
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className={`w-4 h-4 transition-transform ${outreachOpen ? "rotate-180" : ""}`}>
                  <path fillRule="evenodd" d="M5.22 8.22a.75.75 0 011.06 0L10 11.94l3.72-3.72a.75.75 0 111.06 1.06l-4.25 4.25a.75.75 0 01-1.06 0L5.22 9.28a.75.75 0 010-1.06z" clipRule="evenodd" />
                </svg>
              </button>
              {outreachOpen && (
                <pre className="text-xs text-zinc-300 bg-zinc-800 rounded-xl px-4 py-3 whitespace-pre-wrap leading-relaxed font-mono overflow-x-auto">
                  {job.outreach_email}
                </pre>
              )}
            </section>
          )}

          {/* Vendor response */}
          {job.response_email && (
            <section>
              <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-3">Vendor Response</h3>
              <pre className="text-xs text-zinc-300 bg-zinc-800 rounded-xl px-4 py-3 whitespace-pre-wrap leading-relaxed font-mono overflow-x-auto">
                {job.response_email}
              </pre>
            </section>
          )}

          {/* Parsed fields */}
          {(job.parsed_availability || job.parsed_unit_price != null || job.parsed_quantity_available != null || job.parsed_delivery_date) && (
            <section>
              <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-3">Parsed Fields</h3>
              <dl className="divide-y divide-zinc-800 border border-zinc-800 rounded-xl overflow-hidden text-sm">
                {[
                  { label: "Availability",  value: job.parsed_availability },
                  { label: "Unit price",    value: job.parsed_unit_price != null ? `$${job.parsed_unit_price.toFixed(2)}` : null },
                  { label: "Qty available", value: job.parsed_quantity_available?.toString() },
                  { label: "Delivery date", value: job.parsed_delivery_date },
                ].map(({ label, value }) => (
                  <div key={label} className="flex px-4 py-2.5 odd:bg-zinc-900 even:bg-zinc-800/50 gap-4">
                    <dt className="w-32 shrink-0 text-zinc-500">{label}</dt>
                    <dd className={value ? "text-zinc-200 font-medium" : "text-amber-400 italic"}>
                      {value ?? "missing"}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          )}

          {/* Human-in-the-loop confirmation */}
          {job.status === "parsed" && (
            <section className="bg-yellow-500/5 border border-yellow-500/20 rounded-xl px-4 py-4">
              <p className="text-sm font-bold text-yellow-400 mb-1">Review required</p>
              <p className="text-xs text-zinc-400 mb-4">
                All fields parsed successfully. Review the response and parsed data above, then confirm to proceed to ranking.
              </p>
              <button
                onClick={() => act(() => confirmParsedFields(job.id))}
                disabled={acting}
                className="w-full py-3 bg-yellow-500 text-zinc-900 text-sm font-bold rounded-xl hover:bg-yellow-400 disabled:opacity-40 active:scale-[0.98] transition-all"
              >
                {acting ? "Confirming…" : "Confirm & Proceed to Ranking →"}
              </button>
            </section>
          )}

          {/* Follow-up editor */}
          {job.status === "follow_up_required" && (
            <section>
              <h3 className="text-xs font-bold text-amber-500 uppercase tracking-widest mb-3">Follow-Up Required</h3>
              <textarea
                value={followUpText}
                onChange={e => setFollowUpText(e.target.value)}
                rows={8}
                className="w-full px-4 py-3 bg-zinc-800 border border-amber-500/30 rounded-xl text-sm text-zinc-200 leading-relaxed font-mono resize-none focus:outline-none focus:ring-2 focus:ring-amber-500 mb-3"
              />
              <button
                onClick={() => act(() => sendFollowup(job.id, followUpText))}
                disabled={acting}
                className="w-full py-3 bg-amber-500 text-zinc-900 text-sm font-bold rounded-xl hover:bg-amber-400 disabled:opacity-40 active:scale-[0.98] transition-all"
              >
                {acting ? "Sending…" : "Send Follow-Up →"}
              </button>
            </section>
          )}

          {/* Ranking score */}
          {job.status === "ranked" && job.ranking_score != null && (
            <section>
              <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-3">Ranking Score</h3>
              <div className="bg-zinc-800 rounded-xl px-4 py-4 space-y-3">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-zinc-400 text-sm">Composite score</span>
                  <span className="text-2xl font-black text-orange-400">{(job.ranking_score * 100).toFixed(0)}</span>
                </div>
                {priceScore != null && <ScoreBar label="Price (40%)" value={priceScore} />}
                {deliveryScore != null && <ScoreBar label="Delivery (40%)" value={deliveryScore} />}
                {job.vendor && <ScoreBar label="Response rate (20%)" value={job.vendor.response_rate} />}
              </div>
            </section>
          )}

          {error && (
            <p className="text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-2">{error}</p>
          )}
        </div>

        {/* Footer — accept/reject */}
        {job.status === "ranked" && (
          <div className="sticky bottom-0 bg-zinc-900/95 backdrop-blur border-t border-zinc-800 px-6 py-5 flex gap-3">
            <button
              onClick={() => act(() => rejectJob(job.id))}
              disabled={acting}
              className="flex-1 py-3 bg-zinc-800 border border-zinc-700 text-sm font-bold text-zinc-300 rounded-xl hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/30 disabled:opacity-40 transition-all"
            >
              Reject
            </button>
            <button
              onClick={() => act(() => acceptJob(job.id))}
              disabled={acting}
              className="flex-1 py-3 bg-orange-500 text-white text-sm font-bold rounded-xl hover:bg-orange-400 disabled:opacity-40 active:scale-[0.98] transition-all shadow-lg shadow-orange-500/20"
            >
              {acting ? "Updating…" : "Accept →"}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
