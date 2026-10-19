import { MessageSquare, Plus } from 'lucide-react'
import type { Conversation } from '../../services/conversations'
export function ConversationSidebar({
  items,
  selected,
  busy,
  loading,
  error,
  onSelect,
  onCreate,
  onRetry,
}: {
  items: Conversation[]
  selected: string | null
  busy: boolean
  loading: boolean
  error: boolean
  onSelect: (id: string) => void
  onCreate: () => void
  onRetry: () => void
}) {
  return (
    <aside className="ai-sidebar" aria-label="Conversations">
      <div className="ai-sidebar-heading">
        <h2>Your conversations</h2>
        <button
          onClick={onCreate}
          disabled={busy}
          aria-label="New conversation"
        >
          <Plus size={18} />
        </button>
      </div>
      {loading && <p role="status">Loading conversations...</p>}
      {error && (
        <div role="alert">
          <p>Unable to load conversations.</p>
          <button onClick={onRetry}>Try again</button>
        </div>
      )}
      {!loading && !error && !items.length && (
        <p className="ai-sidebar-empty">
          Start a conversation. Your history will appear here.
        </p>
      )}
      <nav aria-label="Conversation history">
        {items.map((item) => (
          <button
            key={item.id}
            className={selected === item.id ? 'is-selected' : ''}
            aria-current={selected === item.id ? 'page' : undefined}
            disabled={busy}
            onClick={() => onSelect(item.id)}
          >
            <MessageSquare size={15} />
            <span>{item.title}</span>
          </button>
        ))}
      </nav>
    </aside>
  )
}
