import DetailsList from '../../components/DetailsList.jsx'
import { formatDateTime } from '../../utils/format.js'

const FIELDS = [
  { key: 'name', label: 'Name' },
  { key: 'book_id', label: 'Book ID' },
  { key: 'description', label: 'Description' },
  { key: 'expected_asset_class', label: 'Asset Class' },
  { key: 'is_active', label: 'Active', format: (v) => (v ? 'Yes' : 'No') },
  { key: 'created_at', label: 'Created At', format: formatDateTime },
  { key: 'updated_at', label: 'Updated At', format: formatDateTime },
]

export default function BookDetails({ book }) {
  return <DetailsList fields={FIELDS} data={book} />
}
