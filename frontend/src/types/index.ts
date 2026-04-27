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

// --- Vendor Outreach ---

export interface Vendor {
  id: string
  name: string
  email: string
  region: string
  type: string
  brands_carried: string[]
  response_rate: number
}

export interface VendorPart {
  id: string
  vendor_id: string
  part_id: string
  list_price: number | null
  delivery_estimate: string | null
  delivery_hours: number | null
  in_stock: boolean
  vendor: Vendor | null
}

export type JobStatus =
  | "created"
  | "outreach_sent"
  | "response_received"
  | "parsed"
  | "follow_up_required"
  | "follow_up_sent"
  | "confirmed"
  | "ranked"
  | "accepted"
  | "rejected"

export interface ProcurementEvent {
  id: string
  job_id: string
  from_status: string | null
  to_status: string
  actor: string
  metadata: Record<string, unknown>
  created_at: string
}

export interface ProcurementJob {
  id: string
  part_id: string
  vendor_id: string
  part_number: string
  part_name: string
  vin: string
  query: string
  urgency: string
  urgency_deadline: string | null
  status: JobStatus
  outreach_email: string | null
  response_email: string | null
  follow_up_email: string | null
  parsed_availability: string | null
  parsed_unit_price: number | null
  parsed_quantity_available: number | null
  parsed_delivery_date: string | null
  parsed_delivery_hours: number | null
  ranking_score: number | null
  respond_at: string | null
  created_at: string
  updated_at: string | null
  vendor: Vendor | null
  events: ProcurementEvent[]
}

export interface ProcurementJobCreate {
  part_id: string
  vendor_id: string
  part_number: string
  part_name: string
  vin: string
  query: string
  urgency: "standard" | "urgent"
  urgency_deadline?: string | null
}
