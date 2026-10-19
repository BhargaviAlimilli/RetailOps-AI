import { z } from 'zod'

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

// This client accepts same-origin paths only; provider secrets never belong in the browser.
export async function getJson<T>(
  path: `/api/${string}`,
  schema: z.ZodType<T>,
  signal?: AbortSignal,
): Promise<T> {
  if (!path.startsWith('/api/') || path.includes('://')) {
    throw new Error('Expected a same-origin API path')
  }
  const timeoutSignal = AbortSignal.timeout(8_000)
  const response = await fetch(path, {
    signal: signal ? AbortSignal.any([signal, timeoutSignal]) : timeoutSignal,
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new ApiError(
      response.status === 503
        ? 'Service is not ready.'
        : 'The request could not be completed.',
      response.status,
      response.headers.get('X-Request-ID'),
    )
  }
  return schema.parse(await response.json())
}
