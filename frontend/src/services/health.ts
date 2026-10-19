import { useQuery } from '@tanstack/react-query'
import { z } from 'zod'
import { getJson } from '../lib/api'
import { selectUser, useAppSelector } from '../store'

const healthSchema = z.object({
  status: z.literal('ok'),
  service: z.literal('retailops-api'),
})
const readinessSchema = z.object({
  status: z.literal('ready'),
  service: z.literal('retailops-api'),
})

export function useHealth() {
  return useQuery({
    queryKey: ['system', 'health'],
    queryFn: ({ signal }) => getJson('/api/v1/health', healthSchema, signal),
    refetchInterval: 30_000,
  })
}

export function useReadiness() {
  return useQuery({
    queryKey: ['system', 'readiness'],
    queryFn: ({ signal }) => getJson('/api/v1/ready', readinessSchema, signal),
    retry: false,
    refetchInterval: 30_000,
  })
}

const aiStatusSchema = z.object({
  provider: z.enum(['disabled', 'gemini']),
  configured: z.boolean(),
  model: z.string().nullable(),
  operational_tools: z.boolean(),
})
export function useAIStatus() {
  const user = useAppSelector(selectUser)
  return useQuery({
    queryKey: ['system', 'ai', user?.id],
    queryFn: ({ signal }) =>
      getJson('/api/v1/ai/status', aiStatusSchema, signal),
    enabled: Boolean(user),
    retry: false,
  })
}
