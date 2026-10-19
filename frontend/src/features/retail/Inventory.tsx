import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Search } from 'lucide-react'
import { DataTable } from '../../components/ui/DataTable'
import { formatDate, retail, type Inventory } from '../../services/retail'
import { useAuth } from '../auth/AuthProvider'
import {
  Badge,
  Dialog,
  PageHeading,
  Pagination,
  Panel,
  QueryState,
  StoreSelect,
} from './shared'
import './retail.css'

const adjustmentSchema = z.object({
  delta: z
    .number()
    .int('Use whole units')
    .refine((value) => value !== 0, 'Adjustment must change stock'),
  reason: z.string().trim().min(5, 'Explain why stock is changing').max(80),
})
function StockDetails({
  item,
  onClose,
  canManage,
}: {
  item: Inventory
  onClose: () => void
  canManage: boolean
}) {
  const client = useQueryClient()
  const [key, setKey] = useState(() => crypto.randomUUID())
  const form = useForm<z.infer<typeof adjustmentSchema>>({
    resolver: zodResolver(adjustmentSchema),
    defaultValues: { reason: '' },
  })
  const history = useQuery({
    queryKey: ['movements', item.id],
    queryFn: ({ signal }) => retail.movements(item.id, signal),
  })
  const mutation = useMutation({
    mutationFn: (body: z.infer<typeof adjustmentSchema>) =>
      retail.adjust(item.id, body, key),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['inventory'] })
      void client.invalidateQueries({ queryKey: ['movements', item.id] })
      void client.invalidateQueries({ queryKey: ['dashboard'] })
      setKey(crypto.randomUUID())
      form.reset({ reason: '' })
    },
  })
  return (
    <Dialog
      title={`${item.product_name} · ${item.store_name}`}
      onClose={onClose}
    >
      <p className="retail-dialog-intro">
        Adjustments create an inventory movement with your identity and reason.
        Negative adjustments cannot consume reserved stock.
      </p>
      {canManage && (
        <form
          className="retail-form"
          onSubmit={form.handleSubmit((data) => mutation.mutate(data))}
        >
          <label>
            Quantity change
            <input
              type="number"
              placeholder="e.g. -2 or 12"
              {...form.register('delta', { valueAsNumber: true })}
            />
            <small>{form.formState.errors.delta?.message}</small>
          </label>
          <label>
            Reason
            <textarea
              {...form.register('reason')}
              maxLength={80}
              placeholder="Explain this adjustment"
            />
            <small>{form.formState.errors.reason?.message}</small>
          </label>
          {mutation.error && <p role="alert">{mutation.error.message}</p>}
          {mutation.isSuccess && (
            <p className="retail-success" role="status">
              Inventory adjustment recorded.
            </p>
          )}
          <button
            className="retail-button primary"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? 'Recording…' : 'Record adjustment'}
          </button>
        </form>
      )}
      <h3>Movement history</h3>
      <QueryState
        pending={history.isPending}
        error={history.error}
        retry={history.refetch}
      />
      {history.data && (
        <DataTable
          rows={history.data}
          columns={[
            {
              key: 'delta',
              title: 'Change',
              render: (row) => (
                <Badge tone={row.delta > 0 ? 'green' : 'amber'}>
                  {row.delta > 0 ? '+' : ''}
                  {row.delta}
                </Badge>
              ),
            },
            { key: 'reason', title: 'Reason', render: (row) => row.reason },
            {
              key: 'actor',
              title: 'Recorded by',
              render: (row) => (
                <span>
                  {row.actor_name}
                  <small className="retail-muted">
                    {formatDate(row.created_at)}
                  </small>
                </span>
              ),
            },
          ]}
        />
      )}
    </Dialog>
  )
}
export function InventoryPage() {
  const { user } = useAuth()
  const [store, setStore] = useState('')
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('all')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<Inventory | null>(null)
  const query = useQuery({
    queryKey: ['inventory', store, q, status, page],
    queryFn: ({ signal }) =>
      retail.inventory(
        { store_id: store, q, status, page, page_size: 20 },
        signal,
      ),
  })
  return (
    <div className="retail-page">
      <PageHeading
        title="Inventory"
        description="Know what’s on hand. Keep every shelf ready for demand."
      />
      <div className="retail-filters">
        <label className="retail-search">
          <Search size={17} />
          <input
            aria-label="Search inventory"
            placeholder="Search product or SKU…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value)
              setPage(1)
            }}
          />
        </label>
        <StoreSelect
          value={store}
          onChange={(value) => {
            setStore(value)
            setPage(1)
          }}
        />
        <label className="retail-filter-label">
          Stock status
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value)
              setPage(1)
            }}
          >
            <option value="all">All stock</option>
            <option value="low">Low stock</option>
            <option value="out">Out of stock</option>
          </select>
        </label>
      </div>
      <QueryState
        pending={query.isPending}
        error={query.error}
        retry={query.refetch}
      />
      {query.data && (
        <Panel
          title="Stock by location"
          description="Select a product to view movements or record an adjustment"
        >
          <DataTable
            rows={query.data.items}
            columns={[
              {
                key: 'product',
                title: 'Product',
                render: (row) => (
                  <button
                    className="retail-text-button"
                    onClick={() => setSelected(row)}
                  >
                    {row.product_name}
                    <small>{row.sku}</small>
                  </button>
                ),
              },
              { key: 'store', title: 'Store', render: (row) => row.store_name },
              {
                key: 'on_hand',
                title: 'On hand',
                render: (row) => row.on_hand,
              },
              {
                key: 'reserved',
                title: 'Reserved',
                render: (row) => row.reserved,
              },
              {
                key: 'available',
                title: 'Available',
                render: (row) => <strong>{row.available}</strong>,
              },
              {
                key: 'reorder',
                title: 'Reorder at',
                render: (row) => row.reorder_point,
              },
              {
                key: 'status',
                title: 'Status',
                render: (row) =>
                  row.available <= 0 ? (
                    <Badge tone="red">Out of stock</Badge>
                  ) : row.available <= row.reorder_point ? (
                    <Badge tone="amber">Low stock</Badge>
                  ) : (
                    <Badge tone="green">In stock</Badge>
                  ),
              },
            ]}
          />
          <Pagination page={page} total={query.data.total} onChange={setPage} />
        </Panel>
      )}
      {selected && (
        <StockDetails
          item={selected}
          onClose={() => setSelected(null)}
          canManage={user?.role === 'admin' || user?.role === 'manager'}
        />
      )}
    </div>
  )
}
