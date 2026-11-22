import StatusBadge from './StatusBadge.jsx'
import './ServiceStatusCards.scss'

// UP: response time (sent as a string), DOWN: the health-check error
const hintOf = ({ status, response_time_ms, error }) =>
  status === 'UP' && response_time_ms !== undefined ? `${Math.round(Number(response_time_ms))} ms` : status === 'DOWN' ? error : null

// services: `services` from useServiceStatus()
export default function ServiceStatusCards({ services }) {
  return (
    <section className="service-cards">
      {services.map((service) => {
        const hint = hintOf(service)
        return (
          <div key={service.id} className={`card service-card service-card--${(service.status ?? 'unknown').toLowerCase()}`}>
            <span>{service.label}</span>
            <StatusBadge status={service.status} />
            {hint && <span className="service-card__hint" title={hint}>{hint}</span>}
          </div>
        )
      })}
    </section>
  )
}
