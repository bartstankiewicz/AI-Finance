import './KpiCard.scss'

// tone: 'down' renders the value in the error color (e.g. negative PnL, stale data), 'up' in the gain color
export default function KpiCard({ label, value, tone, hint }) {
  return (
    <div className="card kpi">
      <span className="kpi__label">{label}</span>
      <span className={tone ? `kpi__value kpi__value--${tone}` : 'kpi__value'}>{value ?? '—'}</span>
      {hint && <span className="kpi__hint">{hint}</span>}
    </div>
  )
}
