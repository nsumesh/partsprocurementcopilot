import { API_BASE } from "./client"
import type { SearchResultPart } from "../types"

export interface SearchRequest {
  vin: string
  query: string
  urgency: "standard" | "urgent"
}

export function streamSearch(
  request: SearchRequest,
  onPart: (p: SearchResultPart) => void,
  onClarify: (question: string) => void,
  onDone: () => void,
  onError: (message: string) => void,
): AbortController {
  const ctrl = new AbortController()

  void (async () => {
    try {
      const res = await fetch(`${API_BASE}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
        signal: ctrl.signal,
      })

      if (!res.ok || !res.body) {
        onError(`Search request failed: ${res.status}`)
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""
      let gotDone = false

      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split("\n")
        buffer = lines.pop() ?? ""

        for (const line of lines) {
          if (!line.startsWith("data:")) continue
          const raw = line.slice(5).trim()
          if (!raw) continue
          try {
            const event = JSON.parse(raw) as { type: string; [k: string]: unknown }
            if (event.type === "part") onPart(event as unknown as SearchResultPart)
            else if (event.type === "clarify") onClarify(event.question as string)
            else if (event.type === "done") { gotDone = true; onDone(); return }
            else if (event.type === "error") { onError(event.message as string); return }
          } catch {
            // skip malformed SSE lines
          }
        }
      }
      // Stream closed without a clean [DONE] — network drop or server crash
      if (gotDone) onDone()
      else onError("Connection lost — search results may be incomplete")
    } catch (err) {
      if ((err as Error).name !== "AbortError") onError(String(err))
    }
  })()

  return ctrl
}
