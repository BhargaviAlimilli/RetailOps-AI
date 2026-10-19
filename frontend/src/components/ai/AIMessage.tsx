import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'
import rehypeHighlight from 'rehype-highlight'
import { Bot, UserRound, Copy } from 'lucide-react'
import { CodeBlock } from './CodeBlock'
export function AIMessage({
  role,
  content,
  children,
}: {
  role: 'user' | 'assistant'
  content: string
  children?: React.ReactNode
}) {
  const [copyResult, setCopyResult] = useState<{
    content: string
    ok: boolean
  } | null>(null)
  const feedback = copyResult?.content === content ? copyResult : null
  return (
    <article
      className={`ai-message ai-message-${role}`}
      aria-label={role === 'user' ? 'Your message' : 'Assistant message'}
    >
      <div className="ai-avatar">
        {role === 'assistant' ? <Bot size={18} /> : <UserRound size={18} />}
      </div>
      <div className="ai-message-body">
        <strong className="ai-author">
          {role === 'assistant' ? 'RetailOps Companion' : 'You'}
        </strong>
        <ReactMarkdown
          skipHtml
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeSanitize, rehypeHighlight]}
          components={{
            pre: CodeBlock,
            img: ({ alt }) => <span>[Image: {alt || 'external image'}]</span>,
            a: ({ children, ...props }) => (
              <a {...props} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            ),
          }}
        >
          {content}
        </ReactMarkdown>
        {children}
        {content && (
          <div className="ai-history-retry">
            <button
              type="button"
              aria-label="Copy message"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(content)
                  setCopyResult({ content, ok: true })
                } catch {
                  setCopyResult({ content, ok: false })
                }
              }}
            >
              <Copy size={12} aria-hidden="true" /> Copy message
            </button>
            <span role="status" className="ai-message-note">
              {feedback
                ? feedback.ok
                  ? 'Copied to clipboard.'
                  : 'Could not copy. Select the message text and copy it manually.'
                : ''}
            </span>
          </div>
        )}
      </div>
    </article>
  )
}
