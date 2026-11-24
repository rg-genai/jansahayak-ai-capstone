import React, { useEffect, useState } from 'react'
import { History, Loader2, MessageSquare, X } from 'lucide-react'
import { apiFetch } from '../api'
import { SessionSummary } from '../types'

interface Props {
  open: boolean
  onClose: () => void
  activeSessionId: string
  busy: boolean
  onSelectSession: (sessionId: string) => void
}

const formatWhen = (iso: string | null): string => {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export const SessionsSidebar: React.FC<Props> = ({
  open,
  onClose,
  activeSessionId,
  busy,
  onSelectSession,
}) => {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [listLoading, setListLoading] = useState(false)
  const [listError, setListError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setListLoading(true)
    setListError(null)
    apiFetch('/api/sessions')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data) => {
        if (!cancelled) setSessions(Array.isArray(data?.sessions) ? data.sessions : [])
      })
      .catch(() => {
        if (!cancelled) setListError('Could not load your session history. Please try again.')
      })
      .finally(() => {
        if (!cancelled) setListLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const handlePick = (id: string) => {
    if (id !== activeSessionId) onSelectSession(id)
    onClose()
  }

  return (
    // mousedown, not click, so a text selection dragged out of the panel does not close it
    <div
      className="fixed inset-0 z-50 flex justify-start bg-slate-900/40 backdrop-blur-xs"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="w-full max-w-xs bg-white h-full shadow-2xl flex flex-col overflow-hidden">
        <div className="px-5 py-4 bg-indiaNavy text-white flex items-center justify-between">
          <div className="flex items-center gap-2">
            <History className="w-5 h-5 text-indiaSaffron" />
            <h3 className="font-semibold text-base">Session History</h3>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-white/10" aria-label="Close session history">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
          {busy && (
            <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-2.5">
              Wait for the current answer to finish before switching sessions.
            </p>
          )}

          {listLoading && (
            <div className="flex items-center justify-center gap-2 py-6 text-xs text-slate-500">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading sessions...
            </div>
          )}

          {listError && <p className="text-xs text-rose-700">{listError}</p>}

          {!listLoading && !listError && sessions.length === 0 && (
            <p className="py-6 text-center text-xs text-slate-500">
              No past conversations yet. Your chats will appear here after you send a message.
            </p>
          )}

          {sessions.map((s) => {
            const isActive = s.session_id === activeSessionId
            return (
              <button
                key={s.session_id}
                type="button"
                disabled={busy}
                onClick={() => handlePick(s.session_id)}
                className={`w-full text-left rounded-lg border px-3 py-2.5 transition disabled:cursor-not-allowed disabled:opacity-50 ${
                  isActive ? 'border-indiaNavy bg-slate-50 ring-1 ring-indiaNavy' : 'border-slate-200 hover:bg-slate-50'
                }`}
              >
                <div className="flex items-start gap-2">
                  <MessageSquare className="w-4 h-4 mt-0.5 shrink-0 text-indiaNavy" />
                  <p className="text-sm font-medium text-slate-800 line-clamp-2">
                    {s.first_question || 'Untitled conversation'}
                  </p>
                </div>
                <div className="mt-1.5 pl-6 flex items-center justify-between text-[11px] text-slate-500">
                  <span>{s.message_count} messages</span>
                  <span>{formatWhen(s.last_message_at)}</span>
                </div>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
