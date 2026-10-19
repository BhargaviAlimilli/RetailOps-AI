import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'
import rehypeHighlight from 'rehype-highlight'
import { Bot, UserRound } from 'lucide-react'
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
      </div>
    </article>
  )
}
