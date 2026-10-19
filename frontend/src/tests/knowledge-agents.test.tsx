import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DocumentsPage from '../features/documents/DocumentsPage'
import AgentsPage from '../features/agents/AgentsPage'
import { knowledge } from '../services/knowledge'
import { agents, type AgentRun } from '../services/agents'
import { retail } from '../services/retail'
import { useAuth } from '../features/auth/AuthProvider'
vi.mock('../features/auth/AuthProvider', () => ({ useAuth: vi.fn() }))
vi.mock('../services/knowledge', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../services/knowledge')>()),
  knowledge: {
    list: vi.fn(),
    create: vi.fn(),
    remove: vi.fn(),
    search: vi.fn(),
  },
}))
vi.mock('../services/agents', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../services/agents')>()),
  agents: { list: vi.fn(), create: vi.fn(), decide: vi.fn(), resume: vi.fn() },
}))
vi.mock('../services/retail', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../services/retail')>()),
  retail: { stores: vi.fn(), products: vi.fn(), suppliers: vi.fn() },
}))
const id = '11111111-1111-4111-8111-111111111111'
const run: AgentRun = {
  id,
  status: 'awaiting_approval',
  purchase_order_id: null,
  created_at: '2026-10-19T00:00:00Z',
  proposal: {
    store_name: 'Central store',
    product_name: 'Green tea',
    supplier_name: 'Local supplier',
    quantity: 8,
    unit_cost: '100.00',
    total: '800.00',
    reason: 'Reorder point reached',
    citations: [
      {
        document_id: id,
        chunk_id: '22222222-2222-4222-8222-222222222222',
        title: 'Replenishment policy source',
        excerpt: 'Managers must review the supplier terms before approval.',
        score: 0.9,
      },
    ],
  },
  steps: [
    {
      name: 'inventory_review',
      status: 'completed',
      detail: 'Read live stock',
    },
  ],
}
function role(value: 'manager' | 'analyst') {
  vi.mocked(useAuth).mockReturnValue({
    user: { id, email: 'person@example.com', name: 'Person', role: value },
    signOut: vi.fn(),
  })
}
function setup(component: React.ReactNode) {
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
          },
        })
      }
    >
      <MemoryRouter>{component}</MemoryRouter>
    </QueryClientProvider>,
  )
}
beforeEach(() => {
  vi.clearAllMocks()
  role('manager')
  vi.mocked(knowledge.list).mockResolvedValue([])
  vi.mocked(agents.list).mockResolvedValue([run])
  vi.mocked(retail.stores).mockResolvedValue([])
  vi.mocked(retail.products).mockResolvedValue({
    items: [],
    total: 0,
    page: 1,
    page_size: 100,
  })
  vi.mocked(retail.suppliers).mockResolvedValue([])
})
describe('knowledge and human approval', () => {
  it('allows an analyst to index their own document and search real excerpts', async () => {
    role('analyst')
    vi.mocked(knowledge.create).mockResolvedValue({
      id,
      title: 'Returns guide',
      status: 'ready',
      created_at: '2026-10-19T00:00:00Z',
      chunk_count: 1,
    })
    vi.mocked(knowledge.search).mockResolvedValue({
      citations: [
        {
          document_id: id,
          chunk_id: '22222222-2222-4222-8222-222222222222',
          title: 'Returns guide',
          excerpt: 'Return unused goods within seven days.',
          score: 0.9,
        },
      ],
    })
    setup(<DocumentsPage />)
    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Document title'))
    await user.paste('Returns guide')
    await user.click(screen.getByLabelText('Document text'))
    await user.paste('Return unused goods within seven days.')
    await userEvent.click(
      screen.getByRole('button', { name: 'Add and index document' }),
    )
    await waitFor(() =>
      expect(knowledge.create).toHaveBeenCalledWith(
        {
          title: 'Returns guide',
          content: 'Return unused goods within seven days.',
        },
        expect.anything(),
      ),
    )
    await user.click(screen.getByLabelText('Search query'))
    await user.paste('Return policy')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    await userEvent.click(await screen.findByText('Returns guide'))
    expect(
      screen.getByText('Return unused goods within seven days.'),
    ).toBeInTheDocument()
  })
  it('requires a reason and explicit confirmation before approving a proposal', async () => {
    vi.mocked(agents.decide).mockResolvedValue({ ...run, status: 'approved' })
    setup(<AgentsPage />)
    await userEvent.click(
      await screen.findByRole('button', { name: 'Review approval' }),
    )
    expect(screen.getByText('Replenishment policy source')).toBeInTheDocument()
    expect(agents.decide).not.toHaveBeenCalled()
    expect(
      screen.getByRole('button', { name: 'Confirm approval' }),
    ).toBeDisabled()
    await userEvent.type(
      screen.getByLabelText('Decision reason'),
      'Reviewed supplier terms and budget',
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Confirm approval' }),
    )
    await waitFor(() =>
      expect(agents.decide).toHaveBeenCalledWith(id, {
        decision: 'approve',
        reason: 'Reviewed supplier terms and budget',
        idempotency_key: expect.stringMatching(/^[0-9a-f-]{36}$/),
      }),
    )
  })
  it('resumes a saved error checkpoint only after an explicit manager action', async () => {
    vi.mocked(agents.list).mockResolvedValue([
      { ...run, status: 'error', error: 'Provider temporarily unavailable' },
    ])
    vi.mocked(agents.resume).mockResolvedValue(run)
    setup(<AgentsPage />)
    expect(
      await screen.findByText('Provider temporarily unavailable'),
    ).toBeInTheDocument()
    expect(agents.resume).not.toHaveBeenCalled()
    await userEvent.click(
      screen.getByRole('button', { name: 'Resume saved workflow' }),
    )
    await waitFor(() =>
      expect(agents.resume).toHaveBeenCalledWith(id, expect.anything()),
    )
    expect(
      await screen.findByRole('button', { name: 'Review approval' }),
    ).toBeInTheDocument()
  })
  it('keeps approval and proposal creation unavailable to analysts', async () => {
    role('analyst')
    setup(<AgentsPage />)
    expect(await screen.findByText('Read live stock')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Review approval' }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Prepare proposal' }),
    ).not.toBeInTheDocument()
  })
})
