import { Link } from 'react-router-dom'

export function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <h1 className="text-4xl font-bold text-gray-900 mb-2">404</h1>
      <p className="text-gray-500 mb-6">Page not found.</p>
      <Link to="/incidents" className="text-blue-600 hover:underline">
        Back to Incidents
      </Link>
    </div>
  )
}
