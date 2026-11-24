import React, { useState, useEffect } from 'react'
import {
  ShieldAlert,
  CheckCircle2,
  Copy,
  ExternalLink,
  X,
  Send,
  Check,
  Mail,
  Download,
  FileEdit,
  Search,
} from 'lucide-react'
import { EmailNotification, GrievanceDraft, GrievanceReceipt, SchemeSummary } from '../types'
import { apiFetch } from '../api'

interface Props {
  open: boolean
  sessionId: string
  defaultApplicantName?: string
  draft: GrievanceDraft | null
  receipt: GrievanceReceipt | null
  onClose: () => void
  onConfirmed: (receipt: GrievanceReceipt, emailNotif?: EmailNotification | null) => void
}

const CPGRAMS_LIMIT = 2000

export const GrievanceModal: React.FC<Props> = ({
  open,
  sessionId,
  defaultApplicantName,
  draft,
  receipt,
  onClose,
  onConfirmed,
}) => {
  // Step 1 (Direct Form) state when user clicks "Raise Grievance" button directly
  const [schemeSearch, setSchemeSearch] = useState('')
  const [schemeSuggestions, setSchemeSuggestions] = useState<SchemeSummary[]>([])
  const [selectedScheme, setSelectedScheme] = useState<SchemeSummary | null>(null)
  const [issueSummary, setIssueSummary] = useState('')
  const [stateName, setStateName] = useState('')
  const [districtName, setDistrictName] = useState('')
  const [refId, setRefId] = useState('')
  const [pendingSince, setPendingSince] = useState('')
  const [drafting, setDrafting] = useState(false)

  // Step 2 (HITL Review & Confirm) state
  const [workingDraft, setWorkingDraft] = useState<GrievanceDraft | null>(draft)
  const [applicantName, setApplicantName] = useState(defaultApplicantName || '')
  const [applicantEmail, setApplicantEmail] = useState('')
  const [subject, setSubject] = useState('')
  const [text, setText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Step 3 (Receipt + Confirmation Email Preview) state
  const [localReceipt, setLocalReceipt] = useState<GrievanceReceipt | null>(receipt)
  const [emailNotif, setEmailNotif] = useState<EmailNotification | null>(null)
  const [showEmailPreview, setShowEmailPreview] = useState(true)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    setWorkingDraft(draft)
    setLocalReceipt(receipt)
    setEmailNotif(null)
    setError(null)
    if (draft) {
      setSubject(draft.subject)
      setText(draft.grievance_text)
    }
    if (defaultApplicantName && !applicantName) {
      setApplicantName(defaultApplicantName)
    }
  }, [draft, receipt, open]) // eslint-disable-line react-hooks/exhaustive-deps

  // Live scheme autocomplete when filling form directly
  useEffect(() => {
    if (!open || workingDraft || localReceipt) return
    const q = schemeSearch.trim()
    const timer = setTimeout(() => {
      fetch(`/api/schemes?limit=6${q ? `&q=${encodeURIComponent(q)}` : ''}`)
        .then((r) => r.json())
        .then((d) => setSchemeSuggestions(d.items || []))
        .catch(() => {})
    }, 180)
    return () => clearTimeout(timer)
  }, [schemeSearch, open, workingDraft, localReceipt])

  if (!open) return null

  const charCount = text.length
  const overLimit = charCount > CPGRAMS_LIMIT

  const handleGenerateDraft = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!issueSummary.trim()) return
    setDrafting(true)
    setError(null)
    try {
      const resp = await apiFetch('/api/grievances/draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scheme_name: selectedScheme?.scheme_name || schemeSearch.trim() || 'Pradhan Mantri Kisan Samman Nidhi',
          scheme_slug: selectedScheme?.slug || undefined,
          ministry: selectedScheme?.ministry || '',
          issue_summary: issueSummary.trim(),
          beneficiary_reference_id: refId.trim() || null,
          state: stateName.trim() || null,
          district: districtName.trim() || null,
          pending_since: pendingSince.trim() || null,
          session_id: sessionId,
          applicant_name: applicantName.trim() || undefined,
          applicant_email: applicantEmail.trim() || undefined,
        }),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.detail || 'Could not create grievance draft')
      setWorkingDraft(data.draft)
      setSubject(data.draft.subject)
      setText(data.draft.grievance_text)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate formal grievance letter')
    } finally {
      setDrafting(false)
    }
  }

  const handleConfirmSubmit = async () => {
    if (!workingDraft || overLimit) return
    setSubmitting(true)
    setError(null)
    try {
      const resp = await apiFetch(`/api/grievances/${workingDraft.draft_id}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          confirmed: true,
          subject,
          grievance_text: text,
          applicant_name: applicantName.trim() || defaultApplicantName || 'Citizen Applicant',
          applicant_email: applicantEmail.trim() || undefined,
        }),
      })
      const data = await resp.json()
      if (!resp.ok) {
        throw new Error(data.detail || 'Submission failed')
      }
      setLocalReceipt(data.receipt)
      setEmailNotif(data.email_notification || null)
      onConfirmed(data.receipt, data.email_notification || null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit grievance')
    } finally {
      setSubmitting(false)
    }
  }

  const copyHandoff = () => {
    const packet = localReceipt?.assisted_handoff_packet
    if (!packet) return
    const fullText = `Ministry: ${packet.ministry} (${packet.ministry_code})\nSubject: ${packet.subject}\n\n${packet.body}`
    navigator.clipboard?.writeText(fullText)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const downloadHtmlReceipt = () => {
    if (!emailNotif) return
    const blob = new Blob([emailNotif.body_html], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `CPGRAMS_Receipt_${emailNotif.registration_number.replace(/\//g, '_')}.html`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1500)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 dark:bg-slate-950/60 backdrop-blur-sm">
      <div className="w-full max-w-2xl glass overflow-hidden max-h-[92vh] flex flex-col">
        {/* Header */}
        <div className="px-5 py-4 bg-white/40 dark:bg-white/5 border-b border-slate-900/10 dark:border-white/10 text-indiaNavy dark:text-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            {localReceipt ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            ) : workingDraft ? (
              <ShieldAlert className="w-5 h-5 text-indiaSaffron" />
            ) : (
              <FileEdit className="w-5 h-5 text-amber-500 dark:text-amber-300" />
            )}
            <div>
              <h3 className="font-semibold text-base text-indiaNavy dark:text-slate-100">
                {localReceipt
                  ? 'CPGRAMS Grievance Registered (Sandbox Gateway)'
                  : workingDraft
                    ? 'Review & Confirm CPGRAMS Grievance'
                    : 'Raise a Public Grievance (CPGRAMS Form)'}
              </h3>
              <p className="text-xs text-slate-600 dark:text-slate-400">
                {localReceipt
                  ? `Registration Number: ${localReceipt.registration_number}`
                  : workingDraft
                    ? 'Verify ministry routing, email address & formal complaint text before submitting.'
                    : 'Select the scheme and describe your issue — we route it to the exact Central Ministry.'}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-full text-slate-600 transition hover:bg-slate-900/5 dark:text-slate-300 dark:hover:bg-white/10" aria-label="Close modal">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 overflow-y-auto space-y-4 text-sm">
          {/* STEP 1: Direct Interactive CPGRAMS Form */}
          {!workingDraft && !localReceipt && (
            <form onSubmit={handleGenerateDraft} className="space-y-3.5">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">
                  1. Select Central Government Scheme *
                </label>
                <div className="relative">
                  <Search className="w-4 h-4 text-slate-400 dark:text-slate-500 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    value={selectedScheme ? selectedScheme.scheme_name : schemeSearch}
                    onChange={(e) => {
                      setSelectedScheme(null)
                      setSchemeSearch(e.target.value)
                    }}
                    placeholder="Type scheme name (e.g., PM-KISAN, Ayushman Bharat, PM-USP Scholarship)..."
                    className="field py-2 pl-9"
                    required
                  />
                </div>
                {!selectedScheme && schemeSuggestions.length > 0 && (
                  <div className="mt-1.5 glass-subtle shadow-lg divide-y divide-slate-900/10 dark:divide-white/10 max-h-36 overflow-y-auto">
                    {schemeSuggestions.map((s) => (
                      <button
                        key={s.slug}
                        type="button"
                        onClick={() => {
                          setSelectedScheme(s)
                          setSchemeSearch(s.scheme_name)
                        }}
                        className="w-full text-left px-3 py-2 hover:bg-white/80 dark:hover:bg-white/10 transition text-xs flex items-center justify-between gap-2"
                      >
                        <span className="font-medium text-slate-800 dark:text-slate-100 truncate">{s.scheme_name}</span>
                        <span className="text-[10px] font-mono text-indiaNavy dark:text-indiaSaffron shrink-0">{s.ministry_code}</span>
                      </button>
                    ))}
                  </div>
                )}
                {selectedScheme && (
                  <p className="text-[11px] text-emerald-700 dark:text-emerald-400 mt-1">
                    Auto-routed Ministry: <strong>{selectedScheme.ministry}</strong> ({selectedScheme.ministry_code})
                  </p>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">Applicant Full Name *</label>
                  <input
                    type="text"
                    value={applicantName}
                    onChange={(e) => setApplicantName(e.target.value)}
                    required
                    placeholder="e.g., Ramesh Kumar"
                                        className="field"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">
                    Email Address (For Confirmation Receipt) *
                  </label>
                  <input
                    type="email"
                    value={applicantEmail}
                    onChange={(e) => setApplicantEmail(e.target.value)}
                    required
                    placeholder="citizen@example.com"
                                        className="field"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">State / UT</label>
                  <input
                    type="text"
                    value={stateName}
                    onChange={(e) => setStateName(e.target.value)}
                    placeholder="e.g., Uttar Pradesh"
                                        className="field text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">District</label>
                  <input
                    type="text"
                    value={districtName}
                    onChange={(e) => setDistrictName(e.target.value)}
                    placeholder="e.g., Lucknow"
                                        className="field text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">Pending Since</label>
                  <input
                    type="text"
                    value={pendingSince}
                    onChange={(e) => setPendingSince(e.target.value)}
                    placeholder="e.g., June 2026"
                                        className="field text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">
                  Application / Beneficiary Reference ID (Optional — never enter full Aadhaar)
                </label>
                <input
                  type="text"
                  value={refId}
                  onChange={(e) => setRefId(e.target.value)}
                  placeholder="e.g., UP-PMKISAN-2026-4412"
                                    className="field text-xs"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">
                  Describe Your Grievance / Delay *
                </label>
                <textarea
                  rows={4}
                  required
                  value={issueSummary}
                  onChange={(e) => setIssueSummary(e.target.value)}
                  placeholder="Example: My last two PM-KISAN installments of ₹2,000 have not been credited despite completed e-KYC and Aadhaar bank seeding..."
                  className="field p-3"
                />
              </div>

              {error && (
                <div className="p-3 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 dark:bg-rose-500/15 dark:border-rose-400/30 dark:text-rose-300 text-xs">{error}</div>
              )}

                              <div className="flex justify-end gap-2 pt-2 border-t border-slate-900/10 dark:border-white/10">
                <button
                  type="button"
                  onClick={onClose}
                  className="btn-secondary text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={drafting}
                  className="btn-primary text-xs"
                >
                  <FileEdit className="w-4 h-4" />
                  {drafting ? 'Generating Formal CPGRAMS Letter...' : 'Generate Formal CPGRAMS Draft'}
                </button>
              </div>
            </form>
          )}

          {/* STEP 2: HITL Review & Confirm Modal */}
          {workingDraft && !localReceipt && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2 glass-subtle p-3 text-xs">
                <div>
                  <span className="text-slate-500 dark:text-slate-400">Target Central Ministry:</span>{' '}
                  <strong className="text-slate-900 dark:text-slate-100">{workingDraft.ministry_name}</strong>
                </div>
                <span className="px-2 py-0.5 rounded-full bg-indiaNavy dark:bg-indiaSaffron text-white dark:text-slate-950 font-mono font-semibold">
                  {workingDraft.ministry_code}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">Applicant Name</label>
                  <input
                    type="text"
                    value={applicantName}
                    onChange={(e) => setApplicantName(e.target.value)}
                    placeholder="Your full name"
                                      className="field text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">
                    Confirmation Email Address (Receives Official Receipt)
                  </label>
                  <input
                    type="email"
                    value={applicantEmail}
                    onChange={(e) => setApplicantEmail(e.target.value)}
                    placeholder="yourname@email.com"
                                      className="field text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">Grievance Subject</label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  maxLength={250}
                                  className="field"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-200">
                    Formal CPGRAMS Grievance Text (Editable)
                  </label>
                  <span
                    className={`text-xs font-mono font-semibold ${
                      overLimit ? 'text-rose-600 dark:text-rose-400' : charCount > 1800 ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-700 dark:text-emerald-400'
                    }`}
                  >
                    {charCount} / {CPGRAMS_LIMIT} chars
                  </span>
                </div>
                <textarea
                  rows={9}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  className={`field p-3 text-xs font-mono leading-relaxed ${
                    overLimit ? 'border-rose-400 bg-rose-50/40 focus:border-rose-400 focus:ring-rose-400/25 dark:border-rose-400/60 dark:bg-rose-500/10' : ''
                  }`}
                />
                {overLimit && (
                  <p className="text-xs text-rose-600 dark:text-rose-400 mt-1">
                    Exceeds official CPGRAMS 2,000-character limit. Please shorten by {charCount - CPGRAMS_LIMIT} characters.
                  </p>
                )}
              </div>

              {error && (
                <div className="p-3 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 dark:bg-rose-500/15 dark:border-rose-400/30 dark:text-rose-300 text-xs">{error}</div>
              )}

              <div className="flex flex-wrap items-center justify-end gap-3 pt-2 border-t border-slate-900/10 dark:border-white/10">
                <button
                  type="button"
                  onClick={onClose}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={submitting || overLimit}
                  onClick={handleConfirmSubmit}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-indiaGreen text-white font-semibold text-sm shadow-md shadow-indiaGreen/25 transition hover:bg-emerald-700 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Send className="w-4 h-4" />
                  {submitting ? 'Submitting & Sending Email Receipt...' : 'Confirm & Submit Grievance'}
                </button>
              </div>
            </>
          )}

          {/* STEP 3: Receipt + Live Confirmation Email Preview + Handoff Packet */}
          {localReceipt && (
            <div className="space-y-4">
              <div className="p-4 rounded-2xl bg-emerald-50/80 border border-emerald-200 shadow-sm dark:bg-emerald-500/15 dark:border-emerald-400/30 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-xs text-emerald-700 dark:text-emerald-400 font-medium">CPGRAMS Registration Number</p>
                                        <p className="text-lg font-mono font-bold text-emerald-950 dark:text-emerald-100">{localReceipt.registration_number}</p>
                  </div>
                  <span className="px-3 py-1 rounded-full bg-emerald-600 text-white text-xs font-semibold">
                    {localReceipt.status} ({localReceipt.mode.toUpperCase()})
                  </span>
                </div>
                <p className="text-xs text-emerald-800 dark:text-emerald-200">
                  <strong>Ministry:</strong> {localReceipt.ministry_name} ({localReceipt.ministry_code}) &bull;{' '}
                  <strong>Expected SLA:</strong> {localReceipt.expected_sla_days} days
                </p>
              </div>

              {/* Confirmation Email Dispatch Card */}
              {emailNotif && (
                <div className="rounded-2xl border border-sky-200 bg-sky-50/60 dark:border-sky-400/30 dark:bg-sky-500/10 p-4 space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Mail className="w-4 h-4 text-indiaNavy dark:text-sky-300" />
                      <div>
                        <p className="text-xs font-bold text-indiaNavy dark:text-slate-100">
                          Confirmation Email {emailNotif.delivery_status === 'SENT_SMTP' ? 'Delivered' : 'Generated (Sandbox Outbox)'}
                        </p>
                        <p className="text-[11px] text-slate-600 dark:text-slate-300">
                          To: <span className="font-mono">{emailNotif.recipient_email}</span> &bull; {emailNotif.delivery_detail}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => setShowEmailPreview((v) => !v)}
                        className="btn-secondary px-2.5 py-1 text-[11px]"
                      >
                        {showEmailPreview ? 'Hide Preview' : 'Preview Email'}
                      </button>
                      <button
                        type="button"
                        onClick={downloadHtmlReceipt}
                        className="btn-primary gap-1 px-2.5 py-1 text-[11px]"
                      >
                        <Download className="w-3 h-3" /> Receipt (.html)
                      </button>
                    </div>
                  </div>

                  {showEmailPreview && (
                    <iframe
                      title="CPGRAMS Email Receipt Preview"
                      srcDoc={emailNotif.body_html}
                      className="w-full h-64 rounded-2xl border border-slate-200 bg-white dark:border-white/10"
                      sandbox=""
                    />
                  )}
                </div>
              )}

              {/* Assisted Real-Portal Handoff Packet */}
              <div className="glass-subtle p-4 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h4 className="font-semibold text-slate-900 dark:text-slate-100 text-sm">
                    Official Portal Handoff Packet (pgportal.gov.in)
                  </h4>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={copyHandoff}
                      className="btn-secondary gap-1.5 px-3 py-1.5 text-xs"
                    >
                      {copied ? <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      {copied ? 'Copied!' : 'Copy Complaint Text'}
                    </button>
                    <a
                      href={localReceipt.assisted_handoff_packet.portal_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-primary gap-1.5 px-3 py-1.5 text-xs"
                    >
                      Open pgportal.gov.in <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>
                </div>

                <ol className="text-xs text-slate-600 dark:text-slate-300 space-y-1 pl-1">
                  {localReceipt.assisted_handoff_packet.next_steps.map((step, idx) => (
                    <li key={idx}>{step}</li>
                  ))}
                </ol>
              </div>

              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={onClose}
                  className="btn-primary"
                >
                  Done
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
