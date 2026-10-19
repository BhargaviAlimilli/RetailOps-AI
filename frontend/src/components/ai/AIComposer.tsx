import { useState } from 'react'
import { ArrowUp, Square } from 'lucide-react'
export function AIComposer({
  busy,
  disabled,
  onSend,
  onStop,
}: {
  busy: boolean
  disabled?: boolean
  onSend: (content: string) => void
  onStop: () => void
}) {
  const [text, setText] = useState('')
  const send = () => {
    if (text.trim() && !busy && !disabled) {
      onSend(text.trim())
      setText('')
    }
  }
  return (
    <form
      className="ai-composer"
      onSubmit={(event) => {
        event.preventDefault()
        send()
      }}
    >
      <label className="sr-only" htmlFor="ai-prompt">
        Message your retail companion
      </label>
      <textarea
        id="ai-prompt"
        placeholder="Ask a question about your retail operations..."
        value={text}
        maxLength={8000}
        disabled={disabled || busy}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (
            event.key === 'Enter' &&
            !event.shiftKey &&
            !event.nativeEvent.isComposing
          ) {
            event.preventDefault()
            send()
          }
        }}
        rows={2}
      />
      <div className="ai-composer-bottom">
        <span>Enter to send / Shift + Enter for a new line</span>
        {busy ? (
          <button type="button" onClick={onStop}>
            <Square size={14} /> Stop
          </button>
        ) : (
          <button
            type="submit"
            disabled={!text.trim() || disabled}
            aria-label="Send message"
          >
            <ArrowUp size={18} />
          </button>
        )}
      </div>
    </form>
  )
}
