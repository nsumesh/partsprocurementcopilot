import { Component } from "react"
import type { ErrorInfo, ReactNode } from "react"

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Uncaught error:", error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-zinc-950 flex items-center justify-center px-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-3xl shadow-2xl shadow-black/60 p-8 w-full max-w-md text-center">
            <h1 className="text-xl font-bold text-white mb-2">Something went wrong</h1>
            <p className="text-sm text-zinc-400 mb-6">
              An unexpected error occurred. Reload the page to continue.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-3 bg-orange-500 text-white text-sm font-bold rounded-xl hover:bg-orange-400 active:scale-[0.98] transition-all shadow-lg shadow-orange-500/20"
            >
              Reload page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
