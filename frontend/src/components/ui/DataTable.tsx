import type { ReactNode } from 'react'
export type Column<T> = {
  key: string
  title: string
  render: (row: T) => ReactNode
}
export function DataTable<T extends { id: string }>({
  rows,
  columns,
  empty = 'No records match these filters.',
}: {
  rows: T[]
  columns: Column<T>[]
  empty?: string
}) {
  return (
    <div className="retail-table-wrap">
      <table className="retail-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col">
                {column.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length ? (
            rows.map((row) => (
              <tr key={row.id}>
                {columns.map((column) => (
                  <td key={column.key}>{column.render(row)}</td>
                ))}
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={columns.length}>
                <div className="retail-empty">{empty}</div>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
