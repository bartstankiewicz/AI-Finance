import { useState } from 'react'
import DataTable from '../../components/DataTable.jsx'
import StreamStatusBadge from '../../components/StreamStatusBadge.jsx'
import { getTradeValuations } from '../../api/pricing.js'
import { formatDateTime, formatNumber, shortId } from '../../utils/format.js'
import useValuationStream from './useValuationStream.js'
import './PricingPage.scss'

// valuation_status is not returned by pricing-service yet; valuation_time only by GET /valuations
const valuationColumns = (renderTradeId) => [
  { key: 'asset_class', label: 'Asset Class' },
  { key: 'trade_id', label: 'Trade ID', render: renderTradeId },
  { key: 'book_id', label: 'Book ID', format: shortId },
  { key: 'fair_value', label: 'Fair Value', format: formatNumber },
  { key: 'realized_pnl', label: 'Realized PnL', format: formatNumber },
  { key: 'unrealized_pnl', label: 'Unrealized PnL', format: formatNumber },
  { key: 'valuation_status', label: 'Valuation Status' },
  { key: 'valuation_time', label: 'Created At', format: formatDateTime },
]

const SEARCH_COLUMNS = valuationColumns((row) => shortId(row.trade_id))

export default function PricingPage() {
  const { latestBySymbol, status } = useValuationStream()
  const [tradeId, setTradeId] = useState('')
  const [results, setResults] = useState(null)
  const [searchError, setSearchError] = useState(null)

  const search = async (id) => {
    setTradeId(id)
    setSearchError(null)
    try {
      setResults(await getTradeValuations(id.trim()))
    } catch (err) {
      setResults(null)
      setSearchError(err.message)
    }
  }

  const lastColumns = [
    { key: 'symbol', label: 'Symbol' },
    ...valuationColumns((row) => (
      <button className="btn btn--link" title="Search this trade" onClick={() => search(row.trade_id)}>
        {shortId(row.trade_id)}
      </button>
    )),
  ]
  const lastValuations = Object.values(latestBySymbol).sort((a, b) => a.symbol.localeCompare(b.symbol))

  return (
    <>
      <section className="section">
        <h2>
          Last valuations
          <StreamStatusBadge status={status} />
        </h2>
        <DataTable columns={lastColumns} rows={lastValuations} rowKey="symbol" />
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
            className="input valuation-search__input"
            placeholder="Search Valuation by Trade ID"
            value={tradeId}
            onChange={(e) => setTradeId(e.target.value)}
          />
          <button className="btn btn--primary" disabled={!tradeId.trim()}>Search</button>
        </form>
        {searchError && <p className="error">{searchError}</p>}
        {results && <DataTable columns={SEARCH_COLUMNS} rows={results} rowKey="valuation_id" />}
      </section>
    </>
  )
}
