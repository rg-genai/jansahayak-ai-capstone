import React, { useState, useEffect, useCallback } from 'react'
import { Search, ExternalLink, X, Building2, Filter, ChevronLeft, ChevronRight } from 'lucide-react'
import { SchemeSummary } from '../types'

interface MinistryItem {
  ministry_code: string
  ministry_name: string
  scheme_count: number
}

interface SchemeDetail {
  scheme: SchemeSummary & {
    detailed_description: string
    benefits: string
    eligibility: string
    exclusions: string
    application_process: string
    documents_required: string
  }
  faqs: Array<{ faq_number: number; question: string; answer: string }>
}

export const SchemeExplorer: React.FC = () => {
  const [query, setQuery] = useState('')
  const [ministry, setMinistry] = useState('')
  const [dbtOnly, setDbtOnly] = useState(false)
  const [ministries, setMinistries] = useState<MinistryItem[]>([])
  const [items, setItems] = useState<SchemeSummary[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<SchemeDetail | null>(null)
  const limit = 18

  useEffect(() => {
    fetch('/api/ministries')
      .then((r) => r.json())
      .then((d) => setMinistries(d.ministries || []))
      .catch(() => {})
  }, [])

  const fetchSchemes = useCallback(async () => {
    setLoading(true)
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (query.trim()) params.set('q', query.trim())
    if (ministry) params.set('ministry', ministry)
    if (dbtOnly) params.set('dbt_only', 'true')
    try {
      const r = await fetch(`/api/schemes?${params}`)
      const d = await r.json()
      setItems(d.items || [])
      setTotal(d.total || 0)
    } finally {
      setLoading(false)
    }
  }, [query, ministry, dbtOnly, offset])

  useEffect(() => {
    const t = setTimeout(() => fetchSchemes(), 200)
    return () => clearTimeout(t)
  }, [fetchSchemes])

  const openDetail = async (slug: string) => {
    const r = await fetch(`/api/schemes/${slug}`)
    if (r.ok) {
      setSelected(await r.json())
    }
  }

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div className="glass p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-bold text-indiaNavy dark:text-slate-100">Central Government Scheme Explorer</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Browse all <strong>649 Central Schemes</strong> &amp; <strong>7,724 Official FAQs</strong> across 51 Ministries
            </p>
          </div>
          <span className="text-xs font-semibold px-3 py-1 rounded-full bg-indiaNavy/10 text-indiaNavy dark:bg-white/10 dark:text-slate-100">
            {total} matching schemes
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-2.5">
          <div className="md:col-span-5 relative">
            <Search className="w-4 h-4 text-slate-400 dark:text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              value={query}
              onChange={(e) => {
                setOffset(0)
                setQuery(e.target.value)
              }}
              placeholder="Search scheme name, benefit, farmer, scholarship, Mudra..."
              className="field py-2 pl-9"
            />
          </div>

          <div className="md:col-span-5 relative">
            <Building2 className="w-4 h-4 text-slate-400 dark:text-slate-500 absolute left-3 top-2.5" />
            <select
              value={ministry}
              onChange={(e) => {
                setOffset(0)
                setMinistry(e.target.value)
              }}
              className="field py-2 pl-9 pr-3 dark:[color-scheme:dark]"
            >
              <option value="">All 51 Central Ministries</option>
              {ministries.map((m) => (
                <option key={m.ministry_code} value={m.ministry_code}>
                  {m.ministry_name} ({m.scheme_count})
                </option>
              ))}
            </select>
          </div>

          <label className="md:col-span-2 flex items-center justify-center gap-2 px-3 py-2 rounded-full border border-slate-300/80 bg-white/70 text-xs font-medium text-slate-700 cursor-pointer transition hover:bg-white dark:border-white/15 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10">
            <Filter className="w-3.5 h-3.5 text-indiaGreen" />
            <input
              type="checkbox"
              checked={dbtOnly}
              onChange={(e) => {
                setOffset(0)
                setDbtOnly(e.target.checked)
              }}
              className="accent-indiaGreen"
            />
            DBT Only
          </label>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-sm text-slate-500 dark:text-slate-400">Loading schemes catalog...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {items.map((s) => (
            <div
              key={s.slug}
              onClick={() => openDetail(s.slug)}
              className="glass-subtle p-4 shadow-sm hover:shadow-lg hover:border-indiaNavy dark:hover:border-indiaSaffron/60 cursor-pointer transition duration-300 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-indiaNavy/10 text-indiaNavy dark:bg-white/10 dark:text-indiaSaffron">
                    {s.ministry_code}
                  </span>
                  <div className="flex items-center gap-1">
                    {s.dbt_scheme && (
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-300 dark:border-emerald-400/30">
                        DBT
                      </span>
                    )}
                    <span className="text-[10px] text-slate-500 dark:text-slate-400">{s.faq_count} FAQs</span>
                  </div>
                </div>
                <h3 className="font-semibold text-sm text-indiaNavy dark:text-slate-100 line-clamp-2">{s.scheme_name}</h3>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 line-clamp-1">{s.ministry}</p>
                                <p className="text-xs text-slate-600 dark:text-slate-300 mt-2 line-clamp-3">{s.brief_description}</p>
              </div>
              <div className="mt-3 pt-2 border-t border-slate-900/10 dark:border-white/10 flex flex-wrap gap-1">
                {s.beneficiary_groups.slice(0, 3).map((bg) => (
                  <span key={bg} className="text-[10px] px-2 py-0.5 rounded-full bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300">
                    {bg}
                  </span>
                ))}
                {s.income_cap_inr && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300">
                    Cap ≤ ₹{(s.income_cap_inr / 100000).toFixed(1)}L
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      <div className="flex items-center justify-between pt-2">
        <span className="text-xs text-slate-500 dark:text-slate-400">
          Showing {total ? offset + 1 : 0}–{Math.min(offset + limit, total)} of {total}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - limit))}
            className="btn-secondary gap-1 px-3 py-1.5 text-xs"
          >
            <ChevronLeft className="w-4 h-4" /> Prev
          </button>
          <button
            type="button"
            disabled={offset + limit >= total}
            onClick={() => setOffset(offset + limit)}
            className="btn-secondary gap-1 px-3 py-1.5 text-xs"
          >
            Next <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Detail Modal */}
      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 dark:bg-slate-950/60 backdrop-blur-sm">
          <div className="w-full max-w-3xl glass max-h-[90vh] flex flex-col overflow-hidden">
            <div className="px-5 py-4 bg-indiaNavy/90 text-white backdrop-blur-md dark:bg-white/5 dark:text-slate-100 border-b border-white/10 flex items-start justify-between gap-3">
              <div>
                <h3 className="font-bold text-base">{selected.scheme.scheme_name}</h3>
                <p className="text-xs text-slate-300 dark:text-slate-400 mt-0.5">
                  {selected.scheme.ministry} ({selected.scheme.ministry_code})
                </p>
              </div>
              <button onClick={() => setSelected(null)} className="p-1.5 rounded-full transition hover:bg-white/10">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 overflow-y-auto space-y-4 text-xs text-slate-700 dark:text-slate-200 leading-relaxed">
              <div className="flex justify-end">
                <a
                  href={selected.scheme.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-primary gap-1.5 px-3 py-1.5 text-xs"
                >
                  Open on myScheme.gov.in <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
              {selected.scheme.benefits && (
                <div>
                  <h4 className="font-bold text-slate-900 dark:text-slate-100 text-sm mb-1">Benefits</h4>
                  <p className="whitespace-pre-line">{selected.scheme.benefits}</p>
                </div>
              )}
              {selected.scheme.eligibility && (
                <div>
                  <h4 className="font-bold text-slate-900 dark:text-slate-100 text-sm mb-1">Eligibility</h4>
                  <p className="whitespace-pre-line">{selected.scheme.eligibility}</p>
                </div>
              )}
              {selected.scheme.exclusions && (
                <div className="p-3 rounded-2xl bg-amber-50 border border-amber-200 dark:bg-amber-500/15 dark:border-amber-400/30">
                  <h4 className="font-bold text-amber-900 dark:text-amber-300 text-sm mb-1">Exclusions</h4>
                                    <p className="whitespace-pre-line text-amber-900 dark:text-amber-200">{selected.scheme.exclusions}</p>
                </div>
              )}
              {selected.scheme.documents_required && (
                <div>
                  <h4 className="font-bold text-slate-900 dark:text-slate-100 text-sm mb-1">Documents Required</h4>
                  <p className="whitespace-pre-line">{selected.scheme.documents_required}</p>
                </div>
              )}
              {selected.faqs.length > 0 && (
                <div className="pt-2 border-t border-slate-900/10 dark:border-white/10">
                  <h4 className="font-bold text-slate-900 dark:text-slate-100 text-sm mb-2">
                    Official FAQs ({selected.faqs.length})
                  </h4>
                  <div className="space-y-2.5">
                    {selected.faqs.slice(0, 15).map((f) => (
                      <div key={f.faq_number} className="p-3 glass-subtle">
                        <p className="font-semibold text-slate-900 dark:text-slate-100">
                          Q{f.faq_number}: {f.question}
                        </p>
                        <p className="mt-1 text-slate-600 dark:text-slate-300 whitespace-pre-line">{f.answer}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
