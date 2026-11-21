import { useCallback, useEffect, useMemo, useState } from 'react'
import ColumnSettings from '../../components/ColumnSettings.jsx'
import DataTable from '../../components/DataTable.jsx'
import KpiCard from '../../components/KpiCard.jsx'
import Pagination, { pageCountOf } from '../../components/Pagination.jsx'
import QueryNotice from '../../components/QueryNotice.jsx'
import StreamNotice from '../../components/StreamNotice.jsx'
import StreamStatusBadge from '../../components/StreamStatusBadge.jsx'
import TableFilters, { NoMatches } from '../../components/TableFilters.jsx'
import { getBooks } from '../../api/books.js'
import { getBookMetrics, getTradeValuations, VALUATION_STALE_AFTER_MS } from '../../api/pricing.js'
import useColumnLayout from '../../hooks/useColumnLayout.js'
import usePolling from '../../hooks/usePolling.js'
import useTableView from '../../hooks/useTableView.js'
import { formatAge, formatAlpha, formatDateTime, formatNumber, formatTime, parseTimestamp, shortId } from '../../utils/format.js'
import useValuationStream from './useValuationStream.js'
import './PricingPage.scss'

// Half of TICK_INTERVAL - book metrics change once per tick round
const BOOK_METRICS_POLL_MS = 5000
// Age / staleness of valuations is re-evaluated between stream events
const NOW_REFRESH_MS = 1000
const PAGE_SIZE = 25

const STREAM_STORAGE_KEY = 'pricing.valuations'
const STREAM_DEFAULT_COLUMNS = [
  'symbol', 'trade_id', 'book', 'asset_class', 'fair_value', 'unrealized_pnl', 'realized_pnl', 'pnl_impact',
  'last_pnl_change', 'changes_per_min', 'alpha', 'beta', 'status', 'created_at', 'age',
]
const STREAM_DEFAULT_PINNED = ['symbol']

const pnlClass = (value) => (value > 0 ? 'is-up' : value < 0 ? 'is-down' : undefined)
const staleClass = (row) => (row.status === 'STALE' ? 'is-stale' : undefined)
const formatPercent = (v) => `${(v * 100).toFixed(1)}%`

const streamColumns = (onSearch) => [
  { key: 'symbol', label: 'Symbol', sortable: true, filter: 'text' },
  {
    key: 'trade_id',
    label: 'Trade ID',
    sortable: true,
    filter: 'prefix',
    render: (row) => (
      <button className="btn btn--link" title="Search this trade" onClick={() => onSearch(row.trade_id)}>
        {shortId(row.trade_id)}
      </button>
    ),
  },
  { key: 'book', label: 'Book', sortable: true, filter: 'text' },
  { key: 'asset_class', label: 'Asset Class', sortable: true, filter: 'prefix' },
  { key: 'fair_value', label: 'Fair Value', format: formatNumber, className: staleClass, sortable: true, numeric: true },
  { key: 'unrealized_pnl', label: 'Unrealized PnL', format: formatNumber, className: (row) => staleClass(row) ?? pnlClass(row.unrealized_pnl), sortable: true, numeric: true },
  { key: 'realized_pnl', label: 'Realized PnL', format: formatNumber, className: (row) => pnlClass(row.realized_pnl), sortable: true, numeric: true },
  { key: 'total_pnl', label: 'Total PnL', format: formatNumber, className: (row) => staleClass(row) ?? pnlClass(row.total_pnl), sortable: true, numeric: true },
  // Colored by the sign of the trade's PnL: gain or loss contribution
  { key: 'pnl_impact', label: 'Book PnL Share', format: formatPercent, className: (row) => pnlClass(row.total_pnl), sortable: true, numeric: true },
  { key: 'last_pnl_change', label: 'Last Δ PnL', format: formatNumber, className: (row) => pnlClass(row.last_pnl_change), sortable: true, numeric: true },
  { key: 'changes', label: 'Changes', sortable: true, numeric: true },
  { key: 'changes_per_min', label: 'Changes/min', format: (v) => formatNumber(v, 1), sortable: true, numeric: true },
  { key: 'alpha', label: 'Book Alpha', format: formatAlpha, sortable: true, numeric: true },
  { key: 'beta', label: 'Book Beta', format: (v) => formatNumber(v, 3), sortable: true, numeric: true },
  { key: 'status', label: 'Valuation Status', className: staleClass, sortable: true, filter: 'prefix' },
  { key: 'created_at', label: 'Created At', format: formatTime, sortable: true },
  { key: 'age', label: 'Age', format: formatAge, className: staleClass, sortable: true, numeric: true },
  { key: 'currency', label: 'Ccy', sortable: true },
]

// SETTLED is the final valuation of a closed trade, so only LIVE ones can go stale
// pnl_impact = trade's share of its book's PnL magnitude (|PnL| / Σ|PnL| of the book), so shares are 0-100% and sum to 100%
function toStreamRows(byTrade, bookNames, now) {
  const valuations = Object.values(byTrade).sort((a, b) => b.created_at.localeCompare(a.created_at))
  const bookAbsPnl = {}
  for (const v of valuations) bookAbsPnl[v.book_id] = (bookAbsPnl[v.book_id] ?? 0) + Math.abs(v.total_pnl)
  return valuations.map((v) => {
    const ageMs = now - parseTimestamp(v.created_at)
    const minutesSeen = Math.max(1, (now - v.first_seen_at) / 60_000)
    return {
      ...v,
      book: bookNames[v.book_id] ?? shortId(v.book_id),
      status: v.valuation_status === 'LIVE' && ageMs > VALUATION_STALE_AFTER_MS ? 'STALE' : v.valuation_status,
      age: Math.max(0, Math.round(ageMs / 1000)),
      changes_per_min: v.changes / minutesSeen,
      pnl_impact: bookAbsPnl[v.book_id] ? Math.abs(v.total_pnl) / bookAbsPnl[v.book_id] : null,
    }
  })
}

const topBy = (rows, key) => rows.reduce((best, row) => (!best || row[key] > best[key] ? row : best), null)

const BOOK_METRICS_COLUMNS = [
  { key: 'name', label: 'Book' },
  { key: 'book_id', label: 'Book ID', format: shortId },
  { key: 'alpha', label: 'Alpha', format: formatAlpha, numeric: true },
  { key: 'beta', label: 'Beta', format: (v) => formatNumber(v, 3), numeric: true },
  // Dev aid: alpha/beta stay empty until the window (ALPHA_BETA_WINDOW = 100) is full
  { key: 'observations', label: 'Observations', format: (v) => `${v} / 100`, numeric: true },
  { key: 'updated_at', label: 'Updated', format: formatDateTime },
]

const SEARCH_COLUMNS = [
  { key: 'asset_class', label: 'Asset Class' },
  { key: 'trade_id', label: 'Trade ID', format: shortId },
  { key: 'book_id', label: 'Book ID', format: shortId },
  { key: 'fair_value', label: 'Fair Value', format: formatNumber, numeric: true },
  { key: 'realized_pnl', label: 'Realized PnL', format: formatNumber, numeric: true },
  { key: 'unrealized_pnl', label: 'Unrealized PnL', format: formatNumber, numeric: true },
  { key: 'currency', label: 'Ccy' },
  { key: 'valuation_status', label: 'Valuation Status' },
  { key: 'valuation_time', label: 'Created At', format: formatDateTime },
]

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export default function PricingPage() {
  const { byTrade, status, lastEventAt } = useValuationStream()
  const metrics = usePolling(getBookMetrics, BOOK_METRICS_POLL_MS)
  const books = usePolling(getBooks)
  const [tradeId, setTradeId] = useState('')
  const [results, setResults] = useState(null)
  const [searchError, setSearchError] = useState(null)
  const [searching, setSearching] = useState(false)
  const [now, setNow] = useState(Date.now)
  const [page, setPage] = useState(1)

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), NOW_REFRESH_MS)
    return () => clearInterval(id)
  }, [])

  // Uses only state setters, so it is stable and the stream columns can be memoized
  const search = useCallback(async (id) => {
    setTradeId(id)
    setResults(null)
    if (!UUID_RE.test(id.trim())) {
      setSearchError('Trade ID must be a full UUID, e.g. 3f2b9c1e-0a4d-4b7e-9c2f-1d5e8a7b6c40.')
      return
    }
    setSearchError(null)
    setSearching(true)
    try {
      setResults(await getTradeValuations(id.trim()))
    } catch (err) {
      setSearchError(err.kind === 'unavailable' ? 'Pricing Service is down or unreachable.' : `Backend error: ${err.message}`)
    } finally {
      setSearching(false)
    }
  }, [])

  const bookNames = Object.fromEntries((books.data ?? []).map((book) => [book.book_id, book.name]))

  const columns = useMemo(() => streamColumns(search), [search])
  const streamRows = toStreamRows(byTrade, bookNames, now)
  const layout = useColumnLayout(STREAM_STORAGE_KEY, columns, STREAM_DEFAULT_COLUMNS, STREAM_DEFAULT_PINNED)
  const view = useTableView(STREAM_STORAGE_KEY, layout.columns, streamRows)
  const currentPage = Math.min(page, pageCountOf(view.rows.length, PAGE_SIZE))
  const pageRows = view.rows.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)
  const hasFilters = Object.values(view.filters).some(Boolean)
  const setFilters = (next) => {
    view.setFilters(next)
    setPage(1)
  }

  const liveCount = streamRows.filter((row) => row.status !== 'SETTLED').length
  const staleCount = streamRows.filter((row) => row.status === 'STALE').length
  const mostActive = topBy(streamRows, 'changes_per_min')
  const topImpact = topBy(streamRows, 'pnl_impact')

  const bookMetrics = (metrics.data?.book_metrics ?? [])
    .map((row) => ({ ...row, name: bookNames[row.book_id] }))
    .sort((a, b) => (a.name ?? a.book_id).localeCompare(b.name ?? b.book_id))

  return (
    <>
      <StreamNotice
        name="Live valuation stream"
        status={status}
        lastEventAt={lastEventAt}
        impact="Valuations below may be outdated (or there are no active trades to value)"
      />

      <section className="section">
        <h2>
          Valuation stream
          <StreamStatusBadge status={status} />
        </h2>
        <div className="kpis">
          <KpiCard label="Valued trades" value={liveCount} />
          <KpiCard label="Stale valuations" value={staleCount} tone={staleCount ? 'down' : undefined} />
          <KpiCard
            label="Most active"
            value={mostActive?.changes ? mostActive.symbol : null}
            hint={mostActive?.changes ? `${shortId(mostActive.trade_id)} · ${formatNumber(mostActive.changes_per_min, 1)}/min` : undefined}
          />
          <KpiCard
            label="Largest book PnL share"
            value={topImpact?.pnl_impact ? topImpact.symbol : null}
            hint={topImpact?.pnl_impact ? `${shortId(topImpact.trade_id)} · ${formatPercent(topImpact.pnl_impact)} of ${topImpact.book}` : undefined}
          />
        </div>
        <div className="pricing-toolbar">
          <TableFilters columns={layout.columns} filters={view.filters} onChange={setFilters} />
          <ColumnSettings layout={layout} />
        </div>
        <DataTable
          columns={layout.columns}
          rows={pageRows}
          rowKey="trade_id"
          sort={view.sort}
          onSort={view.toggleSort}
          onMoveColumn={layout.move}
          loading={status === 'CONNECTING'}
          footer={
            view.rows.length > 0 && (
              <Pagination page={currentPage} pageSize={PAGE_SIZE} total={view.rows.length} onChange={setPage} />
            )
          }
          emptyMessage={
            hasFilters && streamRows.length > 0 ? <NoMatches onClear={() => setFilters({})} />
              : status === 'RECONNECTING' ? 'Valuation stream unavailable – no valuations to show.'
                : 'No valuations yet – they appear once there are active trades (start the generator in Trade Generation).'
          }
        />
      </section>

      <section className="section">
        <h2>Book risk metrics</h2>
        <QueryNotice what="book risk metrics" service="Pricing Service" error={metrics.error} updatedAt={metrics.updatedAt} />
        <DataTable
          columns={BOOK_METRICS_COLUMNS}
          rows={bookMetrics}
          rowKey="book_id"
          loading={metrics.loading}
          emptyMessage={metrics.error ? 'Book risk metrics unavailable' : 'No book risk metrics yet – books need active trades'}
        />
      </section>

      <section className="section">
        <form
          className="card valuation-search"
          onSubmit={(e) => {
            e.preventDefault()
            search(tradeId)
          }}
        >
          <input
            className={`input valuation-search__input${searchError ? ' input--invalid' : ''}`}
            placeholder="Search Valuation by Trade ID"
            aria-invalid={Boolean(searchError)}
            value={tradeId}
            onChange={(e) => setTradeId(e.target.value)}
          />
          <button className="btn btn--primary" disabled={!tradeId.trim() || searching}>
            {searching ? 'Searching…' : 'Search'}
          </button>
        </form>
        {searchError && <p className="error">{searchError}</p>}
        {results && (
          <DataTable columns={SEARCH_COLUMNS} rows={results} rowKey="valuation_id" emptyMessage="No valuations found for this trade" />
        )}
      </section>
    </>
  )
}
