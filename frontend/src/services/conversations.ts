import { z } from 'zod'
import { citationSchema } from './knowledge'
import { apiRequest, ApiError } from '../lib/api'
import { getAccessToken, sessionCleared, store } from '../store'
import { consumeSSE } from '../features/assistant/sse'
const id = z.string().uuid()
export const toolTraceSchema = z.object({
  name: z.string(),
  status: z.enum(['completed', 'error']),
})
export type ToolTrace = z.infer<typeof toolTraceSchema>
export const conversationSchema = z.object({
  id,
  title: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
})
export const messageSchema = z.object({
  id,
  conversation_id: id,
  request_id: id,
  role: z.enum(['user', 'assistant']),
  content: z.string(),
  status: z.enum(['pending', 'streaming', 'completed', 'cancelled', 'error']),
  created_at: z.string(),
  updated_at: z.string(),
  error_code: z.string().nullable(),
  finish_reason: z.string().nullable().optional(),
  citations: z.array(citationSchema).nullable().optional(),
  tool_trace: z.array(toolTraceSchema).nullable().optional(),
  usage: z
    .object({
      input_tokens: z.number(),
      output_tokens: z.number(),
      total_tokens: z.number(),
    })
    .nullable(),
})
export type Conversation = z.infer<typeof conversationSchema>
export type Message = z.infer<typeof messageSchema>
const eventSchema = z.object({
  conversation_id: id,
  message_id: id,
  request_id: id,
  sequence: z.number().int().nonnegative(),
  payload: z
    .object({
      text: z.string().optional(),
      content: z.string().optional(),
      message: z.string().optional(),
      code: z.string().optional(),
      finish_reason: z.string().nullable().optional(),
      citations: z.array(citationSchema).nullable().optional(),
      tool_trace: z.array(toolTraceSchema).nullable().optional(),
    })
    .passthrough(),
})
export type ChatEvent = z.infer<typeof eventSchema> & { type: string }
export const conversations = {
  list: () => apiRequest('/api/v1/conversations', z.array(conversationSchema)),
  create: () =>
    apiRequest('/api/v1/conversations', conversationSchema, {
      method: 'POST',
      body: JSON.stringify({}),
    }),
  messages: (conversationId: string) =>
    apiRequest(
      `/api/v1/conversations/${conversationId}/messages`,
      z.array(messageSchema),
    ),
}
export async function streamMessage(
  conversationId: string,
  content: string,
  requestId: string,
  signal: AbortSignal,
  onEvent: (event: ChatEvent) => void,
) {
  const streamSignal = AbortSignal.any([signal, AbortSignal.timeout(150_000)])
  const response = await fetch(
    `/api/v1/conversations/${conversationId}/messages`,
    {
      method: 'POST',
      signal: streamSignal,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        Authorization: `Bearer ${getAccessToken() ?? ''}`,
      },
      body: JSON.stringify({ content, request_id: requestId }),
    },
  )
  if (!response.ok) {
    if (response.status === 401) store.dispatch(sessionCleared())
    throw new ApiError(
      response.status === 503
        ? 'AI Companion is unavailable. Ask your administrator to configure the Gemini integration.'
        : response.status === 409
          ? 'This request is still active or conflicts with an earlier request. Refresh history before trying again.'
          : 'Your message could not be sent. Please try again.',
      response.status,
      response.headers.get('X-Request-ID'),
    )
  }
  if (!response.headers.get('Content-Type')?.includes('text/event-stream'))
    throw new Error('The service returned an unexpected response format.')
  let terminal = false
  let messageId: string | undefined
  const sequences = new Set<number>()
  await consumeSSE(
    response,
    (event) => {
      if (
        ![
          'message.started',
          'message.delta',
          'message.completed',
          'message.error',
        ].includes(event.event)
      )
        return
      const parsed = eventSchema.parse(JSON.parse(event.data))
      if (
        parsed.conversation_id !== conversationId ||
        parsed.request_id !== requestId
      )
        throw new Error('The response did not match this request.')
      if (messageId && parsed.message_id !== messageId)
        throw new Error('The response message identity changed unexpectedly.')
      messageId = parsed.message_id
      if (sequences.has(parsed.sequence)) return
      sequences.add(parsed.sequence)
      if (
        event.event === 'message.completed' ||
        event.event === 'message.error'
      )
        terminal = true
      onEvent({ ...parsed, type: event.event })
    },
    streamSignal,
  )
  if (!terminal)
    throw new Error(
      'The connection ended before the reply was complete. Retry to recover the saved response.',
    )
}
