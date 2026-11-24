import React, { useState, useEffect, useCallback } from 'react'
import {
  Activity,
  RefreshCw,
  ShieldAlert,
  Zap,
  Clock,
  Cpu,
  Download,
  Copy,
  Check,
  Search,
  Trash2,
  ChevronDown,
  ChevronRight,
  FileJson,
  FileText,
} from 'lucide-react'
import { TraceRecord, TraceSpan } from '../types'
import { apiFetch, downloadAuthenticatedFile } from '../api'

interface TraceSummary {
  total_traces: number
  avg_latency_ms: number
  cache_hits: number
  cache_hit_rate: number
  guardrail_blocks: number
  total_prompt_tokens: number
  total_completion_tokens: number
}

const SPAN_BADGE: Record<string, string> = {
  GUARDRAIL: 'bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-400/15 dark:text-amber-200 dark:border-amber-400/40',
  LLM: 'bg-indigo-100 text-indigo-900 border-indigo-300 dark:bg-indigo-400/15 dark:text-indigo-200 dark:border-indigo-400/40',
  RETRIEVAL: 'bg-emerald-100 text-emerald-900 border-emerald-300 dark:bg-emerald-400/15 dark:text-emerald-200 dark:border-emerald-400/40',
  TOOL: 'bg-sky-100 text-sky-900 border-sky-300 dark:bg-sky-400/15 dark:text-sky-200 dark:border-sky-400/40',
}

export const TraceDashboard: React.FC = () => {
  const [traces, setTraces] = useState<TraceRecord[]>([])
  const [summary, setSummary] = useState<TraceSummary | null>(null)
  const [selected, setSelected] = useState<TraceRecord | null>(null)
  const [search, setSearch] = useState('')
  const [hideErased, setHideErased] = useState(true)
  const [loading, setLoading] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [expandedSpan, setExpandedSpan] = useState<string | null>(null)
  const [actionMsg, setActionMsg] = useState<string | null>(null)

  const loadTraces = useCallback(async () => {
    setLoading(true)
    const params = new URLSearchParams({ limit: '50', hide_erased: String(hideErased) })
    if (search.trim()) params.set('search', search.trim())
    try {
      const r = await apiFetch(`/api/traces?${params}`)
      if (!r.ok) return
      const d = await r.json()
      const items: TraceRecord[] = d.items || []
      setTraces(items)
      setSummary(d.summary || null)
      setSelected((prev) => {
        if (prev && items.some((x) => x.trace_id === prev.trace_id)) {
          return items.find((x) => x.trace_id === prev.trace_id) || prev
        }
        return items[0] || null
      })
    } finally {
      setLoading(false)
    }
  }, [search, hideErased])

  useEffect(() => {
    const t = setTimeout(() => loadTraces(), 150)
    return () => clearTimeout(t)
  }, [loadTraces])

  const copyTraceId = (id: string) => {
    navigator.clipboard?.writeText(id)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 1800)
  }

  const handleCleanup = async () => {
    const r = await apiFetch('/api/traces/cleanup', { method: 'DELETE' })
    if (r.ok) {
      const d = await r.json()
      setActionMsg(`Cleaned ${d.removed_traces} erased test traces.`)
      loadTraces()
      setTimeout(() => setActionMsg(null), 3500)
    }
  }

  const handleDownload = async (url: string, fname: string) => {
    try {
      await downloadAuthenticatedFile(url, fname)
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : 'Export failed')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-base font-bold text-indiaNavy dark:text-slate-100 flex items-center gap-2">
            <Activity className="w-4 h-4 text-indiaSaffron" />
            Langfuse-Style Execution Trace &amp; Span Debugger (Admin)
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Search by Trace ID, inspect per-span inputs/outputs/tokens/latencies, and export structured JSON or Markdown debug reports.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={() => handleDownload(`/api/traces/export/all?format=json&hide_erased=${hideErased}`, 'jansahayak_traces.json')}
            className="btn-secondary gap-1 px-3 py-1.5 text-xs"
          >
            <Download className="w-3.5 h-3.5 text-indiaNavy dark:text-sky-300" /> Export All JSON
          </button>
          <button
            type="button"
            onClick={() => handleDownload(`/api/traces/export/all?format=csv&hide_erased=${hideErased}`, 'jansahayak_traces.csv')}
            className="btn-secondary gap-1 px-3 py-1.5 text-xs"
          >
            <Download className="w-3.5 h-3.5 text-emerald-700 dark:text-emerald-400" /> Export CSV
          </button>
          <button
            type="button"
            onClick={handleCleanup}
            className="inline-flex items-center gap-1 rounded-full border border-rose-300/70 bg-rose-50/80 px-3 py-1.5 text-xs font-medium text-rose-700 transition hover:bg-rose-100 dark:border-rose-400/30 dark:bg-rose-500/15 dark:text-rose-300 dark:hover:bg-rose-500/25"
            title="Delete anonymized [ERASED_BY_USER] test traces"
          >
            <Trash2 className="w-3.5 h-3.5" /> Clean Erased
          </button>
          <button
            type="button"
            onClick={loadTraces}
            className="btn-secondary gap-1 px-3 py-1.5 text-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>
      </div>

      {actionMsg && (
        <div className="glass-subtle px-4 py-2.5 border-emerald-300/70 bg-emerald-50/80 text-emerald-800 text-xs shadow-sm dark:border-emerald-400/30 dark:bg-emerald-500/15 dark:text-emerald-200">
          {actionMsg}
        </div>
      )}

      {/* Search & Filter Bar */}
      <div className="glass-subtle p-3 flex flex-wrap items-center gap-3 shadow-sm">
        <div className="flex-1 min-w-[220px] relative">
          <Search className="w-4 h-4 text-slate-400 dark:text-slate-500 absolute left-3 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter by Trace ID (e.g. TRC-...), user persona (ramesh, priya, admin), or query text..."
            className="field pl-9 pr-3 py-2 text-xs"
          />
        </div>
        <label className="inline-flex items-center gap-2 text-xs text-slate-700 dark:text-slate-200 cursor-pointer">
          <input
            type="checkbox"
            checked={hideErased}
            onChange={(e) => setHideErased(e.target.checked)}
            className="accent-indiaNavy dark:accent-indiaSaffron"
          />
          Hide erased test traces
        </label>
      </div>

      {/* KPI Row */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <div className="glass-subtle p-4 shadow-sm">
            <p className="text-[11px] text-slate-500 dark:text-slate-400">Active Traces</p>
            <p className="text-xl font-bold text-slate-900 dark:text-slate-100">{summary.total_traces}</p>
          </div>
          <div className="glass-subtle p-4 shadow-sm">
            <p className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1"><Clock className="w-3 h-3" /> Avg Latency</p>
            <p className="text-xl font-bold text-indiaNavy dark:text-sky-300">{(summary.avg_latency_ms / 1000).toFixed(2)}s</p>
          </div>
          <div className="glass-subtle p-4 shadow-sm">
            <p className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1"><Zap className="w-3 h-3 text-emerald-600 dark:text-emerald-400" /> Cache Hit Rate</p>
            <p className="text-xl font-bold text-emerald-700 dark:text-emerald-400">{summary.cache_hit_rate}%</p>
          </div>
          <div className="glass-subtle p-4 shadow-sm">
            <p className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1"><ShieldAlert className="w-3 h-3 text-rose-600 dark:text-rose-400" /> Guardrail Blocks</p>
            <p className="text-xl font-bold text-rose-700 dark:text-rose-400">{summary.guardrail_blocks}</p>
          </div>
          <div className="glass-subtle p-4 shadow-sm">
            <p className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1"><Cpu className="w-3 h-3" /> Tokens Used</p>
            <p className="text-xl font-bold text-slate-900 dark:text-slate-100">
              {((summary.total_prompt_tokens + summary.total_completion_tokens) / 1000).toFixed(1)}k
            </p>
          </div>
        </div>
      )}

      {/* Split View */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-4 glass overflow-hidden">
          <div className="px-4 py-3 bg-white/40 border-b border-slate-200/70 text-xs font-semibold text-indiaNavy dark:bg-white/5 dark:border-white/10 dark:text-slate-100">
            Traces ({traces.length})
          </div>
          <div className="divide-y divide-slate-200/70 dark:divide-white/10 max-h-[620px] overflow-y-auto">
            {traces.length === 0 && (
              <p className="p-6 text-xs text-slate-400 dark:text-slate-500 text-center">No matching traces found.</p>
            )}
            {traces.map((t) => (
              <button
                key={t.trace_id}
                type="button"
                onClick={() => {
                  setSelected(t)
                  setExpandedSpan(null)
                }}
                className={`w-full text-left p-3.5 transition hover:bg-white/60 dark:hover:bg-white/10 ${
                  selected?.trace_id === t.trace_id ? 'bg-sky-50/70 border-l-4 border-indiaNavy dark:bg-sky-400/15 dark:border-sky-400' : ''
                }`}
              >
                <div className="flex items-center justify-between gap-2 text-[11px]">
                  <span className="font-mono font-bold text-indiaNavy dark:text-sky-300">{t.trace_id}</span>
                  <div className="flex items-center gap-1">
                    {t.cache_hit !== 'miss' && (
                      <span className="px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-semibold dark:bg-emerald-400/15 dark:text-emerald-300">
                        {t.cache_hit}
                      </span>
                    )}
                    {t.status === 'blocked_by_guardrail' && (
                      <span className="px-1.5 py-0.5 rounded-full bg-rose-100 text-rose-700 font-semibold dark:bg-rose-400/15 dark:text-rose-300">BLOCKED</span>
                    )}
                    <span className="font-mono text-slate-500 dark:text-slate-400">{(t.total_latency_ms / 1000).toFixed(2)}s</span>
                  </div>
                </div>
                <p className="text-xs text-slate-800 dark:text-slate-200 line-clamp-2 mt-1">{t.user_query_masked}</p>
                <div className="flex items-center justify-between text-[10px] text-slate-400 dark:text-slate-500 mt-1">
                  <span>@{t.user_id || 'anonymous'} ({t.detected_lang})</span>
                  <span>{t.prompt_tokens + t.completion_tokens} tok</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="lg:col-span-8 glass p-5 space-y-4 max-h-[660px] overflow-y-auto">
          {!selected ? (
            <p className="text-xs text-slate-400 dark:text-slate-500 text-center py-12">Select a trace to inspect full spans, outputs &amp; debug data.</p>
          ) : (
            <>
              {/* Header + Download Actions */}
              <div className="flex flex-wrap items-start justify-between gap-2 border-b border-slate-200/70 dark:border-white/10 pb-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h4 className="font-mono font-bold text-sm text-indiaNavy dark:text-sky-300">{selected.trace_id}</h4>
                    <button
                      type="button"
                      onClick={() => copyTraceId(selected.trace_id)}
                      className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 bg-slate-100 hover:bg-slate-200 text-[10px] font-medium text-slate-700 transition dark:bg-white/10 dark:text-slate-200 dark:hover:bg-white/15"
                    >
                      {copiedId === selected.trace_id ? <Check className="w-3 h-3 text-emerald-600 dark:text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      {copiedId === selected.trace_id ? 'Copied' : 'Copy ID'}
                    </button>
                    <span className="px-2 py-0.5 rounded-full bg-slate-100 text-[10px] font-mono text-slate-700 dark:bg-white/10 dark:text-slate-200">
                      @{selected.user_id || 'anonymous'} ({selected.user_role || 'citizen'})
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                    Model: <strong>{selected.model_name || 'Qwen/Qwen3-8B'}</strong> &bull; Latency:{' '}
                    <strong>{(selected.total_latency_ms / 1000).toFixed(2)}s</strong> &bull; Tokens:{' '}
                    <strong>{selected.prompt_tokens}p / {selected.completion_tokens}c</strong> &bull; {selected.timestamp}
                  </p>
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() =>
                      handleDownload(`/api/traces/${selected.trace_id}/export?format=json`, `trace_${selected.trace_id}.json`)
                    }
                    className="btn-primary gap-1 px-3 py-1.5 text-[11px]"
                  >
                    <FileJson className="w-3.5 h-3.5" /> Download JSON
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      handleDownload(`/api/traces/${selected.trace_id}/export?format=md`, `trace_${selected.trace_id}.md`)
                    }
                    className="inline-flex items-center gap-1 rounded-full border border-indiaNavy/60 px-3 py-1.5 text-[11px] font-semibold text-indiaNavy transition hover:bg-sky-50 dark:border-sky-400/50 dark:text-sky-300 dark:hover:bg-sky-400/10"
                  >
                    <FileText className="w-3.5 h-3.5" /> Debug Report (.md)
                  </button>
                </div>
              </div>

              {/* Input & Output Side-by-Side (Langfuse style) */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="glass-subtle p-4 shadow-sm">
                  <p className="text-[10px] font-bold uppercase text-slate-500 dark:text-slate-400 mb-1">Input (PII-Masked)</p>
                  <p className="text-xs text-slate-800 dark:text-slate-200 whitespace-pre-wrap">{selected.user_query_masked}</p>
                </div>
                <div className="p-4 rounded-2xl bg-emerald-50/60 border border-emerald-200/80 shadow-sm backdrop-blur-md dark:bg-emerald-500/10 dark:border-emerald-400/25">
                  <p className="text-[10px] font-bold uppercase text-emerald-800 dark:text-emerald-300 mb-1">Final Assistant Output</p>
                  <p className="text-xs text-slate-800 dark:text-slate-200 whitespace-pre-wrap max-h-36 overflow-y-auto">
                    {selected.final_answer || '(Legacy trace prior to v1.1 output capture)'}
                  </p>
                </div>
              </div>

              {/* Guardrail Flags */}
              {selected.guardrail_flags.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {selected.guardrail_flags.map((fl, i) => (
                    <span key={i} className="px-2 py-0.5 rounded-full bg-rose-50 border border-rose-200 text-rose-700 text-[11px] font-medium dark:bg-rose-500/15 dark:border-rose-400/30 dark:text-rose-300">
                      {fl}
                    </span>
                  ))}
                </div>
              )}

              {/* Langfuse-Style Interactive Spans Timeline */}
              {selected.spans && selected.spans.length > 0 ? (
                <div>
                  <p className="text-xs font-semibold text-slate-800 dark:text-slate-100 mb-2">
                    Execution Spans ({selected.spans.length}) — Click any span to inspect I/O
                  </p>
                  <div className="space-y-1.5">
                    {selected.spans.map((sp: TraceSpan) => {
                      const isOpen = expandedSpan === sp.span_id
                      const widthPct = Math.min(100, Math.max(3, (sp.duration_ms / Math.max(selected.total_latency_ms, 1)) * 100))
                      const leftPct = Math.min(95, (sp.start_offset_ms / Math.max(selected.total_latency_ms, 1)) * 100)
                      const badgeCls = SPAN_BADGE[sp.type] || 'bg-slate-100 text-slate-700 border-slate-300 dark:bg-white/10 dark:text-slate-200 dark:border-white/15'
                      return (
                        <div key={sp.span_id} className="border border-slate-200/80 dark:border-white/10 rounded-xl overflow-hidden bg-white/40 dark:bg-white/5">
                          <button
                            type="button"
                            onClick={() => setExpandedSpan(isOpen ? null : sp.span_id)}
                            className="w-full px-3 py-2 flex flex-wrap items-center justify-between gap-2 hover:bg-white/60 dark:hover:bg-white/10 transition text-left text-xs"
                          >
                            <div className="flex items-center gap-2">
                              {isOpen ? <ChevronDown className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500" />}
                              <span className="font-mono text-[10px] text-slate-400 dark:text-slate-500">{sp.span_id}</span>
                              <span className={`px-1.5 py-0.5 rounded border text-[9px] font-bold ${badgeCls}`}>
                                {sp.type}
                              </span>
                              <span className="font-medium text-slate-800 dark:text-slate-100">{sp.name}</span>
                              {sp.error && (
                                <span className="px-1.5 py-0.5 rounded bg-rose-100 text-rose-700 text-[10px] font-semibold dark:bg-rose-400/15 dark:text-rose-300">
                                  ERR
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-3">
                              {sp.tokens && sp.tokens.total > 0 && (
                                <span className="font-mono text-[10px] text-slate-500 dark:text-slate-400">{sp.tokens.total} tok</span>
                              )}
                              <div className="w-24 bg-slate-200/80 dark:bg-white/10 h-2 rounded-full relative overflow-hidden hidden sm:block">
                                <div
                                  className="h-full bg-indiaNavy dark:bg-sky-400 rounded-full absolute"
                                  style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                                />
                              </div>
                              <span className="font-mono text-[11px] font-semibold text-slate-700 dark:text-slate-200 w-16 text-right">
                                {Math.round(sp.duration_ms)}ms
                              </span>
                            </div>
                          </button>
                          {isOpen && (
                            <div className="px-3 pb-3 pt-2 bg-slate-900 dark:bg-black/50 text-slate-100 text-[10px] font-mono space-y-2 border-t border-slate-700 dark:border-white/10">
                              {sp.error && <div className="text-rose-300">ERROR: {sp.error}</div>}
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                <div>
                                  <p className="text-slate-400 uppercase mb-1">Span Input</p>
                                  <pre className="overflow-x-auto max-h-40">{JSON.stringify(sp.input, null, 2)}</pre>
                                </div>
                                <div>
                                  <p className="text-slate-400 uppercase mb-1">Span Output</p>
                                  <pre className="overflow-x-auto max-h-40 text-emerald-200">{JSON.stringify(sp.output, null, 2)}</pre>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              ) : (
                <div>
                  <p className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-2">Step Latency Waterfall</p>
                  <div className="space-y-1.5">
                    {Object.entries(selected.step_latencies || {}).map(([step, ms]) => {
                      const pct = Math.min(100, Math.max(4, (ms / Math.max(selected.total_latency_ms, 1)) * 100))
                      return (
                        <div key={step} className="flex items-center gap-2 text-xs">
                          <span className="w-36 font-mono text-[11px] text-slate-600 dark:text-slate-300 truncate">{step}</span>
                          <div className="flex-1 bg-slate-200/80 dark:bg-white/10 rounded-full h-2.5 overflow-hidden">
                            <div className="h-full bg-indiaNavy dark:bg-sky-400 rounded-full" style={{ width: `${pct}%` }} />
                          </div>
                          <span className="w-16 text-right font-mono text-[11px] text-slate-700 dark:text-slate-200">{Math.round(ms)}ms</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Retrieved Chunks Scores Table */}
              {selected.retrieved_chunks.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1.5">Hybrid Retrieval &amp; Reranker Scores</p>
                  <div className="overflow-x-auto border border-slate-200/80 dark:border-white/10 rounded-xl bg-white/30 dark:bg-white/5">
                    <table className="w-full text-[11px]">
                      <thead className="bg-slate-100/70 text-slate-600 dark:bg-white/10 dark:text-slate-300">
                        <tr>
                          <th className="text-left p-2">Scheme / Section</th>
                          <th className="text-right p-2">BM25</th>
                          <th className="text-right p-2">Dense</th>
                          <th className="text-right p-2">RRF</th>
                          <th className="text-right p-2">Rerank</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200/70 dark:divide-white/10">
                        {selected.retrieved_chunks.map((c, idx) => (
                          <tr key={idx}>
                            <td className="p-2">
                              <span className="font-medium text-slate-900 dark:text-slate-100">{c.scheme_name}</span>
                              <span className="text-slate-400 dark:text-slate-500 ml-1">({c.section})</span>
                            </td>
                            <td className="p-2 text-right font-mono">{c.scores?.bm25?.toFixed(2) ?? '-'}</td>
                            <td className="p-2 text-right font-mono">{c.scores?.dense?.toFixed(3) ?? '-'}</td>
                            <td className="p-2 text-right font-mono">{c.scores?.rrf?.toFixed(4) ?? '-'}</td>
                            <td className="p-2 text-right font-mono font-bold text-emerald-700 dark:text-emerald-400">
                              {c.scores?.rerank?.toFixed(3) ?? '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Planner / Critic Raw JSON */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <p className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">Planner Output JSON</p>
                  <pre className="p-2.5 rounded-xl bg-slate-900 dark:bg-black/50 text-slate-100 text-[10px] overflow-x-auto max-h-40 border border-transparent dark:border-white/10">
                    {JSON.stringify(selected.planner, null, 2)}
                  </pre>
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">Critic Audit JSON</p>
                  <pre className="p-2.5 rounded-xl bg-slate-900 dark:bg-black/50 text-emerald-200 text-[10px] overflow-x-auto max-h-40 border border-transparent dark:border-white/10">
                    {JSON.stringify(selected.critic, null, 2)}
                  </pre>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
