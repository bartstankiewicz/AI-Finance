import { ASSET_CLASSES, TRADE_STATUSES } from '../../constants.js'

export const EMPTY_FILTERS = { bookId: '', assetClass: '', status: '' }

export default function TradeFilters({ books, filters, onChange }) {
  const setFilter = (key, value) => onChange({ ...filters, [key]: value })
  const isEmpty = Object.entries(EMPTY_FILTERS).every(([key, value]) => filters[key] === value)

  return (
    <div className="trade-filters">
      <label>
        Book
        <select className="input" value={filters.bookId} onChange={(e) => setFilter('bookId', e.target.value)}>
          <option value="">All books</option>
          {books.map((book) => <option key={book.book_id} value={book.book_id}>{book.name}</option>)}
        </select>
      </label>
      <label>
        Asset class
        <select className="input" value={filters.assetClass} onChange={(e) => setFilter('assetClass', e.target.value)}>
          <option value="">All asset classes</option>
          {ASSET_CLASSES.map((assetClass) => <option key={assetClass}>{assetClass}</option>)}
        </select>
      </label>
      <label>
        Status
        <select className="input" value={filters.status} onChange={(e) => setFilter('status', e.target.value)}>
          <option value="">All statuses</option>
          {TRADE_STATUSES.map((status) => <option key={status}>{status}</option>)}
        </select>
      </label>
      <button className="btn" disabled={isEmpty} onClick={() => onChange(EMPTY_FILTERS)}>Clear filters</button>
    </div>
  )
}
