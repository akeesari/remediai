import { Link } from 'react-router-dom'
import { Button } from '../components/ui/Button'

export function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-surface px-6 py-24 text-center">
      <h1 className="text-5xl font-semibold text-text-1">404</h1>
      <p className="mt-2 text-sm text-text-2">Page not found.</p>
      <Link to="/incidents" className="mt-6">
        <Button type="button" variant="primary">
          Back to Incidents
        </Button>
      </Link>
    </div>
  )
}
