import { useState } from 'react'
import DataTable from '../../components/DataTable.jsx'
import Panel from '../../components/Panel.jsx'
import StatusBadge from '../../components/StatusBadge.jsx'
import usePolling from '../../hooks/usePolling.js'
import { generateOnce, getGeneratorStatus, startGenerator, stopGenerator } from '../../api/tradeGeneration.js'
import { getTrades } from '../../api/blotter.js'
import { shortId } from '../../utils/format.js'
import './TradeGenerationPage.scss'

const POLL_INTERVAL_MS = 2000
const fetchLatestTrades = () => getTrades({ limit: 10 })

// is_settled is not returned by blotter-service /trades yet
const TRADE_COLUMNS = [
  { key: 'trade_id', label: 'Trade Id', format: shortId },
  { key: 'book_id', label: 'Book Id', format: shortId },
  { key: 'asset_class', label: 'Asset Class' },
  { key: 'side', label: 'Side' },
  { key: 'status', label: 'Status' },
  { key: 'is_settled', label: 'Settled', format: (v) => (v ? 'Yes' : 'No') },
]

export default function TradeGenerationPage() {
  const { data: status, error: statusError, reload: reloadStatus } = usePolling(getGeneratorStatus, POLL_INTERVAL_MS)
  const { data: trades, error: tradesError } = usePolling(fetchLatestTrades, POLL_INTERVAL_MS)
  const [actionError, setActionError] = useState(null)

  const running = status?.status === 'running'

  const run = async (action) => {
    setActionError(null)
    try {
      await action()
      reloadStatus()
    } catch (err) {
      setActionError(err.message)
    }
  }

  return (
    <>
      <div className="panels">
        <Panel title="Trade Generator Action">
          <p className="muted">
            Status:{' '}
            {statusError
              ? <StatusBadge status="DOWN">UNREACHABLE</StatusBadge>
              : <StatusBadge status={status && (running ? 'UP' : 'DOWN')}>{status?.status.toUpperCase()}</StatusBadge>}
          </p>
          <div className="generator-actions">
            <button className="btn generator-actions__btn" disabled={!status || running} onClick={() => run(startGenerator)}>
              Start
            </button>
            <button className="btn generator-actions__btn" disabled={!status || !running} onClick={() => run(stopGenerator)}>
              Stop
            </button>
            <button className="btn generator-actions__btn" disabled={!status} onClick={() => run(generateOnce)}>
              Generate Once
            </button>
          </div>
          {actionError && <p className="error">{actionError}</p>}
        </Panel>

        <Panel title="Trade Generator Config">
          <div className="form">
            <label>Frequency [s]<input className="input" type="number" disabled placeholder="—" /></label>
            <label>Trade Out Probability [%]<input className="input" type="number" disabled placeholder="—" /></label>
            <label>Max Active Trades<input className="input" type="number" disabled placeholder="—" /></label>
          </div>
          <p className="muted">Read-only: trade-generation-service has no config endpoint yet.</p>
        </Panel>
      </div>

      <section className="section">
        <h2>Last Generated Trades</h2>
        {tradesError && <p className="error">Cannot load trades: {tradesError.message}</p>}
        <DataTable columns={TRADE_COLUMNS} rows={trades ?? []} rowKey="trade_id" />
      </section>
    </>
  )
}
