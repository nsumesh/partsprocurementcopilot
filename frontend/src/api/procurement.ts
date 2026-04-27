import { apiGet, apiPost } from "./client"
import type { ProcurementJob, ProcurementJobCreate } from "../types"

export const createProcurementJob = (body: ProcurementJobCreate) =>
  apiPost<ProcurementJob>("/procurement/jobs", body)

export const getProcurementJobs = () =>
  apiGet<ProcurementJob[]>("/procurement/jobs")

export const getProcurementJob = (id: string) =>
  apiGet<ProcurementJob>(`/procurement/jobs/${id}`)

export const sendOutreach = (id: string) =>
  apiPost<ProcurementJob>(`/procurement/jobs/${id}/send`, {})

export const sendFollowup = (id: string, follow_up_email?: string) =>
  apiPost<ProcurementJob>(`/procurement/jobs/${id}/followup`, { follow_up_email })

export const confirmParsedFields = (id: string) =>
  apiPost<ProcurementJob>(`/procurement/jobs/${id}/confirm`, {})

export const acceptJob = (id: string) =>
  apiPost<ProcurementJob>(`/procurement/jobs/${id}/accept`, {})

export const rejectJob = (id: string) =>
  apiPost<ProcurementJob>(`/procurement/jobs/${id}/reject`, {})
