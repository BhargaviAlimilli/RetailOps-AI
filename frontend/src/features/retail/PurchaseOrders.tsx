import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useFieldArray, useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus } from 'lucide-react'
import { DataTable } from '../../components/ui/DataTable'
import {
  formatDate,
  formatMoney,
  retail,
  type PurchaseOrder,
} from '../../services/retail'
import { useAuth } from '../auth/AuthProvider'
import {
  Badge,
  Dialog,
  PageHeading,
  Pagination,
  Panel,
  QueryState,
} from './shared'
import './retail.css'

const orderFormSchema = z
  .object({
    store_id: z.string().uuid('Select a store'),
    supplier_id: z.string().uuid('Select a supplier'),
    items: z
      .array(
        z.object({
          product_id: z.string().uuid('Select a product'),
          quantity: z
            .number()
            .int()
            .positive('Quantity must be a positive whole number'),
        }),
      )
      .min(1),
  })
  .refine(
    (order) =>
      new Set(order.items.map((item) => item.product_id)).size ===
      order.items.length,
    { message: 'Select each product only once', path: ['items'] },
  )
function CreateOrder({
  onClose,
  onSaved,
}: {
  onClose: () => void
  onSaved: () => void
}) {
  const client = useQueryClient()
  const [key] = useState(() => crypto.randomUUID())
  const stores = useQuery({
    queryKey: ['stores'],
    queryFn: ({ signal }) => retail.stores(signal),
  })
  const suppliers = useQuery({
    queryKey: ['suppliers'],
    queryFn: ({ signal }) => retail.suppliers(signal),
  })
  const form = useForm<z.infer<typeof orderFormSchema>>({
    resolver: zodResolver(orderFormSchema),
    defaultValues: {
      store_id: '',
      supplier_id: '',
      items: [{ product_id: '', quantity: 1 }],
    },
  })
  const lines = useFieldArray({ control: form.control, name: 'items' })
  const supplierId = useWatch({ control: form.control, name: 'supplier_id' })
  const supplier = suppliers.data?.find((item) => item.id === supplierId)
  const mutation = useMutation({
    mutationFn: (body: z.infer<typeof orderFormSchema>) =>
      retail.createOrder(body, key),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['purchase-orders'] })
      onSaved()
      onClose()
    },
  })
  return (
    <Dialog title="Create purchase order" onClose={onClose}>
      <p className="retail-dialog-intro">
        Create a draft using your supplier’s agreed costs. Submit it separately
        for review.
      </p>
      <form
        className="retail-form"
        onSubmit={form.handleSubmit((data) => mutation.mutate(data))}
      >
        <label>
          Store
          <select aria-label="Store" {...form.register('store_id')}>
            <option value="">Choose store</option>
            {stores.data?.map((store) => (
              <option key={store.id} value={store.id}>
                {store.name}
              </option>
            ))}
          </select>
          <small>{form.formState.errors.store_id?.message}</small>
        </label>
        <label>
          Supplier
          <select
            aria-label="Supplier"
            {...form.register('supplier_id')}
            onChange={(e) => {
              void form.setValue('supplier_id', e.target.value)
              form.setValue('items', [{ product_id: '', quantity: 1 }])
            }}
          >
            <option value="">Choose supplier</option>
            {suppliers.data?.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          <small>{form.formState.errors.supplier_id?.message}</small>
        </label>
        {lines.fields.map((line, index) => (
          <div className="retail-order-line" key={line.id}>
            <label>
              Product
              <select
                aria-label="Product"
                {...form.register(`items.${index}.product_id`)}
                disabled={!supplier}
              >
                <option value="">Choose product</option>
                {supplier?.terms.map((term) => (
                  <option key={term.product_id} value={term.product_id}>
                    {term.product_name} · {formatMoney(term.cost)} · min{' '}
                    {term.minimum_order_quantity}, pack {term.pack_size}
                  </option>
                ))}
              </select>
              <small>
                {form.formState.errors.items?.[index]?.product_id?.message}
              </small>
            </label>
            <label>
              Quantity
              <input
                type="number"
                aria-label="Quantity"
                min="1"
                {...form.register(`items.${index}.quantity`, {
                  valueAsNumber: true,
                })}
              />
              <small>
                {form.formState.errors.items?.[index]?.quantity?.message}
              </small>
            </label>
            <button
              type="button"
              className="retail-text-button"
              disabled={lines.fields.length === 1}
              onClick={() => lines.remove(index)}
            >
              Remove
            </button>
          </div>
        ))}
        <small role="alert">
          {form.formState.errors.items?.root?.message ||
            form.formState.errors.items?.message}
        </small>
        <button
          type="button"
          className="retail-button"
          disabled={!supplier}
          onClick={() => lines.append({ product_id: '', quantity: 1 })}
        >
          Add line item
        </button>
        {(stores.error || suppliers.error) && (
          <p role="alert">Could not load order options. Close and try again.</p>
        )}
        {mutation.error && <p role="alert">{mutation.error.message}</p>}
        <button className="retail-button primary" disabled={mutation.isPending}>
          {mutation.isPending ? 'Creating…' : 'Create draft'}
        </button>
      </form>
    </Dialog>
  )
}
const statusTone = (status: PurchaseOrder['status']) =>
  status === 'approved' || status === 'received'
    ? 'green'
    : status === 'pending'
      ? 'amber'
      : status === 'rejected'
        ? 'red'
        : 'neutral'
function ReviewOrder({
  order,
  onClose,
  canManage,
  onSaved,
}: {
  order: PurchaseOrder
  onClose: () => void
  canManage: boolean
  onSaved: () => void
}) {
  const client = useQueryClient()
  const [reason, setReason] = useState('')
  const [key] = useState(() => crypto.randomUUID())
  const mutation = useMutation({
    mutationFn: (action: 'submit' | 'approve' | 'reject' | 'receive') =>
      retail.transition(order.id, action, reason, key),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['purchase-orders'] })
      void client.invalidateQueries({ queryKey: ['inventory'] })
      void client.invalidateQueries({ queryKey: ['dashboard'] })
      onSaved()
      onClose()
    },
  })
  return (
    <Dialog
      title={`Purchase order ${order.id.slice(0, 8).toUpperCase()}`}
      onClose={onClose}
    >
      <div className="retail-order-summary">
        <div>
          <strong>{order.supplier_name}</strong>
          <p>
            {order.store_name} · {formatDate(order.created_at)}
          </p>
        </div>
        <Badge tone={statusTone(order.status)}>{order.status}</Badge>
      </div>
      <DataTable
        rows={order.items.map((item) => ({ ...item, id: item.product_id }))}
        columns={[
          { key: 'name', title: 'Product', render: (row) => row.product_name },
          { key: 'quantity', title: 'Quantity', render: (row) => row.quantity },
          {
            key: 'cost',
            title: 'Unit cost',
            render: (row) => formatMoney(row.unit_cost),
          },
          {
            key: 'total',
            title: 'Line total',
            render: (row) => formatMoney(row.line_total),
          },
        ]}
      />
      <p className="retail-order-total">
        Order total <strong>{formatMoney(order.total)}</strong>
      </p>
      {order.approvals.length > 0 && (
        <div className="retail-activity">
          <h3>Approval history</h3>
          {order.approvals.map((item) => (
            <p key={item.id}>
              <span>
                {item.decision} · {item.actor_name}
              </span>
              <small>
                {formatDate(item.created_at)}
                {item.reason ? ` · ${item.reason}` : ''}
              </small>
            </p>
          ))}
        </div>
      )}
      {canManage && !['rejected', 'received'].includes(order.status) && (
        <div className="retail-form">
          <label>
            Decision note
            <textarea
              value={reason}
              maxLength={500}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Add context for this action"
            />
          </label>
          {mutation.error && <p role="alert">{mutation.error.message}</p>}
          <div className="retail-actions">
            {order.status === 'draft' && (
              <button
                className="retail-button primary"
                disabled={mutation.isPending}
                onClick={() => mutation.mutate('submit')}
              >
                Submit for review
              </button>
            )}
            {order.status === 'pending' && (
              <>
                <button
                  className="retail-button primary"
                  disabled={mutation.isPending}
                  onClick={() => mutation.mutate('approve')}
                >
                  Approve order
                </button>
                <button
                  className="retail-button danger"
                  disabled={mutation.isPending || reason.trim().length < 5}
                  onClick={() => mutation.mutate('reject')}
                >
                  Reject order
                </button>
                <small>
                  A rejection requires a reason of at least 5 characters.
                </small>
              </>
            )}
            {order.status === 'approved' && (
              <>
                <p>
                  Confirm the complete delivery has arrived. Receiving updates
                  audited stock quantities.
                </p>
                <button
                  className="retail-button primary"
                  disabled={mutation.isPending}
                  onClick={() => mutation.mutate('receive')}
                >
                  Confirm delivery received
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </Dialog>
  )
}
export function PurchaseOrdersPage() {
  const { user } = useAuth()
  const canManage = user?.role === 'admin' || user?.role === 'manager'
  const [create, setCreate] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const [status, setStatus] = useState('all')
  const [page, setPage] = useState(1)
  const query = useQuery({
    queryKey: ['purchase-orders', status, page],
    queryFn: ({ signal }) =>
      retail.orders({ status, page, page_size: 20 }, signal),
  })
  const order = query.data?.items.find((item) => item.id === selected)
  return (
    <div className="retail-page">
      <PageHeading
        title="Purchase orders"
        description="From draft to delivery. Keep replenishment under control."
      >
        {canManage && (
          <button
            className="retail-button primary"
            onClick={() => setCreate(true)}
          >
            <Plus size={16} />
            Create purchase order
          </button>
        )}
      </PageHeading>
      <div className="retail-filters">
        <label className="retail-filter-label">
          Order status
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value)
              setPage(1)
              setSelected(null)
            }}
          >
            <option value="all">All orders</option>
            {['draft', 'pending', 'approved', 'rejected', 'received'].map(
              (value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ),
            )}
          </select>
        </label>
      </div>
      <QueryState
        pending={query.isPending}
        error={query.error}
        retry={query.refetch}
      />
      {query.data && (
        <Panel title="Procurement ledger">
          <DataTable
            rows={query.data.items}
            columns={[
              {
                key: 'id',
                title: 'Order',
                render: (row) => (
                  <button
                    className="retail-text-button retail-code"
                    onClick={() => setSelected(row.id)}
                  >
                    {row.id.slice(0, 8).toUpperCase()}
                    <small>Review details →</small>
                  </button>
                ),
              },
              {
                key: 'supplier',
                title: 'Supplier',
                render: (row) => row.supplier_name,
              },
              { key: 'store', title: 'Store', render: (row) => row.store_name },
              {
                key: 'date',
                title: 'Created',
                render: (row) => formatDate(row.created_at),
              },
              {
                key: 'total',
                title: 'Total',
                render: (row) => formatMoney(row.total),
              },
              {
                key: 'status',
                title: 'Status',
                render: (row) => (
                  <Badge tone={statusTone(row.status)}>{row.status}</Badge>
                ),
              },
            ]}
          />
          <Pagination
            page={page}
            total={query.data.total}
            onChange={(nextPage) => {
              setPage(nextPage)
              setSelected(null)
            }}
          />
        </Panel>
      )}
      {create && (
        <CreateOrder
          onClose={() => setCreate(false)}
          onSaved={() => setPage(1)}
        />
      )}
      {order && (
        <ReviewOrder
          order={order}
          canManage={canManage}
          onClose={() => setSelected(null)}
          onSaved={() => setPage(1)}
        />
      )}
    </div>
  )
}
