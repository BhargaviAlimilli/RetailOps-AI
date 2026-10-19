import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Sparkles, ArrowDown, ArrowUpRight } from 'lucide-react'
import { conversations, streamMessage } from '../../services/conversations'
import { AIMessage } from '../../components/ai/AIMessage'
import { AIComposer } from '../../components/ai/AIComposer'
import { ConversationSidebar } from '../../components/ai/ConversationSidebar'
import { StreamingMessage } from '../../components/ai/StreamingMessage'
import './assistant.css'

type Attempt = {
  conversationId: string
  content: string
  requestId: string
  text: string
  state: 'streaming' | 'stopped' | 'error' | 'completed'
  error?: string
}
const prompts = [
  'How should I investigate low stock?',
  'Help me plan a supplier review.',
  'What should I check before approving a purchase order?',
]
export default function AssistantPage() {
  const client = useQueryClient()
  const [selected, setSelected] = useState<string | null>(null)
  const [attempt, setAttempt] = useState<Attempt | null>(null)
  const [creatingError, setCreatingError] = useState<string | null>(null)
  const [atBottom, setAtBottom] = useState(true)
  const [streaming, setStreaming] = useState(false)
  const controller = useRef<AbortController | null>(null)
  const scroll = useRef<HTMLDivElement>(null)
  const history = useQuery({
    queryKey: ['conversations'],
    queryFn: conversations.list,
  })
  const messages = useQuery({
    queryKey: ['messages', selected],
    queryFn: () => conversations.messages(selected!),
    enabled: !!selected,
  })
  const create = useMutation({
    mutationFn: conversations.create,
    onSuccess: (item) => {
      client.setQueryData(['conversations'], (old: typeof history.data) => [
        item,
        ...(old ?? []),
      ])
      setSelected(item.id)
      setAttempt(null)
    },
  })
  const busy = streaming || create.isPending
  useEffect(() => () => controller.current?.abort(), [])
  useEffect(() => {
    if (atBottom) scroll.current?.scrollTo({ top: scroll.current.scrollHeight })
  }, [attempt?.text, messages.data, atBottom])
  async function send(content: string, retry?: Attempt) {
    if (controller.current) return
    const active = new AbortController()
    controller.current = active
    setStreaming(true)
    setCreatingError(null)
    let conversationId = retry?.conversationId ?? selected
    let began = false
    try {
      if (!conversationId) conversationId = (await create.mutateAsync()).id
      active.signal.throwIfAborted()
      const next: Attempt = {
        conversationId,
        content,
        requestId: retry?.requestId ?? crypto.randomUUID(),
        text: '',
        state: 'streaming',
      }
      began = true
      setAtBottom(true)
      setAttempt(next)
      await streamMessage(
        conversationId,
        content,
        next.requestId,
        active.signal,
        (event) => {
          setAttempt((old) =>
            old
              ? {
                  ...old,
                  text:
                    event.type === 'message.delta'
                      ? old.text + (event.payload.text ?? '')
                      : (event.payload.content ?? old.text),
                  state:
                    event.type === 'message.completed'
                      ? 'completed'
                      : event.type === 'message.error'
                        ? 'error'
                        : old.state,
                  error:
                    event.type === 'message.error'
                      ? (event.payload.message ??
                        'The reply could not be completed.')
                      : old.error,
                }
              : old,
          )
        },
      )
    } catch (error) {
      if (!began) {
        if (!active.signal.aborted)
          setCreatingError(
            error instanceof Error
              ? error.message
              : 'Unable to create a conversation.',
          )
      } else {
        setAttempt((old) =>
          old
            ? {
                ...old,
                state: active.signal.aborted ? 'stopped' : 'error',
                error: active.signal.aborted
                  ? 'Reply stopped. Any saved partial response remains in history.'
                  : error instanceof Error
                    ? error.message
                    : 'The connection failed.',
              }
            : old,
        )
      }
    } finally {
      controller.current = null
      setStreaming(false)
      if (began)
        await Promise.all([
          client.invalidateQueries({ queryKey: ['messages', conversationId] }),
          client.invalidateQueries({ queryKey: ['conversations'] }),
        ])
    }
  }
  const currentAttempt = attempt?.conversationId === selected ? attempt : null
  const persistedRequest = messages.data?.some(
    (message) => message.request_id === currentAttempt?.requestId,
  )
  const displayAttempt =
    currentAttempt &&
    (!persistedRequest || currentAttempt.state === 'streaming')
  return (
    <section className="ai-workspace">
      <header className="ai-page-heading">
        <div>
          <p className="retail-eyebrow">YOUR OPERATIONS, IN CONVERSATION</p>
          <h1>
            AI Companion <span>Gemini</span>
          </h1>
          <p>Think through your next retail decision.</p>
        </div>
        <span className="ai-private">
          <Sparkles size={15} /> Your workspace assistant
        </span>
      </header>
      <div className="ai-layout">
        <ConversationSidebar
          items={history.data ?? []}
          selected={selected}
          busy={busy}
          loading={history.isPending}
          error={history.isError}
          onRetry={() => void history.refetch()}
          onCreate={() => {
            setCreatingError(null)
            create.mutate(undefined, {
              onError: (error) => setCreatingError(error.message),
            })
          }}
          onSelect={(id) => {
            setSelected(id)
            setAttempt(null)
            setAtBottom(true)
          }}
        />
        <div className="ai-main">
          <div
            className="ai-messages"
            ref={scroll}
            onScroll={(event) => {
              const element = event.currentTarget
              setAtBottom(
                element.scrollHeight -
                  element.scrollTop -
                  element.clientHeight <
                  100,
              )
            }}
          >
            {messages.isPending && selected && (
              <p role="status">Loading conversation...</p>
            )}
            {messages.isError && (
              <div role="alert">
                <p>{messages.error.message}</p>
                <button onClick={() => void messages.refetch()}>
                  Retry history
                </button>
              </div>
            )}
            {!messages.data?.length && !attempt && !messages.isFetching && (
              <div className="ai-welcome">
                <div className="ai-welcome-icon">
                  <Sparkles size={28} />
                </div>
                <h2>A little clarity for your next move.</h2>
                <p>
                  Ask a question, explore an idea, or work through a decision.
                  Replies depend on your configured AI provider.
                </p>
                <div>
                  {prompts.map((prompt) => (
                    <button
                      key={prompt}
                      disabled={busy}
                      onClick={() => void send(prompt)}
                    >
                      {prompt}
                      <ArrowUpRight size={14} />
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.data
              ?.filter(
                (message) =>
                  message.request_id !== currentAttempt?.requestId ||
                  !displayAttempt,
              )
              .map((message) => (
                <AIMessage
                  key={message.id}
                  role={message.role}
                  content={message.content}
                >
                  {message.role === 'assistant' &&
                    ['error', 'cancelled'].includes(message.status) &&
                    !currentAttempt?.error && (
                      <div className="ai-history-retry">
                        <button
                          disabled={busy}
                          onClick={() => {
                            const original = messages.data?.find(
                              (item) =>
                                item.role === 'user' &&
                                item.request_id === message.request_id,
                            )
                            if (original)
                              void send(original.content, {
                                conversationId: message.conversation_id,
                                content: original.content,
                                requestId: message.request_id,
                                text: message.content,
                                state: 'error',
                              })
                          }}
                        >
                          Recover saved reply
                        </button>
                        <button
                          disabled={busy}
                          onClick={() => {
                            const original = messages.data?.find(
                              (item) =>
                                item.role === 'user' &&
                                item.request_id === message.request_id,
                            )
                            if (original) void send(original.content)
                          }}
                        >
                          Try a new reply
                        </button>
                      </div>
                    )}
                  {message.status !== 'completed' && (
                    <p className="ai-message-note">
                      {message.status === 'cancelled'
                        ? 'Stopped'
                        : message.status === 'error'
                          ? 'Reply failed'
                          : message.status}
                    </p>
                  )}
                </AIMessage>
              ))}
            {displayAttempt && (
              <>
                <AIMessage role="user" content={currentAttempt.content} />
                <AIMessage role="assistant" content={currentAttempt.text}>
                  {currentAttempt.state === 'streaming' && (
                    <StreamingMessage
                      text={
                        currentAttempt.text
                          ? 'Receiving reply...'
                          : 'Waiting for the assistant...'
                      }
                    />
                  )}
                </AIMessage>
              </>
            )}
            {currentAttempt?.error && (
              <div className="ai-error" role="alert">
                <p>{currentAttempt.error}</p>
                <button
                  disabled={busy}
                  onClick={() =>
                    void send(currentAttempt.content, currentAttempt)
                  }
                >
                  Recover saved reply
                </button>
                <button
                  disabled={busy}
                  onClick={() => void send(currentAttempt.content)}
                >
                  Try a new reply
                </button>
              </div>
            )}
            {creatingError && (
              <div className="ai-error" role="alert">
                {creatingError}
              </div>
            )}
          </div>
          {!atBottom && (
            <button
              className="ai-jump"
              onClick={() => {
                setAtBottom(true)
                scroll.current?.scrollTo({
                  top: scroll.current.scrollHeight,
                  behavior: 'smooth',
                })
              }}
            >
              <ArrowDown size={14} /> Latest message
            </button>
          )}
          <div className="ai-compose-wrap">
            <AIComposer
              busy={busy}
              disabled={messages.isError}
              onSend={(content) => void send(content)}
              onStop={() => controller.current?.abort()}
            />
            <p className="ai-disclaimer">
              AI can make mistakes. Verify important details before acting. No
              inventory or purchase orders are changed by this chat.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
