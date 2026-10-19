import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AssistantPage from '../features/assistant/AssistantPage'
import { conversations, streamMessage } from '../services/conversations'
vi.mock('../services/conversations', () => ({
  conversations: { list: vi.fn(), create: vi.fn(), messages: vi.fn() },
  streamMessage: vi.fn(),
}))
const conversationId = '11111111-1111-4111-8111-111111111111'
function setup() {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
          },
        })
      }
    >
      <AssistantPage />
    </QueryClientProvider>,
  )
}
beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(conversations.list).mockResolvedValue([])
  vi.mocked(conversations.create).mockResolvedValue({
    id: conversationId,
    title: 'New conversation',
    created_at: '2026-10-19T00:00:00Z',
    updated_at: '2026-10-19T00:00:00Z',
  })
  vi.mocked(conversations.messages).mockResolvedValue([])
  Element.prototype.scrollTo = vi.fn()
})
describe('assistant stream recovery', () => {
  it('stops an active stream and retries the same request to recover without duplicating turns', async () => {
    vi.mocked(streamMessage).mockImplementation(
      (_conversation, _content, _id, signal) =>
        new Promise((_resolve, reject) =>
          signal.addEventListener('abort', () =>
            reject(new DOMException('Stopped', 'AbortError')),
          ),
        ),
    )
    setup()
    await userEvent.type(screen.getByRole('textbox'), 'Help plan inventory')
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }))
    await screen.findByRole('button', { name: 'Stop' })
    const requestId = vi.mocked(streamMessage).mock.calls[0]?.[2]
    await userEvent.click(screen.getByRole('button', { name: 'Stop' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Reply stopped')
    vi.mocked(streamMessage).mockRejectedValue(
      new Error('Transport unavailable'),
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Recover saved reply' }),
    )
    await waitFor(() => expect(streamMessage).toHaveBeenCalledTimes(2))
    expect(vi.mocked(streamMessage).mock.calls[1]?.[2]).toBe(requestId)
    await screen.findByText('Transport unavailable')
    await userEvent.click(
      screen.getByRole('button', { name: 'Try a new reply' }),
    )
    await waitFor(() => expect(streamMessage).toHaveBeenCalledTimes(3))
    expect(vi.mocked(streamMessage).mock.calls[2]?.[2]).not.toBe(requestId)
  })
  it('blocks duplicate sends and never starts a stream after unmount during conversation creation', async () => {
    let resolveCreate!: (
      value: Awaited<ReturnType<typeof conversations.create>>,
    ) => void
    vi.mocked(conversations.create).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveCreate = resolve
        }),
    )
    const view = setup()
    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Pending creation' },
    })
    const form = screen.getByRole('textbox').closest('form')!
    fireEvent.submit(form)
    fireEvent.submit(form)
    await waitFor(() => expect(conversations.create).toHaveBeenCalledOnce())
    view.unmount()
    await act(async () =>
      resolveCreate({
        id: conversationId,
        title: 'New conversation',
        created_at: '2026-10-19T00:00:00Z',
        updated_at: '2026-10-19T00:00:00Z',
      }),
    )
    expect(streamMessage).not.toHaveBeenCalled()
  })
  it('labels replies that reached the model output limit', async () => {
    vi.mocked(streamMessage).mockImplementation(
      async (_conversation, _content, requestId, _signal, onEvent) => {
        onEvent({
          type: 'message.completed',
          conversation_id: conversationId,
          message_id: '33333333-3333-4333-8333-333333333333',
          request_id: requestId,
          sequence: 1,
          payload: {
            content: 'A partial explanation',
            finish_reason: 'MAX_TOKENS',
          },
        })
      },
    )
    setup()
    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Explain purchasing' },
    })
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }))
    expect(
      await screen.findByText(
        'Reply reached the output limit. Ask a follow-up question to continue.',
      ),
    ).toBeInTheDocument()
  })
  it('labels an output-limited reply loaded from persisted history', async () => {
    vi.mocked(conversations.list).mockResolvedValue([
      {
        id: conversationId,
        title: 'Saved conversation',
        created_at: '2026-10-19T00:00:00Z',
        updated_at: '2026-10-19T00:00:00Z',
      },
    ])
    vi.mocked(conversations.messages).mockResolvedValue([
      {
        id: '33333333-3333-4333-8333-333333333333',
        conversation_id: conversationId,
        request_id: '22222222-2222-4222-8222-222222222222',
        role: 'assistant',
        content: 'Saved limited output',
        status: 'completed',
        created_at: '2026-10-19T00:00:00Z',
        updated_at: '2026-10-19T00:00:00Z',
        usage: null,
        error_code: null,
        finish_reason: 'MAX_TOKENS',
      },
    ])
    setup()
    await userEvent.click(
      await screen.findByRole('button', { name: 'Saved conversation' }),
    )
    expect(
      await screen.findByText(
        'Reply reached the output limit. Ask a follow-up question to continue.',
      ),
    ).toBeInTheDocument()
    expect(streamMessage).not.toHaveBeenCalled()
  })
  it('keeps provider configuration failures honest and offers recovery', async () => {
    vi.mocked(streamMessage).mockRejectedValue(
      new Error(
        'AI Companion is unavailable. Ask your administrator to configure the Gemini integration.',
      ),
    )
    setup()
    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Investigate low stock' },
    })
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'configure the Gemini integration',
    )
    expect(
      screen.getByRole('button', { name: 'Recover saved reply' }),
    ).toBeEnabled()
    expect(screen.queryByText('Receiving reply�')).not.toBeInTheDocument()
  })
})
