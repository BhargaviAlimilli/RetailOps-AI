import { afterEach, describe, expect, it, vi } from 'vitest'
import { streamMessage } from '../services/conversations'
const conversation = '11111111-1111-4111-8111-111111111111',
  request = '22222222-2222-4222-8222-222222222222',
  message = '33333333-3333-4333-8333-333333333333'
function event(
  sequence: number,
  type: string,
  payload: Record<string, unknown>,
  messageId = message,
) {
  return `id: ${messageId}:${sequence}\nevent: ${type}\ndata: ${JSON.stringify({ conversation_id: conversation, request_id: request, message_id: messageId, sequence, payload })}\n\n`
}
function mockStream(text: string) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(text, {
        headers: { 'Content-Type': 'text/event-stream' },
      }),
    ),
  )
}
afterEach(() => vi.unstubAllGlobals())
describe('conversation stream contract', () => {
  it('deduplicates delta replay and requires a terminal event', async () => {
    mockStream(
      event(0, 'message.started', {}) +
        event(1, 'message.delta', { text: 'Saved response' }) +
        event(1, 'message.delta', { text: 'Saved response' }) +
        event(2, 'message.completed', { content: 'Saved response' }),
    )
    const handler = vi.fn()
    await streamMessage(
      conversation,
      'Prompt',
      request,
      new AbortController().signal,
      handler,
    )
    expect(handler.mock.calls.map((call) => call[0].type)).toEqual([
      'message.started',
      'message.delta',
      'message.completed',
    ])
    mockStream(event(0, 'message.started', {}))
    await expect(
      streamMessage(
        conversation,
        'Prompt',
        request,
        new AbortController().signal,
        handler,
      ),
    ).rejects.toThrow('before the reply was complete')
  })
  it('rejects a changed message identity', async () => {
    mockStream(
      event(0, 'message.started', {}) +
        event(
          1,
          'message.completed',
          {},
          '44444444-4444-4444-8444-444444444444',
        ),
    )
    await expect(
      streamMessage(
        conversation,
        'Prompt',
        request,
        new AbortController().signal,
        vi.fn(),
      ),
    ).rejects.toThrow('identity changed')
  })
  it('has a 150 second deadline even after headers arrive', async () => {
    const signal = new AbortController()
    const timeout = vi
      .spyOn(AbortSignal, 'timeout')
      .mockReturnValue(signal.signal)
    const cancel = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(new ReadableStream({ cancel }), {
          headers: { 'Content-Type': 'text/event-stream' },
        }),
      ),
    )
    const promise = streamMessage(
      conversation,
      'Prompt',
      request,
      new AbortController().signal,
      vi.fn(),
    )
    await Promise.resolve()
    signal.abort(new DOMException('Timed out', 'TimeoutError'))
    await expect(promise).rejects.toMatchObject({ name: 'TimeoutError' })
    expect(timeout).toHaveBeenCalledWith(150000)
    timeout.mockRestore()
  })
})
