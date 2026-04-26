import { apiGet, apiPost } from "./client"
import type { Order, OrderCreate } from "../types"

export const getOrders = () => apiGet<Order[]>("/orders")
export const createOrder = (body: OrderCreate) => apiPost<Order>("/orders", body)
