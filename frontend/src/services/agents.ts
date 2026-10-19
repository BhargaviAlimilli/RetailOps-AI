import { z } from 'zod'
import { citationSchema } from './knowledge'
import { apiRequest } from '../lib/api'
export const runSchema = z.object({
  id: z.string().uuid(),
  status: z.enum([
    'running',
    'awaiting_approval',
    'approved',
    'rejected',
    'error',
  ]),
  purchase_order_id: z.string().uuid().nullable(),
  proposal: z
    .object({
      store_name: z.string(),
      product_name: z.string(),
      supplier_name: z.string(),
      quantity: z.number(),
      unit_cost: z.string(),
      total: z.string(),
      reason: z.string(),
      citations: z.array(citationSchema).optional(),
    })
    .nullable(),
  steps: z.array(
    z.object({ name: z.string(), status: z.string(), detail: z.string() }),
  ),
  error: z.string().nullable().optional(),
  created_at: z.string(),
})
export type AgentRun = z.infer<typeof runSchema>
export const agents = {
  resume: (id: string) =>
    apiRequest(`/api/v1/agents/runs/${id}/resume`, runSchema, {
      method: 'POST',
      timeoutMs: 120000,
    }),
  list: () => apiRequest('/api/v1/agents/runs', z.array(runSchema)),
  create: (body: {
    store_id: string
    product_id: string
    supplier_id: string
    request_id: string
  }) =>
    apiRequest('/api/v1/agents/runs', runSchema, {
      method: 'POST',
      timeoutMs: 120000,
      body: JSON.stringify(
        z
          .object({
            store_id: z.string().uuid(),
            product_id: z.string().uuid(),
            supplier_id: z.string().uuid(),
            request_id: z.string().uuid(),
          })
          .parse(body),
      ),
    }),
  decide: (
    id: string,
    body: {
      decision: 'approve' | 'reject'
      reason: string
      idempotency_key: string
    },
  ) =>
    apiRequest(`/api/v1/agents/runs/${id}/decision`, runSchema, {
      method: 'POST',
      timeoutMs: 120000,
      body: JSON.stringify(
        z
          .object({
            decision: z.enum(['approve', 'reject']),
            reason: z.string().trim().min(5).max(500),
            idempotency_key: z.string().uuid(),
          })
          .parse(body),
      ),
    }),
}
