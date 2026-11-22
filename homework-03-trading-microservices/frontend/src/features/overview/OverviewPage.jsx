import DataTable from '../../components/DataTable.jsx'
import KpiCard from '../../components/KpiCard.jsx'
import Panel from '../../components/Panel.jsx'
import QueryNotice from '../../components/QueryNotice.jsx'
import ServiceStatusCards from '../../components/ServiceStatusCards.jsx'
import StatusBadge from '../../components/StatusBadge.jsx'
import StreamStatusBadge from '../../components/StreamStatusBadge.jsx'
import useServiceStatus, { MONITORING_SERVICE_ID } from '../../hooks/useServiceStatus.js'
import usePolling from '../../hooks/usePolling.js'
import { useMarketData, useMarketStream } from '../../context/MarketDataContext.jsx'
import { getBooksSummary, getRecentErrors } from '../../api/blotter.js'
import { getLatestValuation, VALUATION_STALE_AFTER_MS } from '../../api/pricing.js'
import { formatAge, formatNumber, formatTime, secondsSince } from '../../utils/format.js'
import './OverviewPage.scss'

const POLL_INTERVAL_MS = 5000
const ERROR_WINDOW_MINUTES = 5
const MARKET_STALE_AFTER_SECONDS = 30 // ~3x TICK_INTERVAL of market-data-service
const VALUATION_STALE_AFTER_SECONDS = VALUATION_STALE_AFTER_MS / 1000

const fetchRecentErrors = () => getRecentErrors(ERROR_WINDOW_MINUTES, 10)

const sum = (rows, key) => rows?.reduce((total, row) => total + row[key], 0)
const pnlTone = (value) => (value > 0 ? 'up' : value < 0 ? 'down' : undefined)
const pnlClass = (key) => (row) => (row[key] > 0 ? 'is-up' : row[key] < 0 ? 'is-down' : undefined)
const formatPnl = (value) => (value === undefined ? null : formatNumber(value))

const BOOK_COLUMNS = [
  { key: 'name', label: 'Book' },
  { key: 'active_trades', label: 'Active', numeric: true },
  { key: 'unrealized_pnl', label: 'Unrealized', format: formatNumber, numeric: true, className: pnlClass('unrealized_pnl') },
  { key: 'realized_pnl', label: 'Realized', format: formatNumber, numeric: true, className: pnlClass('realized_pnl') },
  { key: 'total_pnl', label: 'Total', format: formatNumber, numeric: true, className: pnlClass('total_pnl') },
]

const ERROR_COLUMNS = [
  { key: 'created_at', label: 'Time', format: formatTime },
  { key: 'service_name', label: 'Service' },
  { key: 'event_type', label: 'Event' },
  { key: 'message', label: 'Message' },
]

function TimestampCard({ label, timestamp, stale, emptyHint }) {
  if (!timestamp) return <KpiCard label={label} hint={emptyHint} tone={stale ? 'down' : undefined} />
  return (
    <KpiCard label={label} value={formatTime(timestamp)} hint={formatAge(secondsSince(timestamp))} tone={stale ? 'down' : undefined} />
  )
}

// Only this card reads tick data, so ticks don't re-render the rest of the page
function LastTickCard() {
  const { latest } = useMarketData()
  const { status } = useMarketStream()
  const lastTick = Object.values(latest)
    .map((tick) => tick.timestamp)
    .sort()
    .at(-1)
  const stale = status !== 'CONNECTED' || (lastTick && secondsSince(lastTick) > MARKET_STALE_AFTER_SECONDS)
  return <TimestampCard label="Last market tick" timestamp={lastTick} stale={stale} emptyHint="no ticks yet" />
}

// One verdict for "is the system OK?" - DOWN beats WARN beats UP
function assessHealth({ monitored, monitoringStatus, marketStatus, errorCount, valuationStale }) {
  if (monitoringStatus === 'CONNECTING') return { status: undefined, title: 'Checking system status…', issues: [] }

  const down = monitored.filter((service) => service.status === 'DOWN')
  const issues = []
  if (monitoringStatus !== 'CONNECTED') issues.push('Monitoring feed is unavailable – service status unknown')
  if (down.length > 0) issues.push(`Down: ${down.map((service) => service.label).join(', ')}`)
  if (marketStatus === 'STALE' || marketStatus === 'RECONNECTING') issues.push('No market data ticks – stream is stale')
  if (valuationStale) issues.push('Valuations are stale while trades are active')
  if (errorCount > 0) issues.push(`${errorCount} error(s) in the last ${ERROR_WINDOW_MINUTES} min`)

  if (down.length > 0) return { status: 'DOWN', title: `${down.length} of ${monitored.length} services down`, issues }
  if (monitoringStatus !== 'CONNECTED') return { status: 'WARN', title: 'System status unknown', issues }
  if (issues.length > 0) return { status: 'WARN', title: 'Running with warnings', issues }
  return { status: 'UP', title: `All ${monitored.length} services operational`, issues }
}

export default function OverviewPage() {
  const { services, streamStatus } = useServiceStatus()
  const { status: marketStatus } = useMarketStream()
  const books = usePolling(getBooksSummary, POLL_INTERVAL_MS)
  const errors = usePolling(fetchRecentErrors, POLL_INTERVAL_MS)
  const valuation = usePolling(getLatestValuation, POLL_INTERVAL_MS)

  const activeTrades = sum(books.data, 'active_trades')
  const unrealized = sum(books.data, 'unrealized_pnl')
  const realized = sum(books.data, 'realized_pnl')
  const total = sum(books.data, 'total_pnl')
  const valuationTime = valuation.data?.valuation_time
  // Pricing only revalues active trades, so an old valuation is fine when there are none
  const valuationStale =
    activeTrades > 0 && (!valuationTime || secondsSince(valuationTime) > VALUATION_STALE_AFTER_SECONDS)
  const sortedBooks = books.data ? [...books.data].sort((a, b) => b.total_pnl - a.total_pnl) : []

  const health = assessHealth({
    monitored: services.filter((service) => service.id !== MONITORING_SERVICE_ID),
    monitoringStatus: streamStatus,
    marketStatus,
    errorCount: errors.data?.count,
    valuationStale,
  })

  return (
    <>
      <section className={`card system-health system-health--${(health.status ?? 'unknown').toLowerCase()}`}>
        <StatusBadge status={health.status} />
        <div>
          <h1 className="system-health__title">{health.title}</h1>
          {health.issues.length > 0 && (
            <ul className="system-health__issues">
              {health.issues.map((issue) => <li key={issue}>{issue}</li>)}
            </ul>
          )}
        </div>
      </section>

      <section className="section">
        <h2>
          Services
          <StreamStatusBadge status={streamStatus} />
        </h2>
        <ServiceStatusCards services={services} />
      </section>

      <QueryNotice what="book summary" service="Blotter Service" error={books.error} updatedAt={books.updatedAt} />
      <QueryNotice what="errors" service="Blotter Service" error={errors.error} updatedAt={errors.updatedAt} />
      <QueryNotice what="last valuation" service="Pricing Service" error={valuation.error} updatedAt={valuation.updatedAt} />

      <div className="panels">
        <Panel title="Trading (USD)">
          <div className="kpis">
            <KpiCard label="Total P&L" value={formatPnl(total)} tone={pnlTone(total)} />
            <KpiCard label="Unrealized P&L" value={formatPnl(unrealized)} tone={pnlTone(unrealized)} />
            <KpiCard label="Realized P&L" value={formatPnl(realized)} tone={pnlTone(realized)} />
            <KpiCard label="Active trades" value={activeTrades} />
            <KpiCard label="Books" value={books.data?.length} />
          </div>
        </Panel>

        <Panel title="Pipeline health">
          <div className="kpis">
            <KpiCard
              label={`Errors (last ${ERROR_WINDOW_MINUTES} min)`}
              value={errors.data?.count}
              tone={errors.data?.count > 0 ? 'down' : undefined}
            />
            <LastTickCard />
            <TimestampCard
              label="Last valuation"
              timestamp={valuationTime}
              stale={valuationStale}
              emptyHint={activeTrades > 0 ? 'no valuations' : 'no active trades'}
            />
          </div>
        </Panel>
      </div>

      <div className="panels">
        <Panel title="P&L by book (USD)">
          <DataTable
            columns={BOOK_COLUMNS}
            rows={sortedBooks}
            rowKey="book_id"
            loading={books.loading}
            emptyMessage={books.error ? 'Book summary unavailable' : 'No books yet. Create one in the Books view.'}
          />
        </Panel>

        <Panel title={`Recent errors (last ${ERROR_WINDOW_MINUTES} min)`}>
          <DataTable
            columns={ERROR_COLUMNS}
            rows={errors.data?.errors ?? []}
            rowKey="audit_id"
            loading={errors.loading}
            emptyMessage={errors.error ? 'Error log unavailable' : 'No errors – all quiet'}
          />
        </Panel>
      </div>
    </>
  )
}
