import { useState } from 'react'
import DataTable from '../../components/DataTable.jsx'
import Panel from '../../components/Panel.jsx'
import StatusBadge from '../../components/StatusBadge.jsx'
import usePolling from '../../hooks/usePolling.js'
import usePersistentState from '../../hooks/usePersistentState.js'
import { deleteBook, getBooks } from '../../api/books.js'
import { shortId } from '../../utils/format.js'
import BookDetails from './BookDetails.jsx'
import BookForm from './BookForm.jsx'

export default function BooksPage() {
  const { data: books, error, reload } = usePolling(getBooks)
  const [selectedId, setSelectedId] = usePersistentState('books.selectedId', null)
  const [editedId, setEditedId] = useState(null)
  const [actionError, setActionError] = useState(null)

  const selected = books?.find((b) => b.book_id === selectedId)
  const edited = books?.find((b) => b.book_id === editedId)

  const handleDelete = async (book) => {
    if (!window.confirm(`Delete book ${book.name}?`)) return
    setActionError(null)
    try {
      await deleteBook(book.book_id)
      reload()
    } catch (err) {
      setActionError(`Delete failed: ${err.message}`)
    }
  }

  const columns = [
    { key: 'name', label: 'Book Name' },
    { key: 'book_id', label: 'Book ID', format: shortId },
    { key: 'expected_asset_class', label: 'Asset Class' },
    {
      key: 'is_active',
      label: 'Status',
      format: (v) => <StatusBadge status={v ? 'UP' : 'DOWN'}>{v ? 'ACTIVE' : 'INACTIVE'}</StatusBadge>,
    },
    {
      key: 'details',
      label: 'Details',
      render: (row) => <button className="btn" onClick={() => setSelectedId(row.book_id)}>Details</button>,
    },
    {
      key: 'edit',
      label: 'Edit',
      render: (row) => <button className="btn btn--accent" onClick={() => setEditedId(row.book_id)}>Edit</button>,
    },
    {
      key: 'delete',
      label: 'Delete',
      render: (row) => <button className="btn btn--danger" onClick={() => handleDelete(row)}>Delete</button>,
    },
  ]

  return (
    <>
      <section className="section">
        {error && <p className="error">Cannot load books: {error.message}</p>}
        {actionError && <p className="error">{actionError}</p>}
        <DataTable columns={columns} rows={books ?? []} rowKey="book_id" />
      </section>

      <div className="panels">
        <Panel title="Details">
          {selected ? <BookDetails book={selected} /> : <p className="muted">Click „Details” on a book.</p>}
        </Panel>

        <Panel title={edited ? `Edit ${edited.name}` : 'New Book'}>
          {/* key remounts the form, so its local state resets when switching books */}
          <BookForm
            key={editedId ?? 'new'}
            book={edited}
            onSaved={() => {
              setEditedId(null)
              reload()
            }}
            onCancel={() => setEditedId(null)}
          />
        </Panel>
      </div>
    </>
  )
}
