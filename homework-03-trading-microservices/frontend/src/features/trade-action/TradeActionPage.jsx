import DataTable from '../../components/DataTable.jsx'
import KpiCard from '../../components/KpiCard.jsx'
import Panel from '../../components/Panel.jsx'
import usePolling from '../../hooks/usePolling.js'
import { getQueueStatus } from '../../api/tradeAction.js'
import { getBooksSummary, getTrades } from '../../api/blotter.js'
import { formatDateTime, shortId } from '../../utils/format.js'

const POLL_INTERVAL_MS = 2000
const fetchLatestTrades = () => getTrades({ limit: 10 })

// opened_at / closed_at are not returned by blotter-service /trades yet
const TRADE_COLUMNS = [
  { key: 'trade_id', label: 'Trade Id', format: shortId },
  { key: 'symbol', label: 'Symbol' },
  { key: 'asset_class', label: 'Asset Class' },
  { key: 'side', label: 'Side' },
  { key: 'opened_at', label: 'Opened At', format: formatDateTime },
  { key: 'closed_at', label: 'Closed At', format: formatDateTime },
]

// No backend endpoint for rejected trades yet
const REJECTED_COLUMNS = [
  { key: 'created_at', label: 'Datetime', format: formatDateTime },
  { key: 'trade_id', label: 'Trade Id', format: shortId },
  { key: 'message', label: 'Message' },
]

export default function TradeActionPage() {
  const { data: queue } = usePolling(getQueueStatus, POLL_INTERVAL_MS)
  const { data: books } = usePolling(getBooksSummary, POLL_INTERVAL_MS)
  const { data: trades, error: tradesError } = usePolling(fetchLatestTrades, POLL_INTERVAL_MS)

  const totalOpenTrades = books?.reduce((sum, book) => sum + book.active_trades, 0)

  return (
    <>
      <section className="kpis">
        <KpiCard label="Total Trades" />
        <KpiCard label="Total Errors" />
        <KpiCard label="Queue Status" value={queue?.queue_size} />
        <KpiCard label="Total Open Trades" value={totalOpenTrades} />
        <KpiCard label="Total Closed Trades" />
      </section>

      <section className="section">
        <h2>Last Generated Trades</h2>
        {tradesError && <p className="error">Cannot load trades: {tradesError.message}</p>}
        <DataTable columns={TRADE_COLUMNS} rows={trades ?? []} rowKey="trade_id" />
      </section>

      <div className="panels">
        <Panel title="Rejected Trades">
          <p className="muted">Counter: —</p>
          <DataTable columns={REJECTED_COLUMNS} rows={[]} rowKey="trade_id" />
        </Panel>
        <Panel title="Performance View">
          <p className="muted">Not implemented yet.</p>
        </Panel>
      </div>
    </>
  )
}
