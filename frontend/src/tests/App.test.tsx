import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../app/App'

function renderApp(path = '/') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('workspace foundation', () => {
  it('shows live successful connections without fabricated metrics', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((path: string) =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              service: 'retailops-api',
              status: path.endsWith('/ready') ? 'ready' : 'ok',
            }),
          ),
        ),
      ),
    )
    renderApp()
    expect(
      screen.getByRole('heading', { name: 'Workspace overview' }),
    ).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getAllByText('Connected')).toHaveLength(2),
    )
    expect(
      screen.getByText('No operational metrics are displayed yet.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Not configured')).toBeInTheDocument()
  })
  it('renders database errors and supports retry', async () => {
    const fetchMock = vi.fn((path: string) =>
      Promise.resolve(
        path.endsWith('/ready')
          ? new Response('{}', { status: 503 })
          : new Response(
              JSON.stringify({ status: 'ok', service: 'retailops-api' }),
            ),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderApp()
    expect(await screen.findByText('Unavailable')).toBeInTheDocument()
    expect(
      screen.getByText(/Database connection unavailable/),
    ).toBeInTheDocument()
    await userEvent.click(
      screen.getByRole('button', { name: 'Refresh status' }),
    )
    await waitFor(() =>
      expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(4),
    )
  })
  it('shows pending state while requests are unresolved', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise(() => {})),
    )
    renderApp()
    expect(
      screen.getByText('Checking the data connection...'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Checking' })).toBeDisabled()
  })
  it('supports keyboard navigation toggling and not-found recovery', async () => {
    renderApp('/unknown')
    expect(
      screen.getByRole('heading', { name: 'This page is unavailable.' }),
    ).toBeInTheDocument()
    const toggle = screen.getByRole('button', { name: 'Open navigation' })
    toggle.focus()
    await userEvent.keyboard('{Enter}')
    expect(
      screen.getByRole('button', { name: 'Close navigation' }),
    ).toHaveAttribute('aria-expanded', 'true')
    expect(
      within(screen.getByRole('navigation'))
        .getByText('Inventory')
        .closest('[aria-disabled]'),
    ).toHaveAttribute('aria-disabled', 'true')
  })
})
