import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ErrorBoundary } from 'react-error-boundary'
import { Layout } from './components/Layout'
import { AppErrorFallback } from './components/AppErrorFallback'
import { ThemeProvider } from './components/shell/ThemeContext'
import { ToastProvider } from './components/ui/ToastProvider'
import { IncidentList } from './pages/IncidentList'
import { IncidentDetail } from './pages/IncidentDetail'
import { LocalLogsPage } from './pages/LocalLogsPage'
import { MetricsPage } from './pages/MetricsPage'
import { NotFound } from './pages/NotFound'
import { TargetsPage } from './pages/TargetsPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
})

export function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <ErrorBoundary FallbackComponent={AppErrorFallback}>
              <Routes>
                <Route element={<Layout />}>
                  <Route index element={<Navigate to="/metrics" replace />} />
                  <Route path="/incidents" element={<IncidentList />} />
                  <Route path="/incidents/:id" element={<IncidentDetail />} />
                  <Route path="/metrics" element={<MetricsPage />} />
                  <Route path="/logs" element={<LocalLogsPage />} />
                  <Route path="/targets" element={<TargetsPage />} />
                  <Route path="*" element={<NotFound />} />
                </Route>
              </Routes>
            </ErrorBoundary>
          </BrowserRouter>
        </QueryClientProvider>
      </ToastProvider>
    </ThemeProvider>
  )
}
