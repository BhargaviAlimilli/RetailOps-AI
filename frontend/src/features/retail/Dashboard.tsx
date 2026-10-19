import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  BarChart,
  Bar,
} from 'recharts'
import {
  ArrowUpRight,
  Package,
  ShoppingBag,
  Wallet,
  TrendingUp,
} from 'lucide-react'
import { Link } from 'react-router'
import { formatDate, formatMoney, retail } from '../../services/retail'
import {
  CategorySelect,
  DateFilters,
  PageHeading,
  Panel,
  QueryState,
  StoreSelect,
} from './shared'
import { defaultDates } from './dates'
import './retail.css'

export function RetailDashboard() {
  const [store, setStore] = useState('')
  const [category, setCategory] = useState('')
  const [dates, setDates] = useState(defaultDates)
  const query = useQuery({
    queryKey: ['dashboard', store, category, dates],
    queryFn: ({ signal }) =>
      retail.dashboard(
        {
          store_id: store,
          category_id: category,
          start_date: dates.start,
          end_date: dates.end,
        },
        signal,
      ),
  })
  const data = query.data
  return (
    <div className="retail-page">
      <PageHeading
        title="Business overview"
        description="A clear view of your business. Every store, every day."
      >
        <Link className="retail-button" to="/inventory">
          View inventory <ArrowUpRight size={15} />
        </Link>
      </PageHeading>
      <div className="retail-filters">
        <StoreSelect value={store} onChange={setStore} />
        <CategorySelect value={category} onChange={setCategory} />
        <DateFilters
          start={dates.start}
          end={dates.end}
          onStart={(start) => setDates({ ...dates, start })}
          onEnd={(end) => setDates({ ...dates, end })}
        />
      </div>
      <QueryState
        pending={query.isPending}
        error={query.error}
        retry={query.refetch}
      />
      {data && (
        <>
          <div className="retail-kpis">
            {[
              {
                label: 'Total revenue',
                value: formatMoney(data.revenue),
                icon: Wallet,
                note:
                  data.revenue_change_percent === null
                    ? 'No comparable previous period'
                    : `${data.revenue_change_percent}% vs previous period`,
              },
              {
                label: 'Gross profit',
                value: formatMoney(data.gross_profit),
                icon: TrendingUp,
                note: `${data.gross_margin}% gross margin`,
              },
              {
                label: 'Sales orders',
                value: data.order_count.toLocaleString('en-IN'),
                icon: ShoppingBag,
                note: `${formatMoney(data.average_order_value)} average order`,
              },
              {
                label: 'Inventory value',
                value: formatMoney(data.inventory_valuation),
                icon: Package,
                note: `${data.low_stock_count} low stock · ${data.out_of_stock_count} out of stock`,
              },
            ].map((metric) => (
              <article className="retail-kpi" key={metric.label}>
                <div>
                  <span>{metric.label}</span>
                  <metric.icon size={19} />
                </div>
                <strong>{metric.value}</strong>
                <small>{metric.note}</small>
              </article>
            ))}
          </div>
          <div className="retail-chart-grid">
            <Panel
              title="Revenue performance"
              description="Revenue and gross profit across the selected period"
            >
              <div className="retail-chart">
                {data.trend.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={data.trend.map((item) => ({
                        ...item,
                        revenue: Number(item.revenue),
                        gross_profit: Number(item.gross_profit),
                      }))}
                    >
                      <defs>
                        <linearGradient
                          id="revenueFill"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="0%"
                            stopColor="#4b8e75"
                            stopOpacity={0.3}
                          />
                          <stop
                            offset="100%"
                            stopColor="#4b8e75"
                            stopOpacity={0}
                          />
                        </linearGradient>
                      </defs>
                      <CartesianGrid
                        strokeDasharray="4 4"
                        vertical={false}
                        stroke="#e9efeb"
                      />
                      <XAxis
                        dataKey="date"
                        tickFormatter={(value) => String(value).slice(5)}
                        tickLine={false}
                        axisLine={false}
                      />
                      <YAxis
                        tickFormatter={(value) =>
                          `₹${Number(value) >= 1000 ? `${Number(value) / 1000}k` : value}`
                        }
                        tickLine={false}
                        axisLine={false}
                        width={60}
                      />
                      <Tooltip
                        formatter={(value) => formatMoney(String(value))}
                      />
                      <Area
                        isAnimationActive={false}
                        name="Revenue"
                        dataKey="revenue"
                        stroke="#36765e"
                        fill="url(#revenueFill)"
                        strokeWidth={2.5}
                      />
                      <Area
                        isAnimationActive={false}
                        name="Gross profit"
                        dataKey="gross_profit"
                        stroke="#b3a05f"
                        fill="transparent"
                        strokeWidth={2}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="retail-empty">No sales in this period.</p>
                )}
              </div>
            </Panel>
            <Panel title="Sales by category" description="Revenue contribution">
              <div className="retail-chart">
                {data.by_category.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={data.by_category.map((item) => ({
                        ...item,
                        revenue: Number(item.revenue),
                      }))}
                      layout="vertical"
                    >
                      <CartesianGrid horizontal={false} stroke="#e9efeb" />
                      <XAxis type="number" hide />
                      <YAxis
                        type="category"
                        dataKey="name"
                        width={110}
                        axisLine={false}
                        tickLine={false}
                        tick={{ fontSize: 11 }}
                      />
                      <Tooltip
                        formatter={(value) => formatMoney(String(value))}
                      />
                      <Bar
                        isAnimationActive={false}
                        name="Revenue"
                        dataKey="revenue"
                        fill="#769581"
                        radius={[0, 5, 5, 0]}
                        barSize={22}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="retail-empty">No category sales yet.</p>
                )}
              </div>
            </Panel>
          </div>
          <div className="retail-chart-grid">
            <Panel
              title="Top performing products"
              description="Products leading your sales"
            >
              <div className="retail-ranking">
                {data.top_products.length ? (
                  data.top_products.map((product, index) => (
                    <div key={product.id}>
                      <span className="retail-rank">
                        {String(index + 1).padStart(2, '0')}
                      </span>
                      <div>
                        <strong>{product.name}</strong>
                        <small>
                          {product.sku} · {product.quantity} units sold
                        </small>
                      </div>
                      <b>{formatMoney(product.revenue)}</b>
                    </div>
                  ))
                ) : (
                  <p className="retail-empty">
                    No product sales in this period.
                  </p>
                )}
              </div>
            </Panel>
            <Panel
              title="Operations at a glance"
              description="Keep your next actions in view"
            >
              <div className="retail-operation">
                <span>Purchase orders awaiting approval</span>
                <strong>{data.pending_purchase_orders}</strong>
                <Link to="/purchase-orders">Review orders →</Link>
              </div>
              <div className="retail-operation">
                <span>Products below reorder point</span>
                <strong>{data.low_stock_count}</strong>
                <Link to="/inventory">Check stock →</Link>
              </div>
              <div className="retail-activity">
                <h3>Recent workspace activity</h3>
                {data.recent_activity.slice(0, 3).map((item) => (
                  <p key={item.id}>
                    <span>{activityLabel(item.action)}</span>
                    <small>
                      {item.actor_name} · {formatDate(item.created_at)}
                    </small>
                  </p>
                ))}
              </div>
            </Panel>
          </div>
          <div className="retail-chart-grid">
            <Panel title="Store performance">
              <div className="retail-ranking">
                {data.by_store.length ? (
                  data.by_store.map((item) => (
                    <div key={item.name}>
                      <div>
                        <strong>{item.name}</strong>
                        <small>{item.order_count} orders</small>
                      </div>
                      <b>{formatMoney(item.revenue)}</b>
                    </div>
                  ))
                ) : (
                  <p className="retail-empty">No store sales yet.</p>
                )}
              </div>
            </Panel>
            <Panel
              title="Slow moving products"
              description="Products to review for your next replenishment"
            >
              <div className="retail-ranking">
                {data.slow_products.length ? (
                  data.slow_products.map((item) => (
                    <div key={item.id}>
                      <div>
                        <strong>{item.name}</strong>
                        <small>{item.sku}</small>
                      </div>
                      <b>{item.quantity} sold</b>
                    </div>
                  ))
                ) : (
                  <p className="retail-empty">
                    No slow moving products to show.
                  </p>
                )}
              </div>
            </Panel>
          </div>
        </>
      )}
    </div>
  )
}

function activityLabel(action: string) {
  const labels: Record<string, string> = {
    'auth.login': 'Signed in',
    'auth.logout': 'Signed out',
    'inventory.adjusted': 'Stock adjusted',
    'product.created': 'Product added',
    'purchase_order.created': 'Purchase order drafted',
    'purchase_order.submit': 'Order submitted for review',
    'purchase_order.approve': 'Order approved',
    'purchase_order.reject': 'Order rejected',
    'purchase_order.receive': 'Delivery received',
    'demo.seed.v1': 'Synthetic workspace initialized',
  }
  return labels[action] ?? 'Workspace updated'
}
