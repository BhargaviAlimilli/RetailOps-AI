import { describe, expect, it, vi } from 'vitest'
import { consumeSSE } from '../features/assistant/sse'

function response(text: string) {
  const bytes = new TextEncoder().encode(text)
  return new Response(
    new ReadableStream({
      start(controller) {
        for (const byte of bytes) controller.enqueue(new Uint8Array([byte]))
        controller.close()
      },
    }),
  )
}
describe('SSE decoding', () => {
  it('preserves split UTF-8, CRLF, multiline data, comments and replay deduplication', async () => {
    const events: unknown[] = []
    await consumeSSE(
      response(
        ': heartbeat\r\nid: abc:1\r\nevent: message.delta\r\ndata: {"text":"\u20b9 caf\u00e9 \ud83d\uded2",\r\ndata: "more":true}\r\n\r\nid: abc:1\nevent: message.delta\ndata: duplicate\n\nid: abc:2\nevent: message.completed\ndata: {}\n\n',
      ),
      (event) => events.push(event),
    )
    expect(events).toEqual([
      {
        id: 'abc:1',
        event: 'message.delta',
        data: '{"text":"\u20b9 caf\u00e9 \ud83d\uded2",\n"more":true}',
      },
      { id: 'abc:2', event: 'message.completed', data: '{}' },
    ])
  })
  it('cancels and releases the reader when stopped', async () => {
    const cancel = vi.fn()
    const controller = new AbortController()
    const stream = new ReadableStream({
      start(source) {
        source.enqueue(new TextEncoder().encode('data: waiting\n\n'))
      },
      cancel,
    })
    const reading = consumeSSE(
      new Response(stream),
      () => controller.abort(),
      controller.signal,
    )
    await expect(reading).rejects.toMatchObject({ name: 'AbortError' })
    expect(cancel).toHaveBeenCalledOnce()
    expect(stream.locked).toBe(false)
  })
  it('stops dispatching buffered events immediately after abort', async () => {
    const controller = new AbortController()
    const event = vi.fn(() => controller.abort())
    const body = new TextEncoder().encode('data: one\n\ndata: two\n\n')
    const stream = new ReadableStream({
      start(source) {
        source.enqueue(body)
        source.close()
      },
    })
    await expect(
      consumeSSE(new Response(stream), event, controller.signal),
    ).rejects.toMatchObject({ name: 'AbortError' })
    expect(event).toHaveBeenCalledOnce()
  })
  it('does not dispatch incomplete SSE frames', async () => {
    const event = vi.fn()
    await consumeSSE(response('data: incomplete'), event)
    expect(event).not.toHaveBeenCalled()
  })
})
