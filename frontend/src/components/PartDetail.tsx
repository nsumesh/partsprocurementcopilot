import type { FitmentConfidence, SearchResultPart } from "../types"

const CONF_STYLES: Record<FitmentConfidence, string> = {
  "High Probability":   "bg-green-500/10 text-green-400 ring-green-500/25",
  "Medium Probability": "bg-yellow-500/10 text-yellow-400 ring-yellow-500/25",
  "Low Probability":    "bg-amber-500/10 text-amber-400 ring-amber-500/25",
  "No Fitment":         "bg-red-500/10 text-red-400 ring-red-500/25",
}

interface Props {
  result: SearchResultPart
  onOrder: () => void
  onClose: () => void
}

export default function PartDetail({ result, onOrder, onClose }: Props) {
  const { part, fitment } = result
  const attrs = Object.entries(part.attributes).filter(([, v]) => v != null && v !== "")

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
            <h2 className="text-xl font-bold text-white leading-snug">{part.name}</h2>
            <p className="text-xs font-mono text-zinc-500 mt-1 tracking-wider">{part.part_number}</p>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 w-9 h-9 flex items-center justify-center rounded-xl bg-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-700 transition-colors"
            aria-label="Close"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 px-6 py-6 space-y-7">
          {/* Fitment */}
          <section>
            <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-3">Fitment</h3>
            <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold ring-1 ring-inset ${CONF_STYLES[fitment.confidence]}`}>
              {fitment.confidence}
            </span>
            <p className="text-sm text-zinc-300 mt-3 leading-relaxed">{fitment.reasoning}</p>
          </section>

          {/* Details */}
          {(part.price_usd != null || part.brand) && (
            <section>
              <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-3">Details</h3>
              <dl className="space-y-2.5 text-sm">
                {part.brand && (
                  <div className="flex justify-between items-center">
                    <dt className="text-zinc-500">Brand</dt>
                    <dd className="text-white font-semibold">{part.brand}</dd>
                  </div>
                )}
                {part.price_usd != null && (
                  <div className="flex justify-between items-center">
                    <dt className="text-zinc-500">Unit price</dt>
                    <dd className="text-2xl font-black text-orange-400">${part.price_usd.toFixed(2)}</dd>
                  </div>
                )}
              </dl>
            </section>
          )}

          {/* Description */}
          {part.description && (
            <section>
              <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-3">Description</h3>
              <p className="text-sm text-zinc-300 leading-relaxed">{part.description}</p>
            </section>
          )}

          {/* Specifications */}
          {attrs.length > 0 && (
            <section>
              <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-3">Specifications</h3>
              <dl className="divide-y divide-zinc-800 border border-zinc-800 rounded-xl overflow-hidden text-sm">
                {attrs.map(([k, v]) => (
                  <div key={k} className="flex px-4 py-2.5 odd:bg-zinc-900 even:bg-zinc-800/50 gap-4">
                    <dt className="w-36 shrink-0 text-zinc-500 capitalize">{k.replace(/_/g, " ")}</dt>
                    <dd className="text-zinc-200 break-words font-medium">{String(v)}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )}

          {/* Vendor sources */}
          {part.vendor_urls.length > 0 && (
            <section>
              <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-3">Sources</h3>
              <ul className="space-y-3">
                {part.vendor_urls.map((v, i) => (
                  <li key={i} className="flex items-center justify-between text-sm py-2 border-b border-zinc-800 last:border-0">
                    <span className="text-zinc-300 font-medium">{v.vendor}</span>
                    <a
                      href={v.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-orange-500 hover:text-orange-400 text-xs font-bold transition-colors"
                    >
                      View listing →
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-zinc-900/95 backdrop-blur border-t border-zinc-800 px-6 py-5">
          <button
            onClick={onOrder}
            className="w-full py-3.5 bg-orange-500 text-white text-base font-bold rounded-xl hover:bg-orange-400 active:scale-[0.98] transition-all duration-100 shadow-lg shadow-orange-500/20"
          >
            Order This Part →
          </button>
        </div>
      </div>
    </div>
  )
}
