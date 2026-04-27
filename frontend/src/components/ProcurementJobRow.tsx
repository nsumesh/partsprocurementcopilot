import type { ProcurementJob } from "../types"

interface Props {
  job: ProcurementJob
  onClick: () => void
}

const STATUS_LABEL: Record<string, string> = {
  created:            "Created",
  outreach_sent:      "Awaiting Response",
  response_received:  "Response Received",
  parsed:             "Awaiting Confirmation",
  follow_up_required: "Follow-Up Required",
  follow_up_sent:     "Awaiting Follow-Up",
  confirmed:          "Confirmed",
  ranked:             "Ranked",
  accepted:           "Accepted",
  rejected:           "Rejected",
}

const STATUS_COLOR: Record<string, string> = {
  created:            "bg-zinc-700 text-zinc-300",
  outreach_sent:      "bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/25 animate-pulse",
  response_received:  "bg-indigo-500/10 text-indigo-400 ring-1 ring-indigo-500/25",
  parsed:             "bg-yellow-500/10 text-yellow-400 ring-1 ring-yellow-500/25",
  follow_up_required: "bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/25",
  follow_up_sent:     "bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/25 animate-pulse",
  confirmed:          "bg-green-500/10 text-green-400 ring-1 ring-green-500/25",
  ranked:             "bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/25",
  accepted:           "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-400/40",
  rejected:           "bg-red-500/10 text-red-400 ring-1 ring-red-500/25",
}

function elapsed(isoString: string) {
  const diff = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000)
  if (diff < 60) return `${diff}s`
  if (diff < 3600) return `${Math.floor(diff / 60)}m`
  return `${Math.floor(diff / 3600)}h ${Math.floor((diff % 3600) / 60)}m`
}

export default function ProcurementJobRow({ job, onClick }: Props) {
  const lastEvent = job.events[job.events.length - 1]
  const lastAction = lastEvent
    ? `${STATUS_LABEL[lastEvent.to_status] ?? lastEvent.to_status} by ${lastEvent.actor}`
    : "—"
  const elapsedTime = lastEvent ? elapsed(lastEvent.created_at) : "—"

  return (
    <tr
      onClick={onClick}
      className="border-b border-zinc-800 hover:bg-zinc-800/50 cursor-pointer transition-colors"
    >
      <td className="px-6 py-4">
        <p className="text-sm font-semibold text-white">{job.part_name}</p>
        <p className="text-xs font-mono text-zinc-500 mt-0.5">{job.part_number}</p>
      </td>
      <td className="px-6 py-4">
        <p className="text-sm text-zinc-300">{job.vendor?.name ?? "—"}</p>
        <p className="text-xs text-zinc-500">{job.vendor?.type ?? ""}</p>
      </td>
      <td className="px-6 py-4">
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${STATUS_COLOR[job.status] ?? "bg-zinc-700 text-zinc-300"}`}>
          {STATUS_LABEL[job.status] ?? job.status}
        </span>
      </td>
      <td className="px-6 py-4 text-sm text-zinc-400 tabular-nums">{elapsedTime}</td>
      <td className="px-6 py-4 text-xs text-zinc-500 max-w-[200px] truncate">{lastAction}</td>
    </tr>
  )
}
