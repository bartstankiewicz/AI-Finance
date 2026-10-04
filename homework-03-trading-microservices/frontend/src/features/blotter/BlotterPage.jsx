import { useCallback } from 'react'
import DataTable from '../../components/DataTable.jsx'
import StreamStatusBadge from '../../components/StreamStatusBadge.jsx'
import usePolling from '../../hooks/usePolling.js'
import usePersistentState from '../../hooks/usePersistentState.js'
import { getBooksSummary, getTrades } from '../../api/blotter.js'
import { formatNumber, shortId } from '../../utils/format.js'
import { formatPnl } from './formatPnl.jsx'
import TradeDetails from './TradeDetails.jsx'
import TradeFilters, { EMPTY_FILTERS } from './TradeFilters.jsx'
import useLiveValuations from './useLiveValuations.js'
import './BlotterPage.scss'

const BOOKS_POLL_MS = 5000
const TRADES_POLL_MS = 5000 // only to pick up new/closed trades - values are overlaid live from SSE
const TRADES_LIMIT = 50

// Book unrealized PnL is live once every active trade of the book has a streamed valuation;
// until then (first seconds after opening) the DB aggregate from /books/summary is shown.
function withLiveBookPnl(books, liveByTrade) {
  const live = {}
  for (const v of Object.values(liveByTrade)) {
    const agg = (live[v.book_id] ??= { count: 0, unrealized: 0 })
    agg.count += 1
    agg.unrealized += v.unrealized_pnl
  }
  return books.map((book) => {
    const agg = live[book.book_id]
    const isLive = Boolean(agg) && agg.count >= book.active_trades
    const unrealized = isLive ? agg.unrealized : book.unrealized_pnl
    return { ...book, unrealized_pnl: unrealized, total_pnl: book.realized_pnl + unrealized }
  })
}

const withLiveTradeValues = (trade, valuation) =>
  valuation
    ? {
        ...trade,
        fair_value: valuation.fair_value,
        unrealized_pnl: valuation.unrealized_pnl,
        realized_pnl: valuation.realized_pnl,
        total_pnl: valuation.total_pnl,
      }
    : trade

export default function BlotterPage() {
  const { byTrade, status } = useLiveValuations()
  const { data: books, error: booksError } = usePolling(getBooksSummary, BOOKS_POLL_MS)
  const [filters, setFilters] = usePersistentState('blotter.filters', EMPTY_FILTERS)
  const [selectedTradeId, setSelectedTradeId] = usePersistentState('blotter.selectedTrade', null)

  const fetchTrades = useCallback(
    () => getTrades({ limit: TRADES_LIMIT, book_id: filters.bookId, asset_class: filters.assetClass, status: filters.status }),
    [filters.bookId, filters.assetClass, filters.status],
  )
  const { data: trades, error: tradesError } = usePolling(fetchTrades, TRADES_POLL_MS)

  const bookRows = withLiveBookPnl(books ?? [], byTrade)
  const bookNames = Object.fromEntries(bookRows.map((book) => [book.book_id, book.name]))
  const tradeRows = (trades ?? []).map((trade) => withLiveTradeValues(trade, byTrade[trade.trade_id]))

  const toggleBookFilter = (bookId) =>
    setFilters({ ...filters, bookId: filters.bookId === bookId ? '' : bookId })

  // alpha / beta are not returned by blotter-service yet - shown as "—" until they are
  const bookColumns = [
    { key: 'name', label: 'Book' },
    { key: 'expected_asset_class', label: 'Asset Class' },
    { key: 'active_trades', label: 'Active Trades' },
    { key: 'realized_pnl', label: 'Realized PnL', format: formatPnl },
    { key: 'unrealized_pnl', label: 'Unrealized PnL', format: formatPnl },
    { key: 'total_pnl', label: 'Total PnL', format: formatPnl },
    { key: 'alpha', label: 'Alpha', format: (v) => formatNumber(v, 4) },
    { key: 'beta', label: 'Beta', format: (v) => formatNumber(v, 2) },
    {
      key: 'trades',
      label: 'Trades',
      render: (row) => (
        <button
          className={row.book_id === filters.bookId ? 'btn btn--primary' : 'btn'}
          onClick={() => toggleBookFilter(row.book_id)}
        >
          Show
        </button>
      ),
    },
  ]

  const tradeColumns = [
    { key: 'trade_id', label: 'Trade', format: shortId },
    { key: 'book_id', label: 'Book', format: (id) => bookNames[id] ?? shortId(id) },
    { key: 'asset_class', label: 'Asset Class' },
    { key: 'symbol', label: 'Symbol' },
    { key: 'side', label: 'Side' },
    { key: 'quantity', label: 'Qty' },
    { key: 'trade_price', label: 'Trade Price' },
    { key: 'status', label: 'Status' },
    { key: 'fair_value', label: 'Fair Value', format: formatNumber },
    { key: 'unrealized_pnl', label: 'Unrealized', format: formatPnl },
    { key: 'realized_pnl', label: 'Realized', format: formatPnl },
    {
      key: 'details',
      label: 'Details',
      render: (row) => (
        <button
          className={row.trade_id === selectedTradeId ? 'btn btn--primary' : 'btn'}
          onClick={() => setSelectedTradeId(row.trade_id)}
        >
          Details
        </button>
      ),
    },
  ]

  return (
    <>
      <section className="section">
        <h2>Books</h2>
        {booksError && <p className="error">Cannot load books: {booksError.message}</p>}
        <DataTable columns={bookColumns} rows={bookRows} rowKey="book_id" />
      </section>

      <section className="section">
        <h2>
          Trades
          <StreamStatusBadge status={status} />
        </h2>
        <TradeFilters books={bookRows} filters={filters} onChange={setFilters} />
        {tradesError && <p className="error">Cannot load trades: {tradesError.message}</p>}
        <DataTable columns={tradeColumns} rows={tradeRows} rowKey="trade_id" />
        <p className="muted">
          Showing the {TRADES_LIMIT} most recent trades. Fair value and PnL update live from the valuation stream.
        </p>
      </section>

      {selectedTradeId && (
        <TradeDetails
          key={selectedTradeId}
          tradeId={selectedTradeId}
          row={tradeRows.find((trade) => trade.trade_id === selectedTradeId)}
          live={byTrade[selectedTradeId]}
          bookNames={bookNames}
          onClose={() => setSelectedTradeId(null)}
        />
      )}
    </>
  )
}
