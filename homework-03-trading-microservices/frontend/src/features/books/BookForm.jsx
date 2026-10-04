import { useState } from 'react'
import { createBook, updateBook } from '../../api/books.js'
import { ASSET_CLASSES } from '../../constants.js'

const EMPTY_BOOK = { name: '', description: '', expected_asset_class: 'EQUITY', is_active: true }

export default function BookForm({ book, onSaved, onCancel }) {
  const [form, setForm] = useState(book ?? EMPTY_BOOK)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }))

  const handleSubmit = async (event) => {
    event.preventDefault() // stop the browser's default full-page form submit
    setSaving(true)
    setError(null)
    const payload = {
      name: form.name,
      description: form.description,
      expected_asset_class: form.expected_asset_class,
      is_active: form.is_active,
    }
    try {
      if (book) {
        await updateBook(book.book_id, payload)
      } else {
        await createBook(payload)
        setForm(EMPTY_BOOK)
      }
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label>
        Name
        <input className="input" required value={form.name} onChange={(e) => setField('name', e.target.value)} />
      </label>
      <label>
        Description
        <input
          className="input"
          value={form.description ?? ''}
          onChange={(e) => setField('description', e.target.value)}
        />
      </label>
      <label>
        Asset Class
        <select
          className="input"
          value={form.expected_asset_class}
          onChange={(e) => setField('expected_asset_class', e.target.value)}
        >
          {ASSET_CLASSES.map((assetClass) => <option key={assetClass}>{assetClass}</option>)}
        </select>
      </label>
      <label>
        Active
        <input
          type="checkbox"
          checked={form.is_active}
          onChange={(e) => setField('is_active', e.target.checked)}
        />
      </label>

      {error && <p className="error">{error}</p>}

      <div className="form__actions">
        <button className="btn btn--primary" disabled={saving}>{book ? 'Save' : 'Create'}</button>
        {book && <button type="button" className="btn" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  )
}
