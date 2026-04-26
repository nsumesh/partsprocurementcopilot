export type FitmentConfidence =
  | "High Probability"
  | "Medium Probability"
  | "Low Probability"
  | "No Fitment"

export interface Part {
  id: string
  part_number: string
  name: string
  description: string | null
  category: string
  source: string
  brand: string | null
  price_usd: number | null
  fit_notes: Record<string, unknown>
  attributes: Record<string, unknown>
  vendor_urls: Array<{ vendor: string; url: string }>
}

export interface FitmentResult {
  confidence: FitmentConfidence
  reasoning: string
}

export interface SearchResultPart {
  type: "part"
  index: number
  part: Part
  fitment: FitmentResult
}

export interface VINSpec {
  vin: string
  make: string | null
  model: string | null
  year: number | null
  engine: string | null
  gvwr: string | null
}

export interface Order {
  id: string
  part_id: string | null
  part_number: string
  part_name: string
  quantity: number
  vin: string | null
  query: string | null
  urgency: "standard" | "urgent"
  created_at: string
}

export interface OrderCreate {
  part_id: string
  part_number: string
  part_name: string
  quantity: number
  vin?: string
  query?: string
  urgency?: "standard" | "urgent"
}
