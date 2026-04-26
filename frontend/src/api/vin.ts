import { apiGet } from "./client"
import type { VINSpec } from "../types"

export async function decodeVin(vin: string): Promise<VINSpec | null> {
  try {
    return await apiGet<VINSpec>(`/vin/${vin}`)
  } catch {
    return null
  }
}
