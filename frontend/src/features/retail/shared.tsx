import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, type ReactNode } from 'react'
import { retail } from '../../services/retail'

export function PageHeading({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children?: ReactNode
}) {
  return (
    <header className="retail-heading">
      <div>
        <p className="retail-eyebrow">YOUR RETAIL WORKSPACE</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {children}
    </header>
  )
}
export function QueryState({
  pending,
  error,
  retry,
}: {
  pending: boolean
  error: Error | null
  retry: () => unknown
}) {
  if (pending)
    return (
      <div className="retail-state" role="status">
        <span className="retail-spinner" /> Loading your workspace…
      </div>
    )
  if (error)
    return (
      <div className="retail-state retail-error" role="alert">
        <strong>We couldn’t load this data.</strong>
        <p>{error.message}</p>
        <button className="retail-button" onClick={() => retry()}>
          Try again
        </button>
      </div>
    )
  return null
}
export function Panel({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <section className="retail-panel">
      <header>
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </header>
      {children}
    </section>
  )
}
export function Pagination({
  page,
  total,
  size = 20,
  onChange,
}: {
  page: number
  total: number
  size?: number
  onChange: (page: number) => void
}) {
  return (
    <div className="retail-pagination">
      <span>
        {total.toLocaleString('en-IN')} records · Page {page} of{' '}
        {Math.max(1, Math.ceil(total / size))}
      </span>
      <div>
        <button disabled={page <= 1} onClick={() => onChange(page - 1)}>
          Previous
        </button>
        <button
          disabled={page * size >= total}
          onClick={() => onChange(page + 1)}
        >
          Next
        </button>
      </div>
    </div>
  )
}
export function StoreSelect({
  value,
  onChange,
}: {
  value: string
  onChange: (value: string) => void
}) {
  const query = useQuery({
    queryKey: ['stores'],
    queryFn: ({ signal }) => retail.stores(signal),
  })
  return (
    <label className="retail-filter-label">
      Store
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Filter by store"
      >
        <option value="">All stores</option>
        {query.data?.map((store) => (
          <option value={store.id} key={store.id}>
            {store.name}
          </option>
        ))}
      </select>
      {query.error && <small role="alert">Stores unavailable</small>}
    </label>
  )
}
export function CategorySelect({
  value,
  onChange,
}: {
  value: string
  onChange: (value: string) => void
}) {
  const query = useQuery({
    queryKey: ['categories'],
    queryFn: ({ signal }) => retail.categories(signal),
  })
  return (
    <label className="retail-filter-label">
      Category
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Filter by category"
      >
        <option value="">All categories</option>
        {query.data?.map((category) => (
          <option value={category.id} key={category.id}>
            {category.name}
          </option>
        ))}
      </select>
      {query.error && <small role="alert">Categories unavailable</small>}
    </label>
  )
}
export function DateFilters({
  start,
  end,
  onStart,
  onEnd,
}: {
  start: string
  end: string
  onStart: (value: string) => void
  onEnd: (value: string) => void
}) {
  return (
    <>
      <label className="retail-filter-label">
        From
        <input
          type="date"
          value={start}
          max={end}
          onChange={(e) => onStart(e.target.value)}
        />
      </label>
      <label className="retail-filter-label">
        To
        <input
          type="date"
          value={end}
          min={start}
          onChange={(e) => onEnd(e.target.value)}
        />
      </label>
    </>
  )
}
export function Badge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode
  tone?: 'neutral' | 'green' | 'amber' | 'red'
}) {
  return <span className={`retail-badge ${tone}`}>{children}</span>
}
export function Dialog({
  title,
  onClose,
  children,
}: {
  title: string
  onClose: () => void
  children: ReactNode
}) {
  const dialogRef = useRef<HTMLElement>(null)
  useEffect(() => {
    const previous =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
    const dialog = dialogRef.current
    dialog
      ?.querySelector<HTMLElement>(
        'button, input, select, textarea, [tabindex="0"]',
      )
      ?.focus()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previousOverflow
      previous?.focus()
    }
  }, [])
  return (
    <div
      className="retail-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <section
        ref={dialogRef}
        className="retail-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onKeyDown={(event) => {
          if (event.key === 'Escape') onClose()
          if (event.key !== 'Tab') return
          const elements = dialogRef.current?.querySelectorAll<HTMLElement>(
            'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]',
          )
          const first = elements?.[0]
          const last = elements?.[elements.length - 1]
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault()
            last?.focus()
          }
          if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault()
            first?.focus()
          }
        }}
      >
        <header>
          <h2>{title}</h2>
          <button aria-label="Close dialog" onClick={onClose}>
            ×
          </button>
        </header>
        {children}
      </section>
    </div>
  )
}
