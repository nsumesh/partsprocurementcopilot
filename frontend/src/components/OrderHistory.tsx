import type { Order } from "../types"

interface Props {
  orders: Order[]
}

export default function OrderHistory({ orders }: Props) {
  if (orders.length === 0) {
    return (
      <div className="py-20 text-center">
        <p className="text-zinc-600 text-sm">No orders placed yet.</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-800">
            {["Part", "Part #", "Qty", "VIN", "Urgency", "Date"].map(h => (
              <th
                key={h}
                className="text-left py-3 pr-6 last:pr-0 text-xs font-bold text-zinc-500 uppercase tracking-wider whitespace-nowrap"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800/60">
          {orders.map(order => (
            <tr key={order.id} className="hover:bg-zinc-800/40 transition-colors group">
              <td className="py-4 pr-6 text-white font-semibold max-w-xs truncate group-hover:text-orange-400 transition-colors">
                {order.part_name}
              </td>
              <td className="py-4 pr-6 font-mono text-zinc-500 text-xs tracking-wider whitespace-nowrap">
                {order.part_number}
              </td>
              <td className="py-4 pr-6 text-zinc-300 font-bold tabular-nums">{order.quantity}</td>
              <td className="py-4 pr-6 font-mono text-zinc-600 text-xs tracking-wider whitespace-nowrap">
                {order.vin ?? "—"}
              </td>
              <td className="py-4 pr-6">
                <span className={`px-2.5 py-1 rounded-lg text-xs font-bold ${
                  order.urgency === "urgent"
                    ? "bg-orange-500/15 text-orange-400"
                    : "bg-zinc-800 text-zinc-400"
                }`}>
                  {order.urgency}
                </span>
              </td>
              <td className="py-4 text-zinc-600 text-xs whitespace-nowrap tabular-nums">
                {new Date(order.created_at).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
