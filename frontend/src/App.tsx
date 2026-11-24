import React, { useState, useEffect } from 'react'
import {
  MessageSquareText,
  BookOpen,
  FileCheck,
  Activity,
  Search,
  ExternalLink,
  LogOut,
  Crown,
  User,
  PlusCircle,
  Mail,
  CheckCircle2,
  Clock,
  X,
} from 'lucide-react'
import { EmailNotification, StoredAuth } from './types'
import { apiFetch, clearStoredAuth, getStoredAuth, saveStoredAuth } from './api'
import { LoginScreen } from './components/LoginScreen'
import { AppBackground } from './components/AppBackground'
import { ThemeToggle } from './components/ThemeToggle'
import { ChatWorkspace } from './components/ChatWorkspace'
import { SchemeExplorer } from './components/SchemeExplorer'
import { TraceDashboard } from './components/TraceDashboard'
import { EvalDashboard } from './components/EvalDashboard'
import { GrievanceModal } from './components/GrievanceModal'

type Tab = 'copilot' | 'schemes' | 'grievances' | 'observability'

interface GrievanceListItem {
  draft_id: string
  registration_number: string | null
  scheme_name: string
  ministry_code: string
  ministry_name: string
  subject: string
  grievance_text: string
  applicant_name?: string | null
  applicant_email?: string | null
  status: string
  mode: string
  char_count: number
  status_history?: Array<{ status: string; timestamp: string; note: string }>
  updated_at: string
}

export default function App() {
  const [auth, setAuth] = useState<StoredAuth | null>(() => getStoredAuth())
  const [tab, setTab] = useState<Tab>('copilot')
  const [sessionId, setSessionId] = useState<string>(() => getStoredAuth()?.user.session_id || '')
  const [schemeCount, setSchemeCount] = useState<number>(649)

  const [trackInput, setTrackInput] = useState('')
  const [trackResult, setTrackResult] = useState<Record<string, unknown> | null>(null)
  const [grievanceList, setGrievanceList] = useState<GrievanceListItem[]>([])
  const [selectedGrievance, setSelectedGrievance] = useState<GrievanceListItem | null>(null)
  const [selectedEmails, setSelectedEmails] = useState<EmailNotification[]>([])
  const [directGrievanceOpen, setDirectGrievanceOpen] = useState(false)
  const [statusUpdating, setStatusUpdating] = useState(false)
  const [obsSubTab, setObsSubTab] = useState<'traces' | 'evals'>('traces')

  useEffect(() => {
    if (!auth) return
    apiFetch('/api/auth/me')
      .then((r) => {
        if (!r.ok) {
          clearStoredAuth()
          setAuth(null)
        }
      })
      .catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((d) => {
        if (d?.counts?.schemes) setSchemeCount(d.counts.schemes)
      })
      .catch(() => {})
  }, [])

  const loadGrievances = () => {
    apiFetch('/api/grievances?limit=30')
      .then((r) => r.json())
      .then((d) => setGrievanceList(d.items || []))
      .catch(() => {})
  }

  useEffect(() => {
    if (auth && tab === 'grievances') loadGrievances()
  }, [tab, auth])

  const openTicketInspector = async (g: GrievanceListItem) => {
    setSelectedGrievance(g)
    setSelectedEmails([])
    if (g.registration_number) {
      const r = await apiFetch(
        `/api/grievances/emails/outbox?registration_number=${encodeURIComponent(g.registration_number)}`,
      )
      if (r.ok) {
        const d = await r.json()
        setSelectedEmails(d.items || [])
      }
    }
  }

  const handleAdvanceStatus = async (regNo: string, nextStatus: 'UNDER_REVIEW' | 'ACTION_TAKEN' | 'DISPOSED') => {
    setStatusUpdating(true)
    try {
      const r = await apiFetch('/api/grievances/status', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          registration_number: regNo,
          status: nextStatus,
          note: `Sandbox Ministry Nodal Officer moved grievance to ${nextStatus}`,
        }),
      })
      if (r.ok) {
        const d = await r.json()
        setSelectedGrievance(d.grievance)
        loadGrievances()
      }
    } finally {
      setStatusUpdating(false)
    }
  }

  const handleLoginSuccess = (newAuth: StoredAuth) => {
    saveStoredAuth(newAuth)
    setAuth(newAuth)
    setSessionId(newAuth.user.session_id)
    setTab('copilot')
  }

  const handleLogout = () => {
    clearStoredAuth()
    setAuth(null)
    setTab('copilot')
  }

  const handleTrackTicket = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!trackInput.trim()) return
    const r = await apiFetch(`/api/grievances/track?registration_number=${encodeURIComponent(trackInput.trim())}`)
    setTrackResult(await r.json())
  }

  const resetSession = () => {
    if (!auth) return
    setSessionId(`${auth.user.username}-${Math.random().toString(36).slice(2, 8)}`)
  }

  if (!auth) {
    return (
      <>
        <AppBackground />
        <LoginScreen onLoginSuccess={handleLoginSuccess} />
      </>
    )
  }

  const isAdmin = auth.user.role === 'admin'

  return (
    <div className="min-h-screen flex flex-col">
          <AppBackground />
      <div className="h-1 tricolor-bar w-full" />

      {/* Clean Civic Portal Header */}
      <header className="bg-indiaNavy/90 text-white shadow-lg shadow-indiaNavy/20 backdrop-blur-xl sticky top-0 z-30 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-white/10 border border-white/20 flex items-center justify-center font-bold text-amber-300 text-sm">
              जन
            </div>
            <div>
              <h1 className="font-bold text-base leading-tight tracking-tight">JanSahayak</h1>
              <p className="text-[11px] text-slate-300">
                Citizen Welfare Schemes &amp; Public Grievance Portal
              </p>
            </div>
          </div>

          <nav className="flex items-center gap-1 bg-white/10 p-1 rounded-full border border-white/10 text-xs font-medium">
            <button
              type="button"
              onClick={() => setTab('copilot')}
              className={`inline-flex items-center gap-1.5               px-3 py-1.5 rounded-full transition ${
                tab === 'copilot' ? 'bg-white text-indiaNavy font-semibold shadow-2xs' : 'text-slate-200 hover:bg-white/10'
              }`}
            >
              <MessageSquareText className="w-3.5 h-3.5" /> Citizen Helpdesk
            </button>
            <button
              type="button"
              onClick={() => setTab('schemes')}
              className={`inline-flex items-center gap-1.5               px-3 py-1.5 rounded-full transition ${
                tab === 'schemes' ? 'bg-white text-indiaNavy font-semibold shadow-2xs' : 'text-slate-200 hover:bg-white/10'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5" /> Schemes ({schemeCount})
            </button>
            <button
              type="button"
              onClick={() => setTab('grievances')}
              className={`inline-flex items-center gap-1.5               px-3 py-1.5 rounded-full transition ${
                tab === 'grievances' ? 'bg-white text-indiaNavy font-semibold shadow-2xs' : 'text-slate-200 hover:bg-white/10'
              }`}
            >
              <FileCheck className="w-3.5 h-3.5" /> {isAdmin ? 'All Grievances' : 'My Grievances'}
            </button>
            {isAdmin && (
              <button
                type="button"
                onClick={() => setTab('observability')}
                className={`inline-flex items-center gap-1.5                 px-3 py-1.5 rounded-full transition ${
                  tab === 'observability' ? 'bg-white text-indiaNavy font-semibold shadow-2xs' : 'text-slate-200 hover:bg-white/10'
                }`}
              >
                <Activity className="w-3.5 h-3.5" /> Traces &amp; Evals
              </button>
            )}
          </nav>

          <div className="flex items-center gap-2 text-xs">
                      <ThemeToggle />
                      <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-white/10 border border-white/15">
              {isAdmin ? (
                <Crown className="w-3.5 h-3.5 text-amber-300" />
              ) : (
                <User className="w-3.5 h-3.5 text-emerald-300" />
              )}
              <span className="font-semibold text-white">{auth.user.display_name}</span>
              {isAdmin && (
                <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-amber-400 text-slate-900">
                  Admin
                </span>
              )}
            </div>

            <button
              type="button"
              onClick={handleLogout}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-full bg-white/10 hover:bg-rose-500/30 text-slate-200 hover:text-white transition"
              title="Sign out"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Sign Out</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-3 sm:px-5 py-4">
        {tab === 'copilot' && (
          <ChatWorkspace
            user={auth.user}
            sessionId={sessionId}
            onNewSession={resetSession}
            onSelectSession={setSessionId}
          />
        )}

        {tab === 'schemes' && <SchemeExplorer />}

        {tab === 'grievances' && (
          <div className="max-w-6xl mx-auto space-y-5">
            <div className="glass p-5 sm:p-6 space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-amber-900 text-[11px] font-semibold mb-1.5">
                    CPGRAMS Sandbox Gateway — Pending Production API Setu Onboarding
                  </div>
                  <h2 className="text-lg font-bold text-indiaNavy dark:text-slate-100">
                    {isAdmin ? 'Public Grievances — Live CPGRAMS Sandbox Ledger' : 'My Public Grievances (CPGRAMS Sandbox)'}
                  </h2>
                  <p className="text-xs text-slate-600 dark:text-slate-300 mt-0.5 max-w-2xl">
                    Raise a grievance using the structured form below or inside Citizen Helpdesk. Every confirmed submission generates an official-format ticket ID, sends/stores an acknowledgement email receipt, and includes a copy-paste packet for <code>pgportal.gov.in</code>.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setDirectGrievanceOpen(true)}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-indiaSaffron hover:bg-orange-600 text-white text-xs font-semibold shadow-md shadow-indiaSaffron/25 transition"
                  >
                    <PlusCircle className="w-4 h-4" /> Raise New Grievance
                  </button>
                  <a
                    href="https://pgportal.gov.in/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-secondary text-xs font-semibold text-indiaNavy dark:text-slate-100"
                  >
                    pgportal.gov.in <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>

              <form onSubmit={handleTrackTicket} className="flex gap-2">
                <div className="flex-1 relative">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    value={trackInput}
                    onChange={(e) => setTrackInput(e.target.value)}
                    placeholder="Track by Registration Number (e.g. MOAFW/E/2026/000001)"
                    className="field pl-9 pr-3 py-2 font-mono"
                  />
                </div>
                <button
                  type="submit"
                  className="btn-primary"
                >
                  Track Status
                </button>
              </form>

              {trackResult && (
                <div className="p-4 rounded-2xl bg-emerald-50/70 border border-emerald-200 text-xs space-y-1 dark:bg-emerald-400/10 dark:border-emerald-400/25">
                  <p className="font-bold text-slate-900 dark:text-slate-100">
                    {trackResult.found
                      ? `Ticket ${String(trackResult.registration_number)} — ${String(trackResult.status)}`
                      : `Not Found: ${String(trackResult.registration_number)}`}
                  </p>
                  {Boolean(trackResult.ministry_name) && (
                    <p className="text-slate-700 dark:text-slate-300">
                      Ministry: {String(trackResult.ministry_name)} ({String(trackResult.ministry_code)}) | SLA: {String(trackResult.expected_sla_days || 21)} days
                    </p>
                  )}
                  {Boolean(trackResult.message) && <p className="text-slate-600 dark:text-slate-300">{String(trackResult.message)}</p>}
                </div>
              )}
            </div>

            {/* Ticket Ledger Table (Clickable rows open Live Sandbox Portal Ticket View!) */}
            <div className="glass overflow-hidden">
              <div className="px-4 py-3 bg-slate-900/[0.03] dark:bg-white/5 border-b border-slate-200/70 dark:border-white/10 text-xs font-semibold text-slate-700 dark:text-slate-200 flex items-center justify-between">
                <span>
                  {isAdmin ? 'All Sandbox Drafts & Registered Grievances' : 'Your Drafts & Registered Grievances'} ({grievanceList.length})
                </span>
                <span className="text-[11px] font-normal text-slate-500 dark:text-slate-400">Click any row to inspect form, timeline &amp; confirmation email</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-slate-900/[0.03] dark:bg-white/5 text-slate-500 dark:text-slate-400 border-b border-slate-200/70 dark:border-white/10">
                    <tr>
                      <th className="p-3 text-left">Registration / Draft ID</th>
                      <th className="p-3 text-left">Scheme &amp; Ministry</th>
                      <th className="p-3 text-left">Applicant</th>
                      <th className="p-3 text-center">Status</th>
                      <th className="p-3 text-right">Updated</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200/70 dark:divide-white/10">
                    {grievanceList.length === 0 && (
                      <tr>
                        <td colSpan={5} className="p-6 text-center text-slate-500 dark:text-slate-400">
                          No grievances filed yet. Click <strong>Raise New Grievance</strong> above to submit one.
                        </td>
                      </tr>
                    )}
                    {grievanceList.map((g) => (
                      <tr
                        key={g.draft_id}
                        onClick={() => openTicketInspector(g)}
                        className="hover:bg-sky-50/60 dark:hover:bg-white/5 cursor-pointer transition"
                      >
                        <td className="p-3 font-mono font-semibold text-indiaNavy dark:text-amber-200">
                          {g.registration_number || g.draft_id}
                        </td>
                        <td className="p-3">
                          <div className="font-medium text-slate-900 dark:text-slate-100">{g.scheme_name}</div>
                                                    <div className="text-[11px] text-slate-500 dark:text-slate-400">
                            {g.ministry_name} ({g.ministry_code})
                          </div>
                        </td>
                        <td className="p-3 text-slate-600 dark:text-slate-300">
                          <div>{g.applicant_name || 'Citizen'}</div>
                                                  {g.applicant_email && <div className="text-[10px] font-mono text-slate-400 dark:text-slate-500">{g.applicant_email}</div>}
                        </td>
                        <td className="p-3 text-center">
                          <span
                            className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold ${
                              g.status === 'DISPOSED'
                                ? 'bg-emerald-600 text-white'
                                : g.status === 'SUBMITTED' || g.status === 'ACTION_TAKEN'
                                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-400/15 dark:text-emerald-300'
                                  : g.status === 'UNDER_REVIEW'
                                    ? 'bg-sky-100 text-sky-800 dark:bg-sky-400/15 dark:text-sky-300'
                                    : 'bg-amber-100 text-amber-800 dark:bg-amber-400/15 dark:text-amber-300'
                            }`}
                          >
                            {g.status}
                          </span>
                        </td>
                        <td className="p-3 text-right text-slate-500 dark:text-slate-400">{g.updated_at}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Live Sandbox Ticket Inspector Modal (Form + Timeline + Confirmation Email + Admin Status Advance) */}
            {selectedGrievance && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm">
                <div className="w-full max-w-3xl bg-white dark:bg-slate-900 dark:border dark:border-white/10 rounded-3xl shadow-2xl max-h-[90vh] flex flex-col overflow-hidden">
                  <div className="px-5 py-4 bg-indiaNavy text-white flex items-center justify-between">
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-amber-300 font-semibold">
                        CPGRAMS Sandbox Portal — Official Ticket Record
                      </p>
                      <h3 className="font-mono font-bold text-base">
                        {selectedGrievance.registration_number || selectedGrievance.draft_id}
                      </h3>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSelectedGrievance(null)}
                      className="p-1.5 rounded-lg hover:bg-white/10"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>

                  <div className="p-5 overflow-y-auto space-y-4 text-xs">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 bg-slate-50 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-2xl p-3.5">
                      <div>
                        <p className="text-slate-500 dark:text-slate-400">Scheme &amp; Ministry</p>
                        <p className="font-semibold text-slate-900 dark:text-slate-100">{selectedGrievance.scheme_name}</p>
                        <p className="text-slate-600 dark:text-slate-300">{selectedGrievance.ministry_name} ({selectedGrievance.ministry_code})</p>
                      </div>
                      <div>
                        <p className="text-slate-500 dark:text-slate-400">Status &amp; Applicant</p>
                        <p className="font-bold text-emerald-700 dark:text-emerald-300">{selectedGrievance.status}</p>
                        <p className="text-slate-600 dark:text-slate-300">
                          {selectedGrievance.applicant_name || 'Citizen'} {selectedGrievance.applicant_email ? `• ${selectedGrievance.applicant_email}` : ''}
                        </p>
                      </div>
                    </div>

                    {/* Admin Sandbox Status Progression Controls */}
                    {isAdmin && selectedGrievance.registration_number && (
                      <div className="p-3 rounded-2xl bg-amber-50 border border-amber-200 dark:bg-amber-400/10 dark:border-amber-400/30 flex flex-wrap items-center justify-between gap-2">
                        <span className="font-semibold text-amber-950 dark:text-amber-100">
                          Admin Sandbox Demo Control — Simulate Ministry Action:
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {(['UNDER_REVIEW', 'ACTION_TAKEN', 'DISPOSED'] as const).map((st) => (
                            <button
                              key={st}
                              type="button"
                              disabled={statusUpdating || selectedGrievance.status === st}
                              onClick={() => handleAdvanceStatus(selectedGrievance.registration_number!, st)}
                              className="px-2.5 py-1 rounded-lg bg-white border border-amber-300 hover:bg-amber-100 disabled:opacity-40 text-[11px] font-semibold text-amber-950 dark:bg-amber-300/10 dark:border-amber-400/40 dark:text-amber-100 dark:hover:bg-amber-300/20"
                            >
                              Mark {st}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Status Timeline */}
                    {selectedGrievance.status_history && selectedGrievance.status_history.length > 0 && (
                      <div>
                        <p className="font-bold text-slate-800 dark:text-slate-100 mb-2 flex items-center gap-1.5">
                          <Clock className="w-3.5 h-3.5 text-indiaNavy dark:text-sky-300" /> Live Status Timeline
                        </p>
                        <div className="space-y-2 border-l-2 border-indiaNavy/30 dark:border-sky-300/30 pl-3.5">
                          {selectedGrievance.status_history.map((h, i) => (
                            <div key={i} className="relative">
                              <span className="inline-flex items-center gap-1 font-semibold text-indiaNavy dark:text-sky-200">
                                <CheckCircle2 className="w-3 h-3 text-emerald-600 dark:text-emerald-400" /> {h.status}
                              </span>
                              <span className="text-slate-400 dark:text-slate-500 ml-2 font-mono text-[10px]">{h.timestamp}</span>
                              <p className="text-slate-600 dark:text-slate-300 mt-0.5">{h.note}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Submitted Grievance Text */}
                    <div>
                      <p className="font-bold text-slate-800 dark:text-slate-100 mb-1">Submitted Formal Complaint ({selectedGrievance.char_count} / 2000 chars)</p>
                      <pre className="p-3 rounded-2xl bg-slate-50 dark:bg-white/5 border border-slate-200 dark:border-white/10 font-mono text-[11px] whitespace-pre-wrap text-slate-800 dark:text-slate-200">
                        {selectedGrievance.grievance_text}
                      </pre>
                    </div>

                    {/* Confirmation Email Receipt Preview */}
                    {selectedEmails.length > 0 && (
                      <div className="space-y-2 pt-2 border-t border-slate-200 dark:border-white/10">
                        <p className="font-bold text-indiaNavy dark:text-sky-200 flex items-center gap-1.5">
                          <Mail className="w-4 h-4" /> Official Confirmation Email Receipt ({selectedEmails[0].delivery_status})
                        </p>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400">
                          To: <span className="font-mono">{selectedEmails[0].recipient_email}</span> &bull; {selectedEmails[0].delivery_detail}
                        </p>
                        <iframe
                          title="Ticket Confirmation Email"
                          srcDoc={selectedEmails[0].body_html}
                          className="w-full h-64 rounded-xl border border-slate-200 bg-white"
                          sandbox=""
                        />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Direct Raise Grievance Form Modal from Grievances Tab */}
            <GrievanceModal
              open={directGrievanceOpen}
              sessionId={sessionId}
              defaultApplicantName={auth.user.display_name}
              draft={null}
              receipt={null}
              onClose={() => {
                setDirectGrievanceOpen(false)
                loadGrievances()
              }}
              onConfirmed={() => loadGrievances()}
            />
          </div>
        )}

        {tab === 'observability' && isAdmin && (
          <div className="max-w-6xl mx-auto space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-200 dark:border-white/10 pb-2">
              <button
                type="button"
                onClick={() => setObsSubTab('traces')}
                className={`px-4 py-2 rounded-full text-xs font-semibold transition ${
                  obsSubTab === 'traces'
                    ? 'bg-indiaNavy text-white shadow-md dark:bg-indiaSaffron dark:text-slate-950'
                    : 'bg-white/70 border border-slate-200 text-slate-600 hover:bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-300 dark:hover:bg-white/10'
                }`}
              >
                Live Trace &amp; Span Debugger
              </button>
              <button
                type="button"
                onClick={() => setObsSubTab('evals')}
                className={`px-4 py-2 rounded-full text-xs font-semibold transition ${
                  obsSubTab === 'evals'
                    ? 'bg-indiaNavy text-white shadow-md dark:bg-indiaSaffron dark:text-slate-950'
                    : 'bg-white/70 border border-slate-200 text-slate-600 hover:bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-300 dark:hover:bg-white/10'
                }`}
              >
                Benchmark Evals &amp; Downloads
              </button>
            </div>
            {obsSubTab === 'traces' ? <TraceDashboard /> : <EvalDashboard />}
          </div>
        )}
      </main>
    </div>
  )
}
