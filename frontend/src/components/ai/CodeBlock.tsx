import { useState } from 'react'
import type { ReactNode } from 'react'
import { Copy, Check } from 'lucide-react'
export function CodeBlock({ children }: { children?: ReactNode }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="ai-code">
      <button
        aria-label="Copy code"
        onClick={async (event) => {
          const text =
            event.currentTarget.parentElement?.querySelector('pre')
              ?.textContent ?? ''
          try {
            await navigator.clipboard.writeText(text)
            setCopied(true)
          } catch {
            setCopied(false)
          }
        }}
      >
        {copied ? <Check size={14} /> : <Copy size={14} />}
        {copied ? 'Copied' : 'Copy'}
      </button>
      <pre>{children}</pre>
    </div>
  )
}
