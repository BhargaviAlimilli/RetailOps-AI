import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { knowledge, validateDocumentFile } from '../services/knowledge'
import { DocumentUpload } from '../features/documents/DocumentUpload'
import { sessionCleared, sessionEstablished, store } from '../store'
afterEach(() => {
  vi.unstubAllGlobals()
  store.dispatch(sessionCleared())
})
describe('document multipart upload', () => {
  it('uploads the original filename and UTF-8 file with bearer auth and browser-owned multipart headers', async () => {
    store.dispatch(
      sessionEstablished({
        access_token: 'unit-test-session',
        token_type: 'bearer',
        user: {
          id: '11111111-1111-4111-8111-111111111111',
          email: 'person@example.com',
          name: 'Person',
          role: 'analyst',
        },
      }),
    )
    const fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: '11111111-1111-4111-8111-111111111111',
          title: 'Private policy',
          status: 'ready',
          created_at: '2026-10-19T00:00:00Z',
          chunk_count: 1,
          format: 'markdown',
        }),
      ),
    )
    vi.stubGlobal('fetch', fetch)
    await knowledge.upload({
      title: 'Private policy',
      file: new File(['# UTF-8 policy\nReturn unused goods.'], 'policy.md', {
        type: 'text/markdown',
      }),
    })
    expect(fetch).toHaveBeenCalledOnce()
    const [path, options] = fetch.mock.calls[0]!
    expect(path).toBe('/api/v1/documents/upload')
    expect(options.body).toBeInstanceOf(FormData)
    const body = options.body as FormData
    expect(body.get('title')).toBe('Private policy')
    expect((body.get('file') as File).name).toBe('policy.md')
    expect(new Headers(options.headers).get('Authorization')).toBe(
      'Bearer unit-test-session',
    )
    expect(new Headers(options.headers).has('Content-Type')).toBe(false)
  })
  it('blocks oversized files in the UI without a request', async () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    render(
      <QueryClientProvider client={new QueryClient()}>
        <DocumentUpload />
      </QueryClientProvider>,
    )
    await userEvent.type(screen.getByLabelText('File title'), 'Too large')
    await userEvent.upload(
      screen.getByLabelText('Document file'),
      new File([new Uint8Array(100001)], 'large.txt', { type: 'text/plain' }),
    )
    expect(screen.getByRole('alert')).toHaveTextContent('100,000 byte limit')
    expect(
      screen.getByRole('button', { name: 'Upload and index file' }),
    ).toBeDisabled()
    expect(fetch).not.toHaveBeenCalled()
  })
  it('rejects unsupported extensions and malformed UTF-8 before sending', async () => {
    await expect(
      validateDocumentFile(new File(['text'], 'policy.pdf')),
    ).rejects.toThrow('not supported')
    await expect(
      validateDocumentFile(
        new File([new Uint8Array([0xff, 0xfe, 0x80])], 'policy.txt'),
      ),
    ).rejects.toThrow('valid UTF-8')
  })
})
