import React, { useState } from 'react'
import { CheckCircle2, AlertTriangle, HelpCircle, XCircle, FileCheck2, ExternalLink } from 'lucide-react'
import { EligibilityCardData } from '../types'

interface Props {
  card: EligibilityCardData
}

const VERDICT_STYLE: Record<
  EligibilityCardData['verdict'],
  { bg: string; text: string; border: string; label: string; icon: React.ReactNode }
> = {
  ELIGIBLE: {
    bg: 'bg-emerald-50 dark:bg-emerald-500/15',
    text: 'text-emerald-800 dark:text-emerald-200',
    border: 'border-emerald-200 dark:border-emerald-400/30',
    label: 'Likely Eligible',
    icon: <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />,
  },
  PARTIALLY_ELIGIBLE: {
    bg: 'bg-amber-50 dark:bg-amber-500/15',
    text: 'text-amber-800 dark:text-amber-200',
    border: 'border-amber-200 dark:border-amber-400/30',
    label: 'Partially Eligible',
    icon: <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400" />,
  },
  NEEDS_MORE_INFO: {
    bg: 'bg-sky-50 dark:bg-sky-500/15',
    text: 'text-sky-800 dark:text-sky-200',
    border: 'border-sky-200 dark:border-sky-400/30',
    label: 'More Details Needed',
    icon: <HelpCircle className="w-4 h-4 text-sky-600 dark:text-sky-400" />,
  },
  NOT_ELIGIBLE: {
    bg: 'bg-rose-50 dark:bg-rose-500/15',
    text: 'text-rose-800 dark:text-rose-200',
    border: 'border-rose-200 dark:border-rose-400/30',
    label: 'Not Eligible',
    icon: <XCircle className="w-4 h-4 text-rose-600 dark:text-rose-400" />,
  },
}

export const EligibilityCard: React.FC<Props> = ({ card }) => {
  const [checkedDocs, setCheckedDocs] = useState<Record<number, boolean>>({})
  const st = VERDICT_STYLE[card.verdict] || VERDICT_STYLE.NEEDS_MORE_INFO

  const toggleDoc = (idx: number) => {
    setCheckedDocs((prev) => ({ ...prev, [idx]: !prev[idx] }))
  }

  return (
    <div className={`glass-subtle border ${st.border} shadow-md shadow-slate-900/5 overflow-hidden mt-3`}>
      <div className={`px-4 py-3 ${st.bg} flex flex-wrap items-center justify-between gap-2 border-b ${st.border}`}>
        <div>
          <h4 className="font-bold text-sm text-indiaNavy dark:text-slate-100">{card.scheme_name}</h4>
          {card.ministry && <p className="text-xs text-slate-600 dark:text-slate-300 mt-0.5">{card.ministry}</p>}
        </div>
        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${st.border} bg-white/70 dark:bg-slate-900/60 ${st.text}`}>
          {st.icon}
          {st.label}
        </span>
      </div>

      <div className="p-4 space-y-3 text-[13px] leading-relaxed">
        {card.matched_criteria.length > 0 && (
          <div>
            <p className="font-semibold text-emerald-800 dark:text-emerald-300 text-xs uppercase tracking-wide mb-1">Matched Criteria</p>
            <ul className="list-disc pl-4 space-y-1 text-slate-700 dark:text-slate-200">
              {card.matched_criteria.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        )}

        {card.unmet_criteria && card.unmet_criteria.length > 0 && (
          <div>
            <p className="font-semibold text-rose-800 dark:text-rose-300 text-xs uppercase tracking-wide mb-1">Unmet Criteria</p>
            <ul className="list-disc pl-4 space-y-1 text-rose-700 dark:text-rose-300">
              {card.unmet_criteria.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        )}

        {card.exclusion_warnings.length > 0 && (
          <div className="bg-amber-50/70 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-400/30 rounded-2xl p-3">
            <p className="font-semibold text-amber-900 dark:text-amber-200 text-xs uppercase tracking-wide mb-1">Important Exclusions</p>
            <ul className="list-disc pl-4 space-y-1 text-amber-900 dark:text-amber-200 text-xs">
              {card.exclusion_warnings.slice(0, 3).map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        {card.clarifying_questions.length > 0 && (
          <div>
            <p className="font-semibold text-sky-900 dark:text-sky-300 text-xs uppercase tracking-wide mb-1">Please Confirm</p>
            <ul className="list-disc pl-4 space-y-1 text-slate-700 dark:text-slate-200">
              {card.clarifying_questions.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ul>
          </div>
        )}

        {card.documents_required.length > 0 && (
          <div className="border-t border-slate-900/10 dark:border-white/10 pt-3">
            <p className="font-semibold text-slate-800 dark:text-slate-200 text-xs uppercase tracking-wide mb-2 flex items-center gap-1.5">
              <FileCheck2 className="w-4 h-4 text-indiaNavy dark:text-indiaSaffron" />
              Document Checklist (Keep Ready Before Applying)
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-xs">
              {card.documents_required.slice(0, 8).map((doc, idx) => (
                <label
                  key={idx}
                  className="flex items-start gap-2 p-2 rounded-xl border border-slate-900/10 dark:border-white/10 bg-white/40 dark:bg-white/5 hover:bg-white/80 dark:hover:bg-white/10 cursor-pointer transition"
                >
                  <input
                    type="checkbox"
                    checked={Boolean(checkedDocs[idx])}
                    onChange={() => toggleDoc(idx)}
                    className="mt-0.5 accent-indiaGreen"
                  />
                  <span className={checkedDocs[idx] ? 'line-through text-slate-400 dark:text-slate-500' : 'text-slate-700 dark:text-slate-200'}>
                    {doc}
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="pt-2 border-t border-slate-900/10 dark:border-white/10 flex justify-end">
          <a
            href={card.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-primary gap-1.5 px-3.5 py-1.5 text-xs"
          >
            Open Official Scheme Page <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>
    </div>
  )
}
