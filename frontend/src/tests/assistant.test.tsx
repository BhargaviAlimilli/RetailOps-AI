import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AIComposer } from '../components/ai/AIComposer'
import { AIMessage } from '../components/ai/AIMessage'

describe('assistant components', () => {
  it('sends Enter, preserves Shift+Enter and allows stopping a real active stream', async () => {
    const send = vi.fn(),
      stop = vi.fn()
    const { rerender } = render(
      <AIComposer busy={false} onSend={send} onStop={stop} />,
    )
    const input = screen.getByRole('textbox')
    await userEvent.type(input, 'Question{Shift>}{Enter}{/Shift}details')
    expect(send).not.toHaveBeenCalled()
    await userEvent.keyboard('{Enter}')
    expect(send).toHaveBeenCalledWith('Question\ndetails')
    expect(input).toHaveValue('')
    rerender(<AIComposer busy onSend={send} onStop={stop} />)
    await userEvent.click(screen.getByRole('button', { name: 'Stop' }))
    expect(stop).toHaveBeenCalledOnce()
  })
  it('does not render raw HTML or executable Markdown links', () => {
    const { container } = render(
      <AIMessage
        role="assistant"
        content={
          '<script>alert(1)</script>\n\n[unsafe](javascript:alert(1))\n\n**Verified formatting**\n\n![Untrusted image](https://example.com/tracker)'
        }
      />,
    )
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
    expect(
      container.querySelector('a')?.getAttribute('href') ?? '',
    ).not.toContain('javascript:')
    expect(screen.getByText('Verified formatting').tagName).toBe('STRONG')
  })
})
