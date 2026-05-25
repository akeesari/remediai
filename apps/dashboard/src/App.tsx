import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Layout } from './components/Layout'
import { IncidentList } from './pages/IncidentList'
import { IncidentDetail } from './pages/IncidentDetail'
import { LocalLogsPage } from './pages/LocalLogsPage'
import { MetricsPage } from './pages/MetricsPage'
import { TargetsPage } from './pages/TargetsPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
})

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/incidents" replace />} />
            <Route path="/incidents" element={<IncidentList />} />
            <Route path="/incidents/:id" element={<IncidentDetail />} />
            <Route path="/metrics" element={<MetricsPage />} />
            <Route path="/logs" element={<LocalLogsPage />} />
            <Route path="/targets" element={<TargetsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
