import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Dialog, Pagination } from './shared'
import { DataTable } from '../../components/ui/DataTable'

describe('retail controls', () => {
  it('disables unavailable server page navigation', () => {
    const onChange = vi.fn()
    render(<Pagination page={1} total={21} onChange={onChange} />)
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(onChange).toHaveBeenCalledWith(2)
  })
  it('shows an honest empty state instead of invented rows', () => {
    render(
      <DataTable
        rows={[]}
        columns={[
          {
            key: 'name',
            title: 'Name',
            render: (row: { id: string; name: string }) => row.name,
          },
        ]}
      />,
    )
    expect(screen.getByText('No records match these filters.')).toBeVisible()
    expect(screen.getAllByRole('row')).toHaveLength(2)
  })
  it('traps dialog focus and closes with Escape', () => {
    const onClose = vi.fn()
    render(
      <Dialog title="Review stock" onClose={onClose}>
        <button>Record stock</button>
      </Dialog>,
    )
    const close = screen.getByRole('button', { name: 'Close dialog' })
    const record = screen.getByRole('button', { name: 'Record stock' })
    expect(close).toHaveFocus()
    fireEvent.keyDown(close, { key: 'Tab', shiftKey: true })
    expect(record).toHaveFocus()
    fireEvent.keyDown(record, { key: 'Tab' })
    expect(close).toHaveFocus()
    fireEvent.keyDown(close, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()
  })
})
