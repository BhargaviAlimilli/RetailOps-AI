import { useState, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Workflow, ShieldCheck } from 'lucide-react'
import { CitationCard } from '../../components/ai/CitationCard'
import { ToolExecutionCard } from '../../components/ai/ToolExecutionCard'
import { agents, type AgentRun } from '../../services/agents'
import { retail, formatMoney } from '../../services/retail'
import { useAuth } from '../auth/AuthProvider'
import { PageHeading, QueryState } from '../retail/shared'
import '../retail/retail.css'
import '../documents/knowledge.css'
export default function AgentsPage() {
  const { user } = useAuth(),
    client = useQueryClient()
  const canAct = user?.role === 'admin' || user?.role === 'manager'
  const [storeId, setStore] = useState(''),
    [productId, setProduct] = useState(''),
    [supplierId, setSupplier] = useState(''),
    [reason, setReason] = useState(''),
    [selected, setSelected] = useState<string | null>(null),
    [productSearch, setProductSearch] = useState('')
  const [decision, setDecision] = useState<'approve' | 'reject' | null>(null)
  const request = useRef<string | null>(null),
    decisionRequest = useRef<string | null>(null)
  const runs = useQuery({ queryKey: ['agent-runs'], queryFn: agents.list })
  const stores = useQuery({
    queryKey: ['stores'],
    queryFn: () => retail.stores(),
  })
  const products = useQuery({
    queryKey: ['agent-products', productSearch],
    queryFn: () => retail.products({ page_size: 100, q: productSearch }),
  })
  const suppliers = useQuery({
    queryKey: ['suppliers'],
    queryFn: () => retail.suppliers(),
  })
  const selectedRun =
    runs.data?.find((run) => run.id === selected) ?? runs.data?.[0]
  const refresh = (run: AgentRun) => {
    client.setQueryData<AgentRun[]>(['agent-runs'], (old) => [
      run,
      ...(old ?? []).filter((item) => item.id !== run.id),
    ])
    setSelected(run.id)
  }
  const create = useMutation({
    mutationFn: agents.create,
    onSuccess: (run) => {
      refresh(run)
      request.current = null
    },
  })
  const resume = useMutation({ mutationFn: agents.resume, onSuccess: refresh })
  const decide = useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string
      body: Parameters<typeof agents.decide>[1]
    }) => agents.decide(id, body),
    onSuccess: (run) => {
      refresh(run)
      setDecision(null)
      setReason('')
      decisionRequest.current = null
      void client.invalidateQueries({ queryKey: ['orders'] })
    },
  })
  return (
    <section>
      <PageHeading
        title="Replenishment agent"
        description="A traceable recommendation. An explicit human decision."
      />
      <div className="knowledge-banner">
        <ShieldCheck size={18} />
        <p>
          The workflow prepares a purchase proposal from live retail data. A
          manager or administrator must review and approve it before the
          purchase order advances.
        </p>
      </div>
      <div className="knowledge-layout">
        <div>
          <section className="knowledge-panel">
            <h2>
              <Workflow size={18} /> Plan replenishment
            </h2>
            {canAct ? (
              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  if (!storeId || !productId || !supplierId) return
                  request.current ??= crypto.randomUUID()
                  create.mutate({
                    store_id: storeId,
                    product_id: productId,
                    supplier_id: supplierId,
                    request_id: request.current,
                  })
                }}
              >
                <div className="agent-selects">
                  <label className="knowledge-field">
                    Find product
                    <input
                      value={productSearch}
                      onChange={(event) => {
                        setProductSearch(event.target.value)
                        setProduct('')
                        request.current = null
                      }}
                      placeholder="Search product name or SKU"
                    />
                  </label>
                  <label className="knowledge-field">
                    Store
                    <select
                      required
                      value={storeId}
                      onChange={(event) => {
                        setStore(event.target.value)
                        request.current = null
                      }}
                    >
                      <option value="">Choose a store</option>
                      {stores.data?.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="knowledge-field">
                    Product
                    <select
                      required
                      value={productId}
                      onChange={(event) => {
                        setProduct(event.target.value)
                        request.current = null
                      }}
                    >
                      <option value="">Choose a product</option>
                      {products.data?.items.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name} / {item.sku}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="knowledge-field">
                    Supplier
                    <select
                      required
                      value={supplierId}
                      onChange={(event) => {
                        setSupplier(event.target.value)
                        request.current = null
                      }}
                    >
                      <option value="">Choose a supplier</option>
                      {suppliers.data?.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                {(stores.isPending ||
                  products.isPending ||
                  suppliers.isPending) && (
                  <p role="status">Loading available retail records...</p>
                )}
                {(stores.error || products.error || suppliers.error) && (
                  <div role="alert">
                    <p>Unable to load selection data.</p>
                    <button
                      className="retail-button"
                      type="button"
                      onClick={() => {
                        void stores.refetch()
                        void products.refetch()
                        void suppliers.refetch()
                      }}
                    >
                      Retry selection data
                    </button>
                  </div>
                )}
                {create.isError && <p role="alert">{create.error.message}</p>}
                <button
                  className="retail-button primary"
                  disabled={
                    create.isPending || !storeId || !productId || !supplierId
                  }
                >
                  {create.isPending
                    ? 'Preparing proposal...'
                    : 'Prepare proposal'}
                </button>
              </form>
            ) : (
              <p className="knowledge-muted">
                Your analyst role can review workflow history. Managers and
                administrators create and decide proposals.
              </p>
            )}
          </section>
          <section className="knowledge-panel">
            <h2>Workflow history</h2>
            <QueryState
              pending={runs.isPending}
              error={runs.error}
              retry={() => runs.refetch()}
            />
            {runs.data?.length === 0 && (
              <p className="knowledge-empty">
                No workflows yet. Prepare a proposal to begin.
              </p>
            )}
            <div className="agent-history">
              {runs.data?.map((run) => (
                <button
                  key={run.id}
                  aria-pressed={selectedRun?.id === run.id}
                  onClick={() => {
                    setSelected(run.id)
                    setDecision(null)
                    decide.reset()
                    setReason('')
                  }}
                >
                  <strong>
                    {run.proposal?.product_name ?? 'Replenishment workflow'}
                  </strong>
                  <span>
                    {run.status.replaceAll('_', ' ')} /{' '}
                    {new Date(run.created_at).toLocaleDateString('en-IN')}
                  </span>
                </button>
              ))}
            </div>
          </section>
        </div>
        <section className="knowledge-panel">
          {selectedRun ? (
            <>
              <h2>
                Review proposal{' '}
                <span className="agent-status">
                  {selectedRun.status.replaceAll('_', ' ')}
                </span>
              </h2>
              <ol className="agent-trace">
                {selectedRun.steps.map((step, index) => (
                  <li key={`${step.name}-${index}`}>
                    <span>{index + 1}</span>
                    <ToolExecutionCard {...step} />
                  </li>
                ))}
              </ol>
              {selectedRun.error && <p role="alert">{selectedRun.error}</p>}
              {canAct && ['error', 'running'].includes(selectedRun.status) && (
                <div>
                  <button
                    className="retail-button"
                    disabled={resume.isPending}
                    onClick={() => resume.mutate(selectedRun.id)}
                  >
                    {resume.isPending
                      ? 'Resuming workflow...'
                      : 'Resume saved workflow'}
                  </button>
                  {resume.isError && <p role="alert">{resume.error.message}</p>}
                </div>
              )}
              {selectedRun.proposal && (
                <div className="agent-proposal">
                  <h3>{selectedRun.proposal.product_name}</h3>
                  <dl>
                    <div>
                      <dt>Store</dt>
                      <dd>{selectedRun.proposal.store_name}</dd>
                    </div>
                    <div>
                      <dt>Supplier</dt>
                      <dd>{selectedRun.proposal.supplier_name}</dd>
                    </div>
                    <div>
                      <dt>Quantity</dt>
                      <dd>{selectedRun.proposal.quantity}</dd>
                    </div>
                    <div>
                      <dt>Unit cost</dt>
                      <dd>{formatMoney(selectedRun.proposal.unit_cost)}</dd>
                    </div>
                    <div>
                      <dt>Proposed total</dt>
                      <dd>{formatMoney(selectedRun.proposal.total)}</dd>
                    </div>
                  </dl>
                  <p>{selectedRun.proposal.reason}</p>
                  {selectedRun.proposal.citations?.map((citation) => (
                    <CitationCard key={citation.chunk_id} citation={citation} />
                  ))}
                </div>
              )}
              {selectedRun.purchase_order_id && (
                <p className="knowledge-muted">
                  Purchase order: {selectedRun.purchase_order_id}{' '}
                  <Link to="/purchase-orders">Open purchase orders</Link>
                </p>
              )}
              {canAct && selectedRun.status === 'awaiting_approval' && (
                <div className="agent-decision">
                  {!decision ? (
                    <>
                      <button
                        className="retail-button primary"
                        onClick={() => {
                          setDecision('approve')
                          decisionRequest.current = null
                        }}
                      >
                        Review approval
                      </button>
                      <button
                        className="retail-button"
                        onClick={() => {
                          setDecision('reject')
                          decisionRequest.current = null
                        }}
                      >
                        Reject proposal
                      </button>
                    </>
                  ) : (
                    <form
                      onSubmit={(event) => {
                        event.preventDefault()
                        if (
                          reason.trim().length < 5 ||
                          reason.trim().length > 500
                        )
                          return
                        decisionRequest.current ??= crypto.randomUUID()
                        decide.mutate({
                          id: selectedRun.id,
                          body: {
                            decision,
                            reason: reason.trim(),
                            idempotency_key: decisionRequest.current,
                          },
                        })
                      }}
                    >
                      <h3>
                        {decision === 'approve'
                          ? 'Confirm authorized approval'
                          : 'Confirm rejection'}
                      </h3>
                      <p>
                        {decision === 'approve'
                          ? 'Approving advances the purchase order. Review quantity, supplier, and total before confirming.'
                          : 'Rejecting records your reason and prevents this proposal from advancing.'}
                      </p>
                      <label className="knowledge-field">
                        Decision reason
                        <textarea
                          required
                          minLength={5}
                          maxLength={500}
                          value={reason}
                          onChange={(event) => {
                            setReason(event.target.value)
                            decisionRequest.current = null
                          }}
                          rows={3}
                        />
                      </label>
                      {decide.isError && (
                        <p role="alert">{decide.error.message}</p>
                      )}
                      <button
                        className="retail-button primary"
                        disabled={decide.isPending || reason.trim().length < 5}
                      >
                        {decide.isPending
                          ? 'Recording decision...'
                          : decision === 'approve'
                            ? 'Confirm approval'
                            : 'Confirm rejection'}
                      </button>
                      <button
                        className="retail-button"
                        type="button"
                        disabled={decide.isPending}
                        onClick={() => setDecision(null)}
                      >
                        Cancel
                      </button>
                    </form>
                  )}
                </div>
              )}
            </>
          ) : (
            <div className="knowledge-empty">
              <Workflow size={30} />
              <h2>Your next decision starts here.</h2>
              <p>
                Select a saved workflow or prepare a proposal to review its
                reasoning and approval steps.
              </p>
            </div>
          )}
        </section>
      </div>
    </section>
  )
}
