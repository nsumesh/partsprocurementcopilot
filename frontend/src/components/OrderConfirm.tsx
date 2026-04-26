import { useState } from "react"
import { createOrder } from "../api/orders"
import type { Order, SearchResultPart } from "../types"

interface Props {
  result: SearchResultPart
  vin: string
  query: string
  urgency: "standard" | "urgent"
  onConfirm: (order: Order) => void
  onCancel: () => void
}

export default function OrderConfirm({ result, vin, query, urgency, onConfirm, onCancel }: Props) {
  const [quantity, setQuantity] = useState(1)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { part } = result

  async function handleConfirm() {
    setSubmitting(true)
    setError(null)
    try {
      const order = await createOrder({
        part_id: part.id,
        part_number: part.part_number,
        part_name: part.name,
        quantity,
        vin,
        query,
        urgency,
      })
      onConfirm(order)
    } catch (err) {
      setError(String(err))
      setSubmitting(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4"
      onClick={onCancel}
    >
      <div
        className="bg-zinc-900 border border-zinc-800 rounded-3xl shadow-2xl shadow-black/60 w-full max-w-md p-7 animate-fade-up"
        onClick={e => e.stopPropagation()}
      >
        <h2 className="text-xl font-bold text-white mb-1">Confirm Order</h2>
        <p className="text-sm text-zinc-400 mb-6 truncate">{part.name}</p>

        <dl className="space-y-3 mb-6">
          <div className="flex justify-between items-center py-2.5 border-b border-zinc-800">
            <dt className="text-sm text-zinc-500">Part number</dt>
            <dd className="font-mono text-zinc-200 text-sm tracking-wider">{part.part_number}</dd>
          </div>
          {part.brand && (
            <div className="flex justify-between items-center py-2.5 border-b border-zinc-800">
              <dt className="text-sm text-zinc-500">Brand</dt>
              <dd className="text-white font-semibold text-sm">{part.brand}</dd>
            </div>
          )}
          {part.price_usd != null && (
            <div className="flex justify-between items-center py-2.5 border-b border-zinc-800">
              <dt className="text-sm text-zinc-500">Unit price</dt>
              <dd className="text-2xl font-black text-orange-400">${part.price_usd.toFixed(2)}</dd>
            </div>
          )}
          {part.price_usd != null && (
            <div className="flex justify-between items-center py-2.5">
              <dt className="text-sm text-zinc-500">Total</dt>
              <dd className="text-lg font-black text-white">
                ${(part.price_usd * quantity).toFixed(2)}
              </dd>
            </div>
          )}
        </dl>

        <div className="mb-6">
          <label className="block text-sm font-semibold text-zinc-300 mb-2">Quantity</label>
          <input
            type="number"
            min={1}
            value={quantity}
            onChange={e => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
            className="w-32 px-4 py-2.5 bg-zinc-800 border border-zinc-700 rounded-xl text-white text-base font-semibold focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
          />
        </div>

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
            onClick={handleConfirm}
            disabled={submitting}
            className="flex-1 py-3 bg-orange-500 text-white text-sm font-bold rounded-xl hover:bg-orange-400 disabled:opacity-40 active:scale-[0.98] transition-all shadow-lg shadow-orange-500/20"
          >
            {submitting ? "Ordering…" : "Confirm Order"}
          </button>
        </div>
      </div>
    </div>
  )
}
