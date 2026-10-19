import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Search, Plus } from 'lucide-react'
import { DataTable } from '../../components/ui/DataTable'
import { apiRequest } from '../../lib/api'
import {
  formatMoney,
  productSchema,
  retail,
  type Product,
} from '../../services/retail'
import { useAuth } from '../auth/AuthProvider'
import {
  CategorySelect,
  Dialog,
  PageHeading,
  Pagination,
  Panel,
  QueryState,
} from './shared'
import './retail.css'

const productForm = z.object({
  sku: z.string().trim().min(1).max(80),
  name: z.string().trim().min(1).max(200),
  category_id: z.string().uuid('Choose a category'),
  unit_cost: z
    .string()
    .regex(
      /^\d+(\.\d{1,2})?$/,
      'Use a positive amount with up to two decimal places',
    ),
  unit_price: z
    .string()
    .regex(
      /^\d+(\.\d{1,2})?$/,
      'Use a positive amount with up to two decimal places',
    ),
  reorder_point: z.number().int().nonnegative(),
})
function ProductForm({ onClose }: { onClose: () => void }) {
  const client = useQueryClient()
  const categories = useQuery({
    queryKey: ['categories'],
    queryFn: ({ signal }) => retail.categories(signal),
  })
  const form = useForm<z.infer<typeof productForm>>({
    resolver: zodResolver(productForm),
    defaultValues: {
      sku: '',
      name: '',
      category_id: '',
      unit_cost: '',
      unit_price: '',
      reorder_point: 10,
    },
  })
  const mutation = useMutation({
    mutationFn: (body: z.infer<typeof productForm>) =>
      apiRequest('/api/v1/products', productSchema, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['products'] })
      onClose()
    },
  })
  return (
    <Dialog title="Add a product" onClose={onClose}>
      <form
        className="retail-form"
        onSubmit={form.handleSubmit((data) => mutation.mutate(data))}
      >
        {(['sku', 'name', 'unit_cost', 'unit_price'] as const).map((key) => (
          <label key={key}>
            {key.replaceAll('_', ' ')}
            <input {...form.register(key)} autoComplete="off" />
            {form.formState.errors[key] && (
              <small role="alert">{form.formState.errors[key]?.message}</small>
            )}
          </label>
        ))}
        <label>
          Category
          <select {...form.register('category_id')}>
            <option value="">Select category</option>
            {categories.data?.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          <small>{form.formState.errors.category_id?.message}</small>
        </label>
        <label>
          Reorder point
          <input
            type="number"
            min="0"
            {...form.register('reorder_point', { valueAsNumber: true })}
          />
          <small>{form.formState.errors.reorder_point?.message}</small>
        </label>
        {mutation.error && <p role="alert">{mutation.error.message}</p>}
        <button className="retail-button primary" disabled={mutation.isPending}>
          {mutation.isPending ? 'Saving…' : 'Create product'}
        </button>
      </form>
    </Dialog>
  )
}
export function ProductsPage() {
  const { user } = useAuth()
  const [q, setQ] = useState('')
  const [category, setCategory] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<Product | null>(null)
  const [create, setCreate] = useState(false)
  const query = useQuery({
    queryKey: ['products', q, category, page],
    queryFn: ({ signal }) =>
      retail.products(
        { q, category_id: category, page, page_size: 20 },
        signal,
      ),
  })
  return (
    <div className="retail-page">
      <PageHeading
        title="Products"
        description="Your product catalog, pricing, and category details."
      >
        {(user?.role === 'manager' || user?.role === 'admin') && (
          <button
            className="retail-button primary"
            onClick={() => setCreate(true)}
          >
            <Plus size={16} />
            Add product
          </button>
        )}
      </PageHeading>
      <div className="retail-filters">
        <label className="retail-search">
          <Search size={17} />
          <input
            aria-label="Search products"
            placeholder="Search products or SKU…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value)
              setPage(1)
            }}
          />
        </label>
        <CategorySelect
          value={category}
          onChange={(value) => {
            setCategory(value)
            setPage(1)
          }}
        />
      </div>
      <QueryState
        pending={query.isPending}
        error={query.error}
        retry={query.refetch}
      />
      {query.data && (
        <Panel
          title="Product catalog"
          description="Select a product to inspect its details"
        >
          <DataTable
            rows={query.data.items}
            columns={[
              {
                key: 'name',
                title: 'Product',
                render: (row) => (
                  <button
                    className="retail-text-button"
                    onClick={() => setSelected(row)}
                  >
                    {row.name}
                    <small>{row.sku}</small>
                  </button>
                ),
              },
              {
                key: 'category',
                title: 'Category',
                render: (row) => row.category_name,
              },
              {
                key: 'cost',
                title: 'Unit cost',
                render: (row) => formatMoney(row.unit_cost),
              },
              {
                key: 'price',
                title: 'Selling price',
                render: (row) => formatMoney(row.unit_price),
              },
            ]}
          />
          <Pagination page={page} total={query.data.total} onChange={setPage} />
        </Panel>
      )}
      {selected && (
        <Dialog title={selected.name} onClose={() => setSelected(null)}>
          <dl className="retail-details">
            <dt>SKU</dt>
            <dd>{selected.sku}</dd>
            <dt>Category</dt>
            <dd>{selected.category_name}</dd>
            <dt>Unit cost</dt>
            <dd>{formatMoney(selected.unit_cost)}</dd>
            <dt>Selling price</dt>
            <dd>{formatMoney(selected.unit_price)}</dd>
          </dl>
        </Dialog>
      )}
      {create && <ProductForm onClose={() => setCreate(false)} />}
    </div>
  )
}
export function SuppliersPage() {
  const [selected, setSelected] = useState<string | null>(null)
  const query = useQuery({
    queryKey: ['suppliers'],
    queryFn: ({ signal }) => retail.suppliers(signal),
  })
  const supplier = query.data?.find((item) => item.id === selected)
  return (
    <div className="retail-page">
      <PageHeading
        title="Suppliers"
        description="Your supply partners and agreed procurement terms."
      />
      <QueryState
        pending={query.isPending}
        error={query.error}
        retry={query.refetch}
      />
      {query.data && (
        <Panel title="Supplier directory">
          <DataTable
            rows={query.data}
            columns={[
              {
                key: 'name',
                title: 'Supplier',
                render: (row) => (
                  <button
                    className="retail-text-button"
                    onClick={() => setSelected(row.id)}
                  >
                    {row.name}
                    <small>View product terms →</small>
                  </button>
                ),
              },
              {
                key: 'email',
                title: 'Contact',
                render: (row) => (
                  <a href={`mailto:${row.email}`}>{row.email}</a>
                ),
              },
              {
                key: 'lead',
                title: 'Lead time',
                render: (row) => `${row.lead_time_days} days`,
              },
              {
                key: 'products',
                title: 'Products supplied',
                render: (row) => row.terms.length,
              },
            ]}
          />
        </Panel>
      )}
      {supplier && (
        <Dialog
          title={`${supplier.name} · Supply terms`}
          onClose={() => setSelected(null)}
        >
          <DataTable
            rows={supplier.terms.map((term) => ({
              ...term,
              id: term.product_id,
            }))}
            columns={[
              {
                key: 'product',
                title: 'Product',
                render: (row) => (
                  <span>
                    {row.product_name}
                    <small className="retail-muted">
                      {row.supplier_product_code}
                    </small>
                  </span>
                ),
              },
              {
                key: 'cost',
                title: 'Cost',
                render: (row) => formatMoney(row.cost),
              },
              {
                key: 'minimum',
                title: 'Minimum / Pack',
                render: (row) =>
                  `${row.minimum_order_quantity} / ${row.pack_size}`,
              },
              {
                key: 'lead',
                title: 'Lead time',
                render: (row) => `${row.lead_time_days} days`,
              },
            ]}
          />
        </Dialog>
      )}
    </div>
  )
}
