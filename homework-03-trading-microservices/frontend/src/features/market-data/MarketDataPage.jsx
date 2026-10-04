import { useState } from 'react'
import DataTable from '../../components/DataTable.jsx'
import StreamStatusBadge from '../../components/StreamStatusBadge.jsx'
import { useMarketData } from '../../context/MarketDataContext.jsx'
import PriceChart from './PriceChart.jsx'
import './MarketDataPage.scss'

const TICK_COLUMNS = [
  { key: 'symbol', label: 'Symbol' },
  { key: 'asset_class', label: 'Asset Class' },
  { key: 'timestamp', label: 'Timestamp', format: (v) => v.slice(11, 23) },
  { key: 'bid', label: 'Bid' },
  { key: 'ask', label: 'Ask' },
  { key: 'mid', label: 'Mid' },
  { key: 'spot', label: 'Spot' },
]

export default function MarketDataPage() {
  const { latest, history, status } = useMarketData()
  const [selected, setSelected] = useState('ACME')
  const symbols = Object.keys(history).sort()
  const ticks = Object.values(latest).sort((a, b) => a.symbol.localeCompare(b.symbol))

  return (
    <>
      <section className="card plot">
        <header className="plot__header">
          <h2>Plot</h2>
          <div className="plot__symbols">
            {symbols.map((symbol) => (
              <button
                key={symbol}
                className={symbol === selected ? 'btn btn--primary plot__symbol' : 'btn plot__symbol'}
                onClick={() => setSelected(symbol)}
              >
                {symbol}
              </button>
            ))}
          </div>
        </header>
        <PriceChart points={history[selected] ?? []} />
      </section>

      <section className="section">
        <h2>
          Last Generated Ticks
          <StreamStatusBadge status={status} />
        </h2>
        <DataTable columns={TICK_COLUMNS} rows={ticks} rowKey="symbol" />
      </section>
    </>
  )
}
