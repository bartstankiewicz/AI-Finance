import { renderCell } from './DataTable.jsx'
import './DetailsList.scss'

// Label/value list; fields use the same shape as DataTable columns: { key, label, format?, render? }
export default function DetailsList({ fields, data }) {
  return (
    <dl className="details-list">
      {fields.map((field) => (
        <div key={field.key} className="details-list__row">
          <dt>{field.label}</dt>
          <dd>{renderCell(field, data)}</dd>
        </div>
      ))}
    </dl>
  )
}
