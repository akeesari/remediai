import { BarChart3, Bug, FileText, Server, type LucideIcon } from 'lucide-react'

export interface NavRoute {
  to: string
  label: string
  icon: LucideIcon
}

export const NAV_ROUTES: NavRoute[] = [
  { to: '/metrics', label: 'Metrics', icon: BarChart3 },
  { to: '/incidents', label: 'Incidents', icon: Bug },
  { to: '/targets', label: 'Targets', icon: Server },
  { to: '/logs', label: 'Logs', icon: FileText },
]
