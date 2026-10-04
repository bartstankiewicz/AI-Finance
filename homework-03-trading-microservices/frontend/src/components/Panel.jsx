import './Panel.scss'

export default function Panel({ title, children }) {
  return (
    <section className="card panel">
      <h2 className="panel__title">{title}</h2>
      {children}
    </section>
  )
}
