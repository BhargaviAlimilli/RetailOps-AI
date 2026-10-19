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
  it('copies the complete message and reports actual clipboard success', async () => {
    const user = userEvent.setup()
    const write = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue()
    render(
      <AIMessage
        role="assistant"
        content="**Complete** message with details"
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Copy message' }))
    expect(write).toHaveBeenCalledWith('**Complete** message with details')
    expect(screen.getByRole('status')).toHaveTextContent('Copied to clipboard.')
    write.mockRestore()
  })
  it('reports clipboard failure without claiming the message was copied', async () => {
    const user = userEvent.setup()
    const write = vi
      .spyOn(navigator.clipboard, 'writeText')
      .mockRejectedValue(new Error('Denied'))
    render(<AIMessage role="user" content="My question" />)
    await user.click(screen.getByRole('button', { name: 'Copy message' }))
    expect(screen.getByRole('status')).toHaveTextContent('Could not copy.')
    expect(screen.queryByText('Copied to clipboard.')).not.toBeInTheDocument()
    write.mockRestore()
  })
  it('keeps one copy control outside untrusted Markdown links', async () => {
    const user = userEvent.setup()
    const write = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue()
    const content = '[Supplier policy](https://example.com/policy)'
    const { container } = render(
      <AIMessage role="assistant" content={content} />,
    )
    expect(
      screen.getAllByRole('button', { name: 'Copy message' }),
    ).toHaveLength(1)
    expect(container.querySelector('a button')).toBeNull()
    expect(container.querySelector('a div')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Copy message' }))
    expect(write).toHaveBeenCalledWith(content)
    write.mockRestore()
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
