import { z } from 'zod'
import { apiRequest, getJson } from '../lib/api'

const money = z.string().regex(/^-?\d+(\.\d+)?$/)
const id = z.string().uuid()
export const storeSchema = z.object({ id, name: z.string(), code: z.string() })
export const categorySchema = z.object({ id, name: z.string() })
export const productSchema = z.object({
  id,
  sku: z.string(),
  name: z.string(),
  category_id: id,
  category_name: z.string(),
  unit_cost: money,
  unit_price: money,
})
export const inventorySchema = z.object({
  id,
  product_id: id,
  store_id: id,
  product_name: z.string(),
  sku: z.string(),
  store_name: z.string(),
  on_hand: z.number().int(),
  reserved: z.number().int(),
  available: z.number().int(),
  reorder_point: z.number().int(),
  safety_stock: z.number().int(),
  unit_cost: money,
})
export const supplierSchema = z.object({
  id,
  name: z.string(),
  email: z.string(),
  lead_time_days: z.number(),
  terms: z.array(
    z.object({
      product_id: id,
      product_name: z.string(),
      supplier_product_code: z.string(),
      cost: money,
      minimum_order_quantity: z.number(),
      pack_size: z.number(),
      lead_time_days: z.number(),
    }),
  ),
})
const activity = z.object({
  id,
  action: z.string(),
  created_at: z.string(),
  actor_name: z.string(),
})
const rankedProduct = z.object({
  id,
  name: z.string(),
  sku: z.string(),
  quantity: z.number(),
  revenue: money,
})
export const dashboardSchema = z.object({
  currency: z.literal('INR'),
  revenue: money,
  gross_profit: money,
  gross_margin: money,
  order_count: z.number(),
  average_order_value: money,
  revenue_change_percent: money.nullable(),
  low_stock_count: z.number(),
  out_of_stock_count: z.number(),
  inventory_valuation: money,
  pending_purchase_orders: z.number(),
  trend: z.array(
    z.object({
      date: z.string(),
      revenue: money,
      gross_profit: money,
      order_count: z.number(),
    }),
  ),
  by_store: z.array(
    z.object({ name: z.string(), revenue: money, order_count: z.number() }),
  ),
  by_category: z.array(z.object({ name: z.string(), revenue: money })),
  top_products: z.array(rankedProduct),
  slow_products: z.array(rankedProduct),
  recent_activity: z.array(activity),
})
export const saleSchema = z.object({
  id,
  store_name: z.string(),
  sold_at: z.string(),
  total: money,
  gross_profit: money,
  item_count: z.number(),
})
export const purchaseOrderSchema = z.object({
  id,
  store_id: id,
  store_name: z.string(),
  supplier_id: id,
  supplier_name: z.string(),
  status: z.enum(['draft', 'pending', 'approved', 'rejected', 'received']),
  total: money,
  created_at: z.string(),
  items: z.array(
    z.object({
      product_id: id,
      product_name: z.string(),
      quantity: z.number(),
      unit_cost: money,
      line_total: money,
    }),
  ),
  approvals: z.array(
    z.object({
      id,
      decision: z.string(),
      reason: z.string().nullable(),
      actor_name: z.string(),
      created_at: z.string(),
    }),
  ),
})
export const pageSchema = <T extends z.ZodType>(item: T) =>
  z.object({
    items: z.array(item),
    total: z.number().int(),
    page: z.number().int(),
    page_size: z.number().int(),
  })
export type Product = z.infer<typeof productSchema>
export type Inventory = z.infer<typeof inventorySchema>
export type PurchaseOrder = z.infer<typeof purchaseOrderSchema>
export type Filters = Record<string, string | number | undefined>
export function queryString(filters: Filters) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value))
  })
  return params.size ? `?${params}` : ''
}
const read = <T>(path: string, schema: z.ZodType<T>, signal?: AbortSignal) =>
  getJson(`/api/v1/${path}`, schema, signal)
export const retail = {
  stores: (signal?: AbortSignal) =>
    read('stores', z.array(storeSchema), signal),
  categories: (signal?: AbortSignal) =>
    read('categories', z.array(categorySchema), signal),
  suppliers: (signal?: AbortSignal) =>
    read('suppliers', z.array(supplierSchema), signal),
  products: (filters: Filters, signal?: AbortSignal) =>
    read(`products${queryString(filters)}`, pageSchema(productSchema), signal),
  product: (productId: string, signal?: AbortSignal) =>
    read(`products/${productId}`, productSchema, signal),
  inventory: (filters: Filters, signal?: AbortSignal) =>
    read(
      `inventory${queryString(filters)}`,
      pageSchema(inventorySchema),
      signal,
    ),
  dashboard: (filters: Filters, signal?: AbortSignal) =>
    read(`dashboard${queryString(filters)}`, dashboardSchema, signal),
  sales: (filters: Filters, signal?: AbortSignal) =>
    read(`sales${queryString(filters)}`, pageSchema(saleSchema), signal),
  orders: (filters: Filters, signal?: AbortSignal) =>
    read(
      `purchase-orders${queryString(filters)}`,
      pageSchema(purchaseOrderSchema),
      signal,
    ),
  movements: (inventoryId: string, signal?: AbortSignal) =>
    read(
      `inventory/${inventoryId}/movements`,
      z.array(
        z.object({
          id,
          delta: z.number(),
          reason: z.string(),
          created_at: z.string(),
          actor_name: z.string(),
        }),
      ),
      signal,
    ),
  adjust: (
    inventoryId: string,
    body: { delta: number; reason: string },
    key: string,
  ) =>
    apiRequest(`/api/v1/inventory/${inventoryId}/adjust`, inventorySchema, {
      method: 'POST',
      headers: { 'Idempotency-Key': key },
      body: JSON.stringify(body),
    }),
  createOrder: (
    body: {
      store_id: string
      supplier_id: string
      items: { product_id: string; quantity: number }[]
    },
    key: string,
  ) =>
    apiRequest('/api/v1/purchase-orders', purchaseOrderSchema, {
      method: 'POST',
      headers: { 'Idempotency-Key': key },
      body: JSON.stringify(body),
    }),
  transition: (
    orderId: string,
    action: 'submit' | 'approve' | 'reject' | 'receive',
    reason: string,
    key: string,
  ) =>
    apiRequest(
      `/api/v1/purchase-orders/${orderId}/${action}`,
      purchaseOrderSchema,
      {
        method: 'POST',
        headers: { 'Idempotency-Key': key },
        body: JSON.stringify({ reason }),
      },
    ),
}
export const formatMoney = (value: string | number) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(Number(value))
export const formatDate = (value: string) =>
  new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' }).format(
    new Date(value),
  )
