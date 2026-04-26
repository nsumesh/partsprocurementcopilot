import { useNavigate } from "react-router-dom"
import SearchBar from "../components/SearchBar"

export default function SearchPage() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col">
      {/* Subtle grid background */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />

      <div className="relative flex-1 flex items-center justify-center px-4 py-16">
        <div className="w-full max-w-xl">
          {/* Brand */}
          <div className="text-center mb-12">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-orange-500 shadow-2xl shadow-orange-500/30 mb-6">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white" className="w-8 h-8">
                <path d="M3.375 4.5C2.339 4.5 1.5 5.34 1.5 6.375V13.5h12V6.375c0-1.036-.84-1.875-1.875-1.875h-8.25zM13.5 15h-12v2.625c0 1.035.84 1.875 1.875 1.875H3.75a3 3 0 106 0h3.75a.75.75 0 00.75-.75V15z" />
                <path d="M8.25 19.5a1.5 1.5 0 10-3 0 1.5 1.5 0 003 0zM15.75 6.75a.75.75 0 00-.75.75v11.25c0 .087.015.17.042.248a3 3 0 015.958.464c.853-.175 1.522-.935 1.464-1.883a18.659 18.659 0 00-3.732-10.104 1.837 1.837 0 00-1.47-.725h-1.512z" />
                <path d="M19.5 19.5a1.5 1.5 0 10-3 0 1.5 1.5 0 003 0z" />
              </svg>
            </div>
            <h1 className="text-4xl font-black text-white tracking-tight">
              HeaviAI{" "}
              <span className="text-orange-500">Procurement</span>
              <br />
              <span className="text-3xl font-bold text-zinc-400">CoPilot</span>
            </h1>
            <p className="mt-4 text-zinc-500 text-base">
              AI-powered OEM &amp; aftermarket parts search for fleet operators
            </p>
          </div>

          {/* Form card */}
          <div className="bg-zinc-900 rounded-3xl border border-zinc-800 p-8 shadow-2xl shadow-black/60">
            <SearchBar
              onSearch={(vin, query, urgency) =>
                navigate("/results", { state: { vin, query, urgency } })
              }
              isLoading={false}
            />
          </div>

          <p className="text-center text-xs text-zinc-700 mt-6">
            Powered by Claude AI · Cohere Rerank · pgvector
          </p>
        </div>
      </div>
    </div>
  )
}
