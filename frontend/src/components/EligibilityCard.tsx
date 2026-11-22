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
    bg: 'bg-emerald-50',
    text: 'text-emerald-800',
    border: 'border-emerald-200',
    label: 'Likely Eligible',
    icon: <CheckCircle2 className="w-4 h-4 text-emerald-600" />,
  },
  PARTIALLY_ELIGIBLE: {
    bg: 'bg-amber-50',
    text: 'text-amber-800',
    border: 'border-amber-200',
    label: 'Partially Eligible',
    icon: <AlertTriangle className="w-4 h-4 text-amber-600" />,
  },
  NEEDS_MORE_INFO: {
    bg: 'bg-sky-50',
    text: 'text-sky-800',
    border: 'border-sky-200',
    label: 'More Details Needed',
    icon: <HelpCircle className="w-4 h-4 text-sky-600" />,
  },
  NOT_ELIGIBLE: {
    bg: 'bg-rose-50',
    text: 'text-rose-800',
    border: 'border-rose-200',
    label: 'Not Eligible',
    icon: <XCircle className="w-4 h-4 text-rose-600" />,
  },
}

export const EligibilityCard: React.FC<Props> = ({ card }) => {
  const [checkedDocs, setCheckedDocs] = useState<Record<number, boolean>>({})
  const st = VERDICT_STYLE[card.verdict] || VERDICT_STYLE.NEEDS_MORE_INFO

  const toggleDoc = (idx: number) => {
    setCheckedDocs((prev) => ({ ...prev, [idx]: !prev[idx] }))
  }

  return (
    <div className={`rounded-xl border ${st.border} bg-white shadow-2xs overflow-hidden mt-3`}>
      <div className={`px-4 py-3 ${st.bg} flex flex-wrap items-center justify-between gap-2 border-b ${st.border}`}>
        <div>
          <h4 className="font-bold text-sm text-slate-900">{card.scheme_name}</h4>
          {card.ministry && <p className="text-xs text-slate-600 mt-0.5">{card.ministry}</p>}
        </div>
        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${st.border} bg-white ${st.text}`}>
          {st.icon}
          {st.label}
        </span>
      </div>

      <div className="p-4 space-y-3 text-[13px] leading-relaxed">
        {card.matched_criteria.length > 0 && (
          <div>
            <p className="font-semibold text-emerald-800 text-xs uppercase tracking-wide mb-1">Matched Criteria</p>
            <ul className="list-disc pl-4 space-y-1 text-slate-700">
              {card.matched_criteria.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        )}

        {card.unmet_criteria && card.unmet_criteria.length > 0 && (
          <div>
            <p className="font-semibold text-rose-800 text-xs uppercase tracking-wide mb-1">Unmet Criteria</p>
            <ul className="list-disc pl-4 space-y-1 text-rose-700">
              {card.unmet_criteria.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        )}

        {card.exclusion_warnings.length > 0 && (
          <div className="bg-amber-50/70 border border-amber-200 rounded-lg p-3">
            <p className="font-semibold text-amber-900 text-xs uppercase tracking-wide mb-1">Important Exclusions</p>
            <ul className="list-disc pl-4 space-y-1 text-amber-900 text-xs">
              {card.exclusion_warnings.slice(0, 3).map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        {card.clarifying_questions.length > 0 && (
          <div>
            <p className="font-semibold text-sky-900 text-xs uppercase tracking-wide mb-1">Please Confirm</p>
            <ul className="list-disc pl-4 space-y-1 text-slate-700">
              {card.clarifying_questions.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ul>
          </div>
        )}

        {card.documents_required.length > 0 && (
          <div className="border-t border-slate-100 pt-3">
            <p className="font-semibold text-slate-800 text-xs uppercase tracking-wide mb-2 flex items-center gap-1.5">
              <FileCheck2 className="w-4 h-4 text-indiaNavy" />
              Document Checklist (Keep Ready Before Applying)
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-xs">
              {card.documents_required.slice(0, 8).map((doc, idx) => (
                <label
                  key={idx}
                  className="flex items-start gap-2 p-2 rounded-lg border border-slate-100 hover:bg-slate-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={Boolean(checkedDocs[idx])}
                    onChange={() => toggleDoc(idx)}
                    className="mt-0.5 accent-indiaGreen"
                  />
                  <span className={checkedDocs[idx] ? 'line-through text-slate-400' : 'text-slate-700'}>
                    {doc}
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="pt-2 border-t border-slate-100 flex justify-end">
          <a
            href={card.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indiaNavy hover:bg-slate-800 text-white text-xs font-semibold transition"
          >
            Open Official Scheme Page <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>
    </div>
  )
}
