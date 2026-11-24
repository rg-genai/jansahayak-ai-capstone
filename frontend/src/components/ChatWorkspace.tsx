import React, { useState, useRef, useEffect } from 'react'
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Send,
  UserCheck,
  ExternalLink,
  FileWarning,
  Loader2,
  Globe,
  BookOpen,
  Sprout,
  GraduationCap,
  Hammer,
  FileText,
  MessageSquarePlus,
  RotateCcw,
  FilePlus2,
  History,
} from 'lucide-react'
import {
  AuthUser,
  ChatMessage,
  CitationItem,
  CitizenProfile,
  GrievanceDraft,
  GrievanceReceipt,
  LANGUAGE_OPTIONS,
} from '../types'
import { apiFetch } from '../api'
import { useVoiceIO } from '../hooks/useVoiceIO'
import { EligibilityCard } from './EligibilityCard'
import { GrievanceModal } from './GrievanceModal'
import { ProfileDrawer } from './ProfileDrawer'
import { SessionsSidebar } from './SessionsSidebar'

interface Props {
  user: AuthUser
  sessionId: string
  initialPrompt?: string | null
  onClearInitialPrompt?: () => void
  onNewSession: () => void
  onSelectSession: (sessionId: string) => void
  onTraceCreated?: () => void
}

const QUICK_SERVICES = [
  {
    icon: <Sprout className="w-4 h-4 text-emerald-700" />,
    title: 'Delayed PM-KISAN Installment',
    subtitle: 'Check pending DBT reasons or file a complaint (Hindi/Hinglish)',
    lang: 'hi',
    text: 'Mera PM-KISAN ka pichle 6 mahine se paisa nahi aaya, kya karun? Main Uttar Pradesh se farmer hoon.',
  },
  {
    icon: <GraduationCap className="w-4 h-4 text-sky-700" />,
    title: 'Central Scholarships & Documents',
    subtitle: 'Check eligibility for OBC/SC/ST/EWS college scholarships',
    lang: 'en',
    text: 'I am a 19-year-old OBC B.Tech student with ₹1,80,000 annual family income. Which Central scholarships am I eligible for and what documents do I need?',
  },
  {
    icon: <Hammer className="w-4 h-4 text-amber-700" />,
    title: 'PM Vishwakarma for Artisans',
    subtitle: 'Toolkit incentive, skill training & 5% concessional loan details',
    lang: 'en',
    text: 'I am a 34-year-old carpenter. Explain PM Vishwakarma toolkit incentive, loan interest rate, and exclusions.',
  },
  {
    icon: <FileText className="w-4 h-4 text-rose-700" />,
    title: 'Draft a Public Grievance (CPGRAMS)',
    subtitle: 'Generate a formal complaint letter routed to the right Ministry',
    lang: 'en',
    text: 'Please draft a formal CPGRAMS grievance to the Ministry of Agriculture because my PM-KISAN installment has been pending for 6 months in Lucknow, Uttar Pradesh.',
  },
]

function renderInlineSpans(text: string, citations: CitationItem[]): React.ReactNode {
  // Parse markdown links [label](url), **bold**, `code`, and clickable inline citations [1]
  const tokenRegex = /(\[[^\]]+\]\(https?:\/\/[^\s)]+\)|\*\*[^*]+\*\*|`[^`]+`|\[\d+\])/g
  const parts = text.split(tokenRegex)

  return parts.map((part, idx) => {
    if (!part) return null

    // Markdown link [label](url)
    const linkMatch = part.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/)
    if (linkMatch) {
      return (
        <a
          key={idx}
          href={linkMatch[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-indiaNavy font-medium underline decoration-indiaNavy/40 hover:decoration-indiaNavy inline-flex items-center gap-0.5"
        >
          {linkMatch[1]}
          <ExternalLink className="w-3 h-3 inline" />
        </a>
      )
    }

    // Bold **text**
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={idx} className="font-semibold text-slate-900">
          {part.slice(2, -2)}
        </strong>
      )
    }

    // Inline code `text`
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={idx} className="px-1.5 py-0.5 rounded bg-slate-100 text-indiaNavy font-mono text-[12px]">
          {part.slice(1, -1)}
        </code>
      )
    }

    // Clickable inline citation [1] -> directly opens that scheme's official page!
    const citeMatch = part.match(/^\[(\d+)\]$/)
    if (citeMatch) {
      const num = Number(citeMatch[1])
      const found = citations.find((c) => c.index === num)
      if (found?.source_url) {
        return (
          <a
            key={idx}
            href={found.source_url}
            target="_blank"
            rel="noopener noreferrer"
            title={`Open official source: ${found.scheme_name}`}
            className="inline-flex items-center justify-center mx-0.5 px-1.5 py-0 rounded-full bg-sky-50 hover:bg-sky-100 text-indiaNavy border border-sky-200 text-[10px] font-bold align-super transition"
          >
            {num}
          </a>
        )
      }
      return (
        <span key={idx} className="text-[11px] font-semibold text-indiaNavy ml-0.5">
          [{num}]
        </span>
      )
    }

    return <React.Fragment key={idx}>{part}</React.Fragment>
  })
}

function renderCitizenMessage(content: string, citations: CitationItem[] = []): React.ReactNode {
  const lines = content.replace(/\r\n/g, '\n').split('\n')
  const blocks: React.ReactNode[] = []
  let bulletBuffer: string[] = []
  let orderedBuffer: string[] = []

  const flushLists = (keyPrefix: string) => {
    if (bulletBuffer.length > 0) {
      blocks.push(
        <ul key={`${keyPrefix}-ul`} className="my-2 space-y-1.5 pl-5 list-disc marker:text-indiaSaffron text-[14px] leading-relaxed text-slate-700">
          {bulletBuffer.map((item, idx) => (
            <li key={idx}>{renderInlineSpans(item, citations)}</li>
          ))}
        </ul>,
      )
      bulletBuffer = []
    }
    if (orderedBuffer.length > 0) {
      blocks.push(
        <ol key={`${keyPrefix}-ol`} className="my-2 space-y-1.5 pl-5 list-decimal marker:text-indiaNavy marker:font-semibold text-[14px] leading-relaxed text-slate-700">
          {orderedBuffer.map((item, idx) => (
            <li key={idx}>{renderInlineSpans(item, citations)}</li>
          ))}
        </ol>,
      )
      orderedBuffer = []
    }
  }

  lines.forEach((rawLine, i) => {
    const trimmed = rawLine.trim()
    if (!trimmed) {
      flushLists(`sp-${i}`)
      return
    }

    // Callout / Privacy Notice (> ...)
    if (trimmed.startsWith('>')) {
      flushLists(`q-${i}`)
      const clean = trimmed.replace(/^>\s*/, '')
      blocks.push(
        <div
          key={`q-${i}`}
          className="my-2.5 px-3.5 py-2.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-950 text-xs leading-relaxed"
        >
          {renderInlineSpans(clean, citations)}
        </div>,
      )
      return
    }

    // Headings (#, ##, ###, ####) -> clean readable section titles, NEVER raw ###
    const headingMatch = trimmed.match(/^#{1,6}\s+(.*)$/)
    if (headingMatch) {
      flushLists(`h-${i}`)
      const headingText = headingMatch[1].replace(/\*\*/g, '').trim()
      const level = trimmed.startsWith('####') ? 4 : trimmed.startsWith('###') ? 3 : 2
      blocks.push(
        <h4
          key={`h-${i}`}
          className={
            level <= 3
              ? 'mt-3.5 mb-1.5 text-[15px] font-bold text-indiaNavy border-b border-slate-100 pb-1'
              : 'mt-3 mb-1 text-[14px] font-semibold text-slate-900'
          }
        >
          {renderInlineSpans(headingText, citations)}
        </h4>,
      )
      return
    }

    // Standalone **Bold Heading** on its own line
    if (/^\*\*[^*]+\*\*:?$/.test(trimmed)) {
      flushLists(`bh-${i}`)
      const cleanTitle = trimmed.replace(/^\*\*/, '').replace(/\*\*:?$/, '').trim()
      blocks.push(
        <h4 key={`bh-${i}`} className="mt-3.5 mb-1 text-[14px] font-bold text-indiaNavy">
          {cleanTitle}
        </h4>,
      )
      return
    }

    // Unordered list item (- or *)
    const bulletMatch = trimmed.match(/^[-•*]\s+(.*)$/)
    if (bulletMatch) {
      if (orderedBuffer.length) flushLists(`b-${i}`)
      bulletBuffer.push(bulletMatch[1])
      return
    }

    // Ordered list item (1. )
    const ordMatch = trimmed.match(/^\d+[.)]\s+(.*)$/)
    if (ordMatch) {
      if (bulletBuffer.length) flushLists(`o-${i}`)
      orderedBuffer.push(ordMatch[1])
      return
    }

    // Regular paragraph
    flushLists(`p-${i}`)
    blocks.push(
      <p key={`p-${i}`} className="my-1.5 text-[14px] leading-relaxed text-slate-800">
        {renderInlineSpans(trimmed, citations)}
      </p>,
    )
  })

  flushLists('end')
  return blocks
}

function parseSseBlock(rawBlock: string): { event: string; data: unknown } | null {
  const lines = rawBlock.split('\n').map((l) => l.replace(/\r$/, ''))
  let eventName = 'message'
  const dataParts: string[] = []
  for (const line of lines) {
    if (!line || line.startsWith(':')) continue
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataParts.push(line.slice(5).trim())
    }
  }
  if (!dataParts.length) return null
  try {
    return { event: eventName, data: JSON.parse(dataParts.join('\n')) }
  } catch {
    return null
  }
}

export const ChatWorkspace: React.FC<Props> = ({
  user,
  sessionId,
  initialPrompt,
  onClearInitialPrompt,
  onNewSession,
  onSelectSession,
  onTraceCreated,
}) => {
  const [language, setLanguage] = useState<string>(user.preferred_language || 'en')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [liveStep, setLiveStep] = useState<string | null>(null)
  const [profile, setProfile] = useState<CitizenProfile>(user.default_profile || {})
  const [profileOpen, setProfileOpen] = useState(false)
  const [sessionsOpen, setSessionsOpen] = useState(false)
  const [grievanceModalOpen, setGrievanceModalOpen] = useState(false)
  const [activeDraft, setActiveDraft] = useState<GrievanceDraft | null>(null)
  const [activeReceipt, setActiveReceipt] = useState<GrievanceReceipt | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  const currentLangOpt = LANGUAGE_OPTIONS.find((l) => l.code === language) || LANGUAGE_OPTIONS[0]
  const voice = useVoiceIO(currentLangOpt.speech)
  const isAdmin = user.role === 'admin'

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, liveStep])

  useEffect(() => {
    if (initialPrompt) {
      setInput(initialPrompt)
      onClearInitialPrompt?.()
    }
  }, [initialPrompt, onClearInitialPrompt])

  useEffect(() => {
    let cancelled = false
    setLanguage(user.preferred_language || 'en')
    setMessages([])
    apiFetch(`/api/sessions/${sessionId}`)
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return
        if (data?.session?.profile && Object.keys(data.session.profile).length > 0) {
          setProfile(data.session.profile)
        } else {
          setProfile(user.default_profile || {})
        }
        if (Array.isArray(data?.messages)) {
          const hydrated: ChatMessage[] = data.messages.map((m: Record<string, unknown>) => ({
            id: `db-${String(m.id)}`,
            role: (m.role === 'user' ? 'user' : 'assistant') as 'user' | 'assistant',
            content: String(m.content || ''),
            citations: Array.isArray(m.citations) ? (m.citations as ChatMessage['citations']) : [],
            eligibility_cards: Array.isArray(m.eligibility) ? (m.eligibility as ChatMessage['eligibility_cards']) : [],
            grievance_draft:
              m.grievance && typeof m.grievance === 'object' && 'draft_id' in (m.grievance as object)
                ? (m.grievance as GrievanceDraft)
                : null,
            trace_id: m.trace_id ? String(m.trace_id) : undefined,
            created_at: String(m.created_at || ''),
          }))
          setMessages(hydrated)
        } else {
          setMessages([])
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [sessionId, user])

  const appendFinalAssistantPayload = (p: {
    answer: string
    citations?: ChatMessage['citations']
    eligibility_cards?: ChatMessage['eligibility_cards']
    grievance_draft?: GrievanceDraft | null
    grievance_receipt?: GrievanceReceipt | null
    citizen_profile?: CitizenProfile
    trace_id?: string
    cache_hit?: string
    latency_ms?: number
    guardrail_flags?: string[]
  }) => {
    if (p.citizen_profile) setProfile(p.citizen_profile)
    if (p.grievance_draft) {
      setActiveReceipt(null)
      setActiveDraft(p.grievance_draft)
      setGrievanceModalOpen(true)
    }
    setMessages((prev) => [
      ...prev,
      {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: p.answer || 'No response generated.',
        citations: p.citations || [],
        eligibility_cards: p.eligibility_cards || [],
        grievance_draft: p.grievance_draft || null,
        grievance_receipt: p.grievance_receipt || null,
        trace_id: p.trace_id,
        cache_hit: p.cache_hit,
        latency_ms: p.latency_ms,
        guardrail_flags: p.guardrail_flags || [],
        created_at: new Date().toLocaleTimeString(),
      },
    ])
    onTraceCreated?.()
  }

  const sendMessage = async (textOverride?: string, langOverride?: string) => {
    const text = (textOverride ?? input).trim()
    if (!text || loading) return
    const reqLang = langOverride ?? language
    if (langOverride) setLanguage(langOverride)
    if (!textOverride) setInput('')

    setMessages((prev) => [
      ...prev,
      {
        id: `u-${Date.now()}`,
        role: 'user',
        content: text,
        created_at: new Date().toLocaleTimeString(),
      },
    ])
    setLoading(true)
    setLiveStep('Reviewing your question...')

    try {
      const resp = await apiFetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: text,
          language: reqLang,
        }),
      })

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
        throw new Error(errData.detail || `Server error ${resp.status}`)
      }

      const reader = resp.body?.getReader()
      if (!reader) throw new Error('Streaming unavailable')
      const decoder = new TextDecoder()
      let buffer = ''
      let finalPayload: Record<string, unknown> | null = null

      const handleParsedBlock = (block: string) => {
        const parsed = parseSseBlock(block)
        if (!parsed) return
        const evName = parsed.event
        const data = parsed.data as Record<string, unknown>
        if (evName === 'guardrail' && data.status) {
          setLiveStep(String(data.status))
        } else if (
          evName === 'language' ||
          evName === 'planner' ||
          evName === 'tool_call' ||
          evName === 'synthesizer' ||
          evName === 'critic' ||
          evName === 'localize'
        ) {
          setLiveStep(String(data.status || 'Looking up official scheme information...'))
        } else if (evName === 'final') {
          finalPayload = data
        } else if (evName === 'error') {
          throw new Error(String(data.detail || 'Stream error'))
        }
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
        const blocks = buffer.split('\n\n')
        buffer = blocks.pop() || ''
        for (const blk of blocks) {
          if (blk.trim()) handleParsedBlock(blk)
        }
      }
      if (buffer.trim()) handleParsedBlock(buffer)

      if (finalPayload) {
        appendFinalAssistantPayload(finalPayload as Parameters<typeof appendFinalAssistantPayload>[0])
      } else {
        setLiveStep('Finishing your response...')
        const syncResp = await apiFetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId, message: text, language: reqLang }),
        })
        if (!syncResp.ok) {
          const errData = await syncResp.json().catch(() => ({ detail: `HTTP ${syncResp.status}` }))
          throw new Error(errData.detail || 'Failed to get response')
        }
        appendFinalAssistantPayload(await syncResp.json())
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: 'assistant',
          content: `We could not complete your request right now: ${
            err instanceof Error ? err.message : 'Please try again in a moment.'
          }`,
          created_at: new Date().toLocaleTimeString(),
        },
      ])
    } finally {
      setLoading(false)
      setLiveStep(null)
    }
  }

  const handleSaveProfile = async (newProf: CitizenProfile) => {
    const r = await apiFetch(`/api/sessions/${sessionId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preferred_language: language, profile: newProf }),
    })
    if (r.ok) {
      const data = await r.json()
      setProfile(data.session.profile || newProf)
    }
  }

  const handleDeleteAllData = async () => {
    await apiFetch(`/api/sessions/${sessionId}`, { method: 'DELETE' })
    setProfile({})
    setMessages([])
    onNewSession()
  }

  const profileCount = Object.values(profile).filter((v) => v !== null && v !== undefined && v !== '').length

  return (
    <div className="flex flex-col h-[calc(100vh-112px)] max-w-4xl mx-auto">
      {/* Calm Citizen Utility Bar with Session Controls & Direct Raise Grievance CTA */}
      <div className="bg-white border border-slate-200/90 rounded-xl px-3.5 py-2.5 mb-3 flex flex-wrap items-center justify-between gap-2 shadow-2xs">
        <div className="flex flex-wrap items-center gap-2">
          <Globe className="w-4 h-4 text-indiaNavy" />
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            aria-label="Preferred Language"
            className="text-xs font-semibold text-slate-800 border border-slate-300 rounded-lg px-2.5 py-1.5 bg-slate-50 focus:bg-white focus:border-indiaNavy focus:outline-none"
          >
            {LANGUAGE_OPTIONS.map((opt) => (
              <option key={opt.code} value={opt.code}>
                {opt.label}
              </option>
            ))}
          </select>

          <button
            type="button"
            onClick={() => {
              setMessages([])
              setInput('')
              onNewSession()
            }}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-xs font-medium text-slate-700 transition"
            title="Start a fresh conversation session"
          >
            <MessageSquarePlus className="w-3.5 h-3.5 text-indiaNavy" />
            New Chat
          </button>

          <button
            type="button"
            onClick={() => setSessionsOpen(true)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-xs font-medium text-slate-700 transition"
            title="View your past conversations"
          >
            <History className="w-3.5 h-3.5 text-indiaNavy" />
            Sessions
          </button>

          {messages.length > 0 && (
            <button
              type="button"
              onClick={async () => {
                await apiFetch(`/api/sessions/${sessionId}`, { method: 'DELETE' })
                setMessages([])
                onNewSession()
              }}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-rose-200 bg-rose-50/70 hover:bg-rose-100 text-xs font-medium text-rose-700 transition"
              title="Close and erase current chat session"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Close Session
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setActiveDraft(null)
              setActiveReceipt(null)
              setGrievanceModalOpen(true)
            }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indiaSaffron hover:bg-orange-600 text-white text-xs font-semibold shadow-2xs transition"
          >
            <FilePlus2 className="w-3.5 h-3.5" />
            Raise Grievance
          </button>

          <button
            type="button"
            onClick={() => setProfileOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-xs font-semibold text-indiaNavy transition"
          >
            <UserCheck className="w-4 h-4 text-indiaSaffron" />
            My Profile
            {profileCount > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-indiaNavy text-white text-[10px]">
                {profileCount}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Conversation Area */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1 pb-4">
        {messages.length === 0 && (
          <div className="bg-white border border-slate-200/90 rounded-2xl p-6 sm:p-8 space-y-5 shadow-2xs">
            <div className="space-y-1.5">
              <p className="text-xs font-semibold uppercase tracking-wide text-indiaSaffron">
                Citizen Helpdesk
              </p>
              <h2 className="text-xl sm:text-2xl font-bold text-indiaNavy">
                Namaste, {user.display_name}. How can we assist you today?
              </h2>
              <p className="text-sm text-slate-600 leading-relaxed max-w-2xl">
                Ask about any Central Government scheme, check your eligibility and required documents,
                or get help drafting and tracking a formal CPGRAMS public grievance.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              {QUICK_SERVICES.map((svc, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => sendMessage(svc.text, svc.lang)}
                  className="p-4 rounded-xl border border-slate-200 bg-[#FAF9F6] hover:bg-white hover:border-indiaNavy hover:shadow-xs transition text-left flex items-start gap-3"
                >
                  <div className="w-8 h-8 rounded-lg bg-white border border-slate-200 flex items-center justify-center shrink-0 mt-0.5">
                    {svc.icon}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{svc.title}</p>
                    <p className="text-xs text-slate-500 mt-0.5 leading-snug">{svc.subtitle}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => {
          const citations = m.citations || []
          // Deduplicate official scheme links and separate live .gov.in web search links
          const schemeLinksMap = new Map<string, CitationItem>()
          const webLinksMap = new Map<string, CitationItem>()
          for (const c of citations) {
            if (!c.source_url) continue
            if (c.source_type === 'gov_web') {
              if (!webLinksMap.has(c.source_url)) webLinksMap.set(c.source_url, c)
            } else {
              if (!schemeLinksMap.has(c.source_url)) schemeLinksMap.set(c.source_url, c)
            }
          }
          const officialSchemes = Array.from(schemeLinksMap.values())
          const webSources = Array.from(webLinksMap.values())

          return (
            <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[94%] sm:max-w-[88%] rounded-2xl px-5 py-4 shadow-2xs ${
                  m.role === 'user'
                    ? 'bg-indiaNavy text-white rounded-br-sm text-sm leading-relaxed'
                    : 'bg-white border border-slate-200/90 text-slate-800 rounded-bl-sm'
                }`}
              >
                {m.role === 'user' ? (
                  <p className="whitespace-pre-wrap">{m.content}</p>
                ) : (
                  <div>{renderCitizenMessage(m.content, citations)}</div>
                )}

                {/* Eligibility & Document Checklist Cards */}
                {m.eligibility_cards && m.eligibility_cards.length > 0 && (
                  <div className="mt-3 space-y-2.5">
                    {m.eligibility_cards.map((ec, idx) => (
                      <EligibilityCard key={idx} card={ec} />
                    ))}
                  </div>
                )}

                {/* Grievance Draft HITL Action Card */}
                {m.grievance_draft && (
                  <div className="mt-4 p-4 rounded-xl bg-amber-50 border border-amber-300 flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-start gap-2.5 text-xs text-amber-950">
                      <FileWarning className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
                      <div>
                        <p className="font-bold text-sm text-amber-950">Your Grievance Draft is Ready for Review</p>
                        <p className="text-amber-800 mt-0.5">
                          Routed to <strong>{m.grievance_draft.ministry_name}</strong> ({m.grievance_draft.char_count} / 2000 characters). Nothing is submitted until you confirm.
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setActiveReceipt(null)
                        setActiveDraft(m.grievance_draft || null)
                        setGrievanceModalOpen(true)
                      }}
                      className="px-4 py-2 rounded-lg bg-indiaSaffron hover:bg-orange-600 text-white text-xs font-semibold shadow-xs transition"
                    >
                      Review &amp; Submit Grievance
                    </button>
                  </div>
                )}

                {/* Direct Official Scheme Links (myScheme.gov.in) */}
                {m.role === 'assistant' && officialSchemes.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-slate-100">
                    <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
                      <BookOpen className="w-3.5 h-3.5 text-indiaNavy" />
                      Direct Official Scheme Pages
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {officialSchemes.slice(0, 4).map((c) => (
                        <a
                          key={c.source_url}
                          href={c.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center justify-between gap-2 px-3 py-2 rounded-xl bg-[#FAF9F6] hover:bg-sky-50 border border-slate-200 hover:border-indiaNavy/40 transition group"
                        >
                          <div className="min-w-0">
                            <p className="text-xs font-semibold text-indiaNavy truncate group-hover:underline">
                              {c.scheme_name}
                            </p>
                            {c.ministry && (
                              <p className="text-[11px] text-slate-500 truncate">{c.ministry}</p>
                            )}
                          </div>
                          <ExternalLink className="w-3.5 h-3.5 text-slate-400 group-hover:text-indiaNavy shrink-0" />
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                {/* Live .gov.in Web Search Links (DuckDuckGo / Tavily) */}
                {m.role === 'assistant' && webSources.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-100">
                    <p className="text-[11px] font-semibold text-emerald-800 uppercase tracking-wide mb-2 flex items-center gap-1.5">
                      <Globe className="w-3.5 h-3.5 text-emerald-700" />
                      Official Government Web Links Found (.gov.in / .nic.in)
                    </p>
                    <div className="space-y-1.5">
                      {webSources.map((w) => (
                        <a
                          key={w.source_url}
                          href={w.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-emerald-50/60 hover:bg-emerald-50 border border-emerald-200 text-xs text-emerald-950 transition"
                        >
                          <span className="truncate font-medium">{w.scheme_name}</span>
                          <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700 shrink-0">
                            Open Link <ExternalLink className="w-3 h-3" />
                          </span>
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                {/* Clean Footer (Read Aloud for all; Trace ID only for Admin) */}
                {m.role === 'assistant' && (
                  <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between gap-2 text-[11px] text-slate-400">
                    <div className="flex items-center gap-2">
                      {isAdmin && m.trace_id && (
                        <span className="font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                          {m.trace_id}
                        </span>
                      )}
                      {isAdmin && m.latency_ms !== undefined && (
                        <span>{(m.latency_ms / 1000).toFixed(1)}s</span>
                      )}
                    </div>
                    {voice.ttsSupported && (
                      <button
                        type="button"
                        onClick={() => (voice.isSpeaking || voice.isLoadingAudio ? voice.stopSpeaking() : voice.speak(m.content))}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg hover:bg-slate-100 text-slate-600 hover:text-indiaNavy font-medium transition"
                      >
                        {voice.isLoadingAudio ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin text-indiaSaffron" />
                        ) : voice.isSpeaking ? (
                          <VolumeX className="w-3.5 h-3.5" />
                        ) : (
                          <Volume2 className="w-3.5 h-3.5" />
                        )}
                        {voice.isLoadingAudio ? 'Loading Audio...' : voice.isSpeaking ? 'Stop Audio' : 'Listen'}
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          )
        })}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-slate-200 rounded-2xl px-4 py-3 text-xs text-slate-600 flex items-center gap-2.5 shadow-2xs">
              <Loader2 className="w-4 h-4 animate-spin text-indiaSaffron" />
              <span>{liveStep || 'Looking up official scheme information...'}</span>
            </div>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      {voice.voiceError && (
        <div className="mb-2 px-3 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-xs">
          {voice.voiceError}
        </div>
      )}

      {/* Clean Message Input Bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          sendMessage()
        }}
        className="bg-white border border-slate-300 rounded-2xl p-2 flex items-center gap-2 shadow-sm focus-within:border-indiaNavy transition"
      >
        <button
          type="button"
          onClick={() =>
            voice.isListening
              ? voice.stopListening()
              : voice.startListening((transcript) => setInput((prev) => (prev ? `${prev} ${transcript}` : transcript)))
          }
          className={`p-2.5 rounded-xl transition ${
            voice.isListening
              ? 'bg-rose-600 text-white animate-pulse'
              : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
          }`}
          title={voice.sttSupported ? `Speak in ${currentLangOpt.label}` : 'Voice input unsupported in this browser'}
        >
          {voice.isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
        </button>

        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={`Ask about schemes, eligibility, documents, or grievances (${currentLangOpt.label})...`}
          className="flex-1 text-sm bg-transparent px-2 py-2 focus:outline-none text-slate-900 placeholder-slate-400"
          disabled={loading}
        />

        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-indiaNavy hover:bg-slate-800 disabled:opacity-40 text-white font-semibold text-sm transition"
        >
          <Send className="w-4 h-4" />
          <span className="hidden sm:inline">Ask</span>
        </button>
      </form>

      <SessionsSidebar
        open={sessionsOpen}
        onClose={() => setSessionsOpen(false)}
        activeSessionId={sessionId}
        busy={loading}
        onSelectSession={onSelectSession}
      />

      <ProfileDrawer
        open={profileOpen}
        onClose={() => setProfileOpen(false)}
        sessionId={sessionId}
        profile={profile}
        onSaveProfile={handleSaveProfile}
        onDeleteAllData={handleDeleteAllData}
      />

      <GrievanceModal
        open={grievanceModalOpen}
        sessionId={sessionId}
        defaultApplicantName={user.display_name}
        draft={activeDraft}
        receipt={activeReceipt}
        onClose={() => {
          setGrievanceModalOpen(false)
          setActiveDraft(null)
          setActiveReceipt(null)
        }}
        onConfirmed={(receipt, emailNotif) => {
          setActiveReceipt(receipt)
          setMessages((prev) => [
            ...prev,
            {
              id: `rec-${Date.now()}`,
              role: 'assistant',
              content:
                `**Grievance Registered Successfully**\n\n` +
                `- **Registration Number:** \`${receipt.registration_number}\`\n` +
                `- **Target Ministry:** ${receipt.ministry_name} (\`${receipt.ministry_code}\`)\n` +
                `- **Current Status:** ${receipt.status} (${receipt.mode.toUpperCase()})\n` +
                (emailNotif
                  ? `- **Confirmation Email:** ${emailNotif.delivery_status === 'SENT_SMTP' ? 'Sent to' : 'Saved in Sandbox Outbox for'} \`${emailNotif.recipient_email}\`\n`
                  : '') +
                `\nYou can view the full CPGRAMS Sandbox receipt & email anytime in the **Public Grievances** tab or ask me to track \`${receipt.registration_number}\`.`,
              grievance_receipt: receipt,
              created_at: new Date().toLocaleTimeString(),
            },
          ])
        }}
      />
    </div>
  )
}
