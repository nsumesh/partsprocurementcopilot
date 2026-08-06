import { API_BASE } from "./client"
import type { SearchResultPart } from "../types"

export interface SearchRequest {
  vin: string
  query: string
  urgency: "standard" | "urgent"
  urgency_deadline?: string | null
}

// Abort the stream if no chunk arrives for this long (backend stall guard)
const INACTIVITY_TIMEOUT_MS = 60_000

export function streamSearch(
  request: SearchRequest,
  onPart: (p: SearchResultPart) => void,
  onClarify: (question: string) => void,
  onDone: () => void,
  onError: (message: string) => void,
): AbortController {
  const ctrl = new AbortController()

  void (async () => {
    let timedOut = false
    let watchdog: ReturnType<typeof setTimeout> | undefined
    const resetWatchdog = () => {
      if (watchdog !== undefined) clearTimeout(watchdog)
      watchdog = setTimeout(() => {
        timedOut = true
        ctrl.abort()
      }, INACTIVITY_TIMEOUT_MS)
    }

    try {
      resetWatchdog()
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
      let sawTerminal = false

      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        resetWatchdog()
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
            else if (event.type === "clarify") { sawTerminal = true; onClarify(event.question as string) }
            else if (event.type === "done") { onDone(); return }
            else if (event.type === "error") { onError(event.message as string); return }
          } catch {
            // skip malformed SSE lines
          }
        }
      }
      // Stream closed without a done/clarify/error event — network drop or server crash
      if (!sawTerminal) onError("Connection lost — search results may be incomplete")
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        // Watchdog abort is an error; caller-initiated abort is intentional and silent
        if (timedOut) onError("Search timed out")
      } else {
        onError(String(err))
      }
    } finally {
      if (watchdog !== undefined) clearTimeout(watchdog)
    }
  })()

  return ctrl
}
