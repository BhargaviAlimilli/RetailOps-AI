import { describe, expect, it, vi } from 'vitest'
import { z } from 'zod'
import { ApiError, getJson } from '../lib/api'

const schema = z.object({ status: z.literal('ok') })

describe('typed API client', () => {
  it('rejects malformed responses rather than trusting casts', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ status: 'invented' })),
        ),
    )
    await expect(getJson('/api/v1/health', schema)).rejects.toBeInstanceOf(
      ApiError,
    )
  })
  it('keeps error bodies private and preserves request identity', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response('private driver detail', {
          status: 503,
          headers: { 'X-Request-ID': 'request-1' },
        }),
      ),
    )
    try {
      await getJson('/api/v1/ready', schema)
      expect.fail('Expected unavailable error')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect(error).toMatchObject({ status: 503, requestId: 'request-1' })
      expect(String(error)).not.toContain('private')
    }
  })
  it('passes cancellation to fetch', async () => {
    const controller = new AbortController()
    controller.abort()
    const fetchMock = vi.fn((_path, options: RequestInit) => {
      expect(options.signal?.aborted).toBe(true)
      return Promise.reject(new DOMException('Cancelled', 'AbortError'))
    })
    vi.stubGlobal('fetch', fetchMock)
    await expect(
      getJson('/api/v1/health', schema, controller.signal),
    ).rejects.toMatchObject({ name: 'AbortError' })
  })
})
