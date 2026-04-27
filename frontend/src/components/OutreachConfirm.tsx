import { useState } from "react"
import { sendOutreach } from "../api/procurement"
import type { ProcurementJob } from "../types"

interface Props {
  job: ProcurementJob
  onConfirm: (updated: ProcurementJob) => void
  onCancel: () => void
}

export default function OutreachConfirm({ job, onConfirm, onCancel }: Props) {
  const [email, setEmail] = useState(job.outreach_email ?? "")
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSend() {
    setSending(true)
    setError(null)
    try {
      const updated = await sendOutreach(job.id)
      onConfirm(updated)
    } catch (err) {
      setError(String(err))
      setSending(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4"
      onClick={onCancel}
    >
      <div
        className="bg-zinc-900 border border-zinc-800 rounded-3xl shadow-2xl shadow-black/60 w-full max-w-lg p-7 animate-fade-up flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        <h2 className="text-xl font-bold text-white mb-1">Review Outreach Email</h2>
        <p className="text-sm text-zinc-400 mb-5">
          To: <span className="text-zinc-300">{job.vendor?.name}</span>
          {job.vendor?.email && <span className="text-zinc-500"> &lt;{job.vendor.email}&gt;</span>}
        </p>

        <textarea
          value={email}
          onChange={e => setEmail(e.target.value)}
          rows={10}
          className="w-full px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-xl text-sm text-zinc-200 leading-relaxed font-mono resize-none focus:outline-none focus:ring-2 focus:ring-orange-500 mb-5"
        />

        {error && (
          <p className="text-xs text-red-400 mb-4 bg-red-500/10 rounded-lg px-3 py-2">{error}</p>
        )}

        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 py-3 bg-zinc-800 border border-zinc-700 text-sm font-semibold text-zinc-300 rounded-xl hover:bg-zinc-700 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSend}
            disabled={sending}
            className="flex-1 py-3 bg-orange-500 text-white text-sm font-bold rounded-xl hover:bg-orange-400 disabled:opacity-40 active:scale-[0.98] transition-all shadow-lg shadow-orange-500/20"
          >
            {sending ? "Sending…" : "Send Outreach →"}
          </button>
        </div>
      </div>
    </div>
  )
}
