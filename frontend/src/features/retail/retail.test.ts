import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  inventorySchema,
  productSchema,
  queryString,
  retail,
} from '../../services/retail'

afterEach(() => vi.unstubAllGlobals())
describe('retail data boundaries', () => {
  it('encodes user searches and omits empty filters', () => {
    expect(
      queryString({
        q: 'rice & oil',
        store_id: '',
        page: 2,
        category_id: undefined,
      }),
    ).toBe('?q=rice+%26+oil&page=2')
  })
  it('rejects numeric money and incomplete inventory from the API', () => {
    expect(
      productSchema.safeParse({
        id: crypto.randomUUID(),
        sku: 'SKU',
        name: 'Product',
        category_id: crypto.randomUUID(),
        category_name: 'Food',
        unit_cost: 10,
        unit_price: '12.00',
      }).success,
    ).toBe(false)
    expect(
      inventorySchema.safeParse({ id: crypto.randomUUID(), on_hand: 4 })
        .success,
    ).toBe(false)
  })
  it('passes abort signals and pagination to the server instead of paging a partial list', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ items: [], total: 41, page: 3, page_size: 20 }),
        ),
      )
    vi.stubGlobal('fetch', fetch)
    const controller = new AbortController()
    expect(
      await retail.products(
        { q: 'rice', page: 3, page_size: 20 },
        controller.signal,
      ),
    ).toEqual({ items: [], total: 41, page: 3, page_size: 20 })
    expect(fetch.mock.calls[0]![0]).toBe(
      '/api/v1/products?q=rice&page=3&page_size=20',
    )
    expect(fetch.mock.calls[0]![1].signal).toBeInstanceOf(AbortSignal)
  })
  it('requires a complete validated response for inventory writes', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ ok: true })))
    vi.stubGlobal('fetch', fetch)
    await expect(
      retail.adjust(
        crypto.randomUUID(),
        { delta: -2, reason: 'Damaged packaging' },
        'request-stable-key',
      ),
    ).rejects.toThrow()
    const options = fetch.mock.calls[0]![1] as RequestInit
    expect(options.method).toBe('POST')
    expect(new Headers(options.headers).get('Idempotency-Key')).toBe(
      'request-stable-key',
    )
    expect(JSON.parse(String(options.body))).toEqual({
      delta: -2,
      reason: 'Damaged packaging',
    })
  })
  it('requests purchase order status and page from the server', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ items: [], total: 102, page: 6, page_size: 20 }),
        ),
      )
    vi.stubGlobal('fetch', fetch)
    expect(
      await retail.orders({ status: 'pending', page: 6, page_size: 20 }),
    ).toEqual({ items: [], total: 102, page: 6, page_size: 20 })
    expect(fetch.mock.calls[0]![0]).toBe(
      '/api/v1/purchase-orders?status=pending&page=6&page_size=20',
    )
  })
})
