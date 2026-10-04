import './DataTable.scss'

// column: { key, label, format?(value), render?(row) } - render wins, used for buttons/links
export const renderCell = (col, row) => {
  if (col.render) return col.render(row)
  const value = row[col.key]
  if (value === undefined || value === null) return '—'
  return col.format ? col.format(value) : value
}

export default function DataTable({ columns, rows, rowKey }) {
  return (
    <div className="data-table">
      <table>
        <thead>
          <tr>
            {columns.map((col) => <th key={col.key}>{col.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td className="data-table__empty" colSpan={columns.length}>No data</td>
            </tr>
          )}
          {rows.map((row) => (
            <tr key={row[rowKey]}>
              {columns.map((col) => <td key={col.key}>{renderCell(col, row)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
