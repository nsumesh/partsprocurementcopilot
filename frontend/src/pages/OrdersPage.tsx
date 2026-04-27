import { useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { getOrders } from "../api/orders"
import OrderHistory from "../components/OrderHistory"
import type { Order } from "../types"

export default function OrdersPage() {
  const navigate = useNavigate()
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getOrders()
      .then(setOrders)
      .catch(err => setError(String(err)))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="min-h-screen bg-zinc-950">
      <header className="sticky top-0 z-30 bg-zinc-950/95 backdrop-blur border-b border-zinc-800">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center gap-1">
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
            className="px-4 py-1.5 rounded-lg text-sm font-semibold bg-zinc-800 text-white"
          >
            Orders
          </button>
          <button
            onClick={() => navigate("/procurement")}
            className="px-4 py-1.5 rounded-lg text-sm font-semibold text-zinc-500 hover:text-white hover:bg-zinc-800/60 transition-colors"
          >
            Procurement
          </button>
          <div className="flex-1" />
          <Link
            to="/"
            className="px-4 py-2 bg-orange-500 text-white text-sm font-bold rounded-xl hover:bg-orange-400 transition-colors shadow-lg shadow-orange-500/20"
          >
            New Search →
          </Link>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="bg-zinc-900 rounded-2xl border border-zinc-800 p-6 shadow-xl shadow-black/40">
          {loading && (
            <div className="py-20 text-center">
              <div className="flex items-center justify-center gap-1.5">
                {[0, 1, 2].map(i => (
                  <span
                    key={i}
                    className="w-2 h-2 rounded-full bg-orange-500/60 animate-bounce"
                    style={{ animationDelay: `${i * 150}ms` }}
                  />
                ))}
              </div>
              <p className="text-zinc-600 text-sm mt-3">Loading orders…</p>
            </div>
          )}
          {error && (
            <div className="py-8 text-center text-red-400 text-sm bg-red-500/10 rounded-xl px-4">
              {error}
            </div>
          )}
          {!loading && !error && <OrderHistory orders={orders} />}
        </div>
      </div>
    </div>
  )
}
