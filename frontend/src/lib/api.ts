import { z } from 'zod'
import { getAccessToken, sessionCleared, store } from '../store'

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly requestId: string | null,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}
export type ApiRequestOptions = RequestInit & { timeoutMs?: number }
async function request(
  path: `/api/${string}`,
  options: ApiRequestOptions = {},
) {
  const { timeoutMs = 8_000, ...fetchOptions } = options
  if (!path.startsWith('/api/') || path.includes('://') || path.includes('\\'))
    throw new Error('Expected a same-origin API path')
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  if (options.body && !(options.body instanceof FormData))
    headers.set('Content-Type', 'application/json')
  const token = getAccessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const timeout = AbortSignal.timeout(timeoutMs)
  let response: Response
  try {
    response = await fetch(path, {
      ...fetchOptions,
      headers,
      signal: options.signal
        ? AbortSignal.any([options.signal, timeout])
        : timeout,
    })
  } catch (error) {
    if (options.signal?.aborted) throw error
    throw new ApiError(
      'Unable to reach the service. Please try again.',
      0,
      null,
    )
  }
  if (!response.ok) {
    if (response.status === 401 && token) store.dispatch(sessionCleared())
    const messages: Record<number, string> = {
      401: 'Your email or password is incorrect, or your session has expired.',
      403: 'You do not have permission to perform this action.',
      409: 'This action conflicts with an existing record. Refresh and try again.',
      422: 'Please check the submitted values.',
      429: 'Too many attempts. Please try again later.',
      503: 'Service is not ready.',
    }
    throw new ApiError(
      messages[response.status] ?? 'The request could not be completed.',
      response.status,
      response.headers.get('X-Request-ID'),
    )
  }
  return response
}
export async function apiRequest<T>(
  path: `/api/${string}`,
  schema: z.ZodType<T>,
  options?: ApiRequestOptions,
): Promise<T> {
  const response = await request(path, options)
  try {
    return schema.parse(await response.json())
  } catch {
    throw new ApiError(
      'The service returned an unexpected response.',
      response.status,
      response.headers.get('X-Request-ID'),
    )
  }
}
export const requestJson = apiRequest
export function getJson<T>(
  path: `/api/${string}`,
  schema: z.ZodType<T>,
  signal?: AbortSignal,
): Promise<T> {
  return apiRequest(path, schema, { signal })
}
export async function requestVoid(
  path: `/api/${string}`,
  options?: ApiRequestOptions,
): Promise<void> {
  await request(path, options)
}
