export interface ServerEvent {
  id: string
  event: string
  data: string
}
/** Incremental SSE decoding: UTF-8, CRLF, comments, multiline data, and replay IDs. */
export async function consumeSSE(
  response: Response,
  onEvent: (event: ServerEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (!response.body)
    throw new Error('The service returned no response stream.')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const seen = new Set<string>()
  let buffer = '',
    event = '',
    id = '',
    data: string[] = []
  function line(value: string) {
    if (!value) {
      if (data.length && (!id || !seen.has(id))) {
        signal?.throwIfAborted()
        if (id) seen.add(id)
        onEvent({ id, event: event || 'message', data: data.join('\n') })
      }
      event = ''
      id = ''
      data = []
      return
    }
    if (value.startsWith(':')) return
    const colon = value.indexOf(':')
    const field = colon < 0 ? value : value.slice(0, colon)
    let content = colon < 0 ? '' : value.slice(colon + 1)
    if (content.startsWith(' ')) content = content.slice(1)
    if (field === 'data') data.push(content)
    if (field === 'event') event = content
    if (field === 'id' && !content.includes('\0')) id = content
  }
  function flush(final = false) {
    let start = 0
    for (let i = 0; i < buffer.length; i++) {
      if (buffer[i] !== '\r' && buffer[i] !== '\n') continue
      if (buffer[i] === '\r' && i === buffer.length - 1 && !final) break
      line(buffer.slice(start, i))
      if (buffer[i] === '\r' && buffer[i + 1] === '\n') i++
      start = i + 1
    }
    buffer = buffer.slice(start)
    if (final && buffer) {
      line(buffer)
      buffer = ''
    }
  }
  const cancel = () => {
    void reader.cancel().catch(() => {})
  }
  signal?.addEventListener('abort', cancel, { once: true })
  try {
    while (true) {
      signal?.throwIfAborted()
      const { done, value } = await reader.read()
      signal?.throwIfAborted()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      flush()
    }
    buffer += decoder.decode()
    flush(true)
  } finally {
    signal?.removeEventListener('abort', cancel)
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}
