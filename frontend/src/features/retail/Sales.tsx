import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { DataTable } from '../../components/ui/DataTable'
import { formatDate, formatMoney, retail } from '../../services/retail'
import {
  DateFilters,
  PageHeading,
  Pagination,
  Panel,
  QueryState,
  StoreSelect,
} from './shared'
import { defaultDates } from './dates'
import './retail.css'
export function SalesPage() {
  const [store, setStore] = useState('')
  const [dates, setDates] = useState(defaultDates)
  const [page, setPage] = useState(1)
  const query = useQuery({
    queryKey: ['sales', store, dates, page],
    queryFn: ({ signal }) =>
      retail.sales(
        {
          store_id: store,
          start_date: dates.start,
          end_date: dates.end,
          page,
          page_size: 20,
        },
        signal,
      ),
  })
  return (
    <div className="retail-page">
      <PageHeading
        title="Sales"
        description="Explore recorded sales and the profit behind every order."
      />
      <div className="retail-filters">
        <StoreSelect
          value={store}
          onChange={(value) => {
            setStore(value)
            setPage(1)
          }}
        />
        <DateFilters
          start={dates.start}
          end={dates.end}
          onStart={(start) => {
            setDates({ ...dates, start })
            setPage(1)
          }}
          onEnd={(end) => {
            setDates({ ...dates, end })
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
        <Panel title="Sales ledger">
          <DataTable
            rows={query.data.items}
            columns={[
              {
                key: 'id',
                title: 'Order',
                render: (row) => (
                  <span className="retail-code">
                    {row.id.slice(0, 8).toUpperCase()}
                  </span>
                ),
              },
              {
                key: 'date',
                title: 'Date',
                render: (row) => formatDate(row.sold_at),
              },
              { key: 'store', title: 'Store', render: (row) => row.store_name },
              { key: 'items', title: 'Items', render: (row) => row.item_count },
              {
                key: 'total',
                title: 'Revenue',
                render: (row) => formatMoney(row.total),
              },
              {
                key: 'profit',
                title: 'Gross profit',
                render: (row) => formatMoney(row.gross_profit),
              },
            ]}
          />
          <Pagination page={page} total={query.data.total} onChange={setPage} />
        </Panel>
      )}
    </div>
  )
}
