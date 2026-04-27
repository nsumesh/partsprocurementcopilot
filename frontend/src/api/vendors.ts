import { apiGet } from "./client"
import type { VendorPart } from "../types"

export const getVendorsForPart = (part_id: string) =>
  apiGet<VendorPart[]>(`/vendors/part/${part_id}`)
