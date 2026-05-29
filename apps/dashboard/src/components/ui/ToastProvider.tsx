import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { Toast } from './Toast'

interface ToastMessage {
  id: number
  kind: 'success' | 'warning' | 'error'
  text: string
}

interface ToastContextValue {
  success: (text: string) => void
  warning: (text: string) => void
  error: (text: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [messages, setMessages] = useState<ToastMessage[]>([])

  const push = useCallback((kind: ToastMessage['kind'], text: string) => {
    const id = Date.now() + Math.floor(Math.random() * 1000)
    setMessages((current) => [...current, { id, kind, text }])
    window.setTimeout(() => {
      setMessages((current) => current.filter((message) => message.id !== id))
    }, 4000)
  }, [])

  const value = useMemo<ToastContextValue>(
    () => ({
      success: (text: string) => push('success', text),
      warning: (text: string) => push('warning', text),
      error: (text: string) => push('error', text),
    }),
    [push],
  )

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed inset-x-3 bottom-20 z-50 space-y-2 sm:inset-x-auto sm:bottom-6 sm:right-6 sm:w-96">
        {messages.map((message) => (
          <Toast
            key={message.id}
            kind={message.kind}
            text={message.text}
            onClose={() => setMessages((current) => current.filter((item) => item.id !== message.id))}
          />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return context
}
