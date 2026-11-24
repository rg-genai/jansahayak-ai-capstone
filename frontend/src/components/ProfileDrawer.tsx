import React, { useState, useEffect } from 'react'
import { User, Trash2, Save, ShieldCheck, X } from 'lucide-react'
import { CitizenProfile } from '../types'

interface Props {
  open: boolean
  onClose: () => void
  sessionId: string
  profile: CitizenProfile
  onSaveProfile: (profile: CitizenProfile) => Promise<void>
  onDeleteAllData: () => Promise<void>
}

export const ProfileDrawer: React.FC<Props> = ({
  open,
  onClose,
  sessionId,
  profile,
  onSaveProfile,
  onDeleteAllData,
}) => {
  const [form, setForm] = useState<CitizenProfile>(profile)
  const [saving, setSaving] = useState(false)
  const [erasing, setErasing] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)

  useEffect(() => {
    setForm(profile)
  }, [profile])

  if (!open) return null

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setFeedback(null)
    try {
      await onSaveProfile(form)
      setFeedback('Citizen profile saved for personalized eligibility checks.')
    } finally {
      setSaving(false)
    }
  }

  const handleErase = async () => {
    setErasing(true)
    setFeedback(null)
    try {
      await onDeleteAllData()
      setForm({})
      setFeedback('DPDP Act 2023: All session history & profile data permanently erased.')
    } finally {
      setErasing(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-xs">
      <div className="glass rounded-none w-full max-w-md h-full flex flex-col overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-900/10 dark:border-white/10 text-indiaNavy dark:text-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <User className="w-5 h-5 text-indiaSaffron" />
            <div>
              <h3 className="font-semibold text-base">Citizen Profile</h3>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">Session: {sessionId}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-full text-slate-500 hover:bg-slate-900/5 hover:text-indiaNavy dark:text-slate-400 dark:hover:bg-white/10 dark:hover:text-slate-100 transition" aria-label="Close drawer">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSave} className="flex-1 overflow-y-auto p-5 space-y-3.5 text-sm">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Fields are automatically extracted from your chat turns or can be edited here for sharper eligibility matching.
          </p>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-200 mb-1">Age (Years)</label>
              <input
                type="number"
                min={0}
                max={120}
                value={form.age ?? ''}
                onChange={(e) => setForm({ ...form, age: e.target.value ? Number(e.target.value) : null })}
                className="field"
                placeholder="e.g. 46"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-200 mb-1">Gender</label>
              <select
                value={form.gender ?? ''}
                onChange={(e) => setForm({ ...form, gender: e.target.value || null })}
                className="field dark:[color-scheme:dark]"
              >
                <option value="">Not specified</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 dark:text-slate-200 mb-1">State / UT</label>
            <input
              type="text"
              value={form.state ?? ''}
              onChange={(e) => setForm({ ...form, state: e.target.value || null })}
              className="field"
              placeholder="e.g. Uttar Pradesh, Maharashtra, Tamil Nadu"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-200 mb-1">Annual Income (₹)</label>
              <input
                type="number"
                min={0}
                value={form.annual_income_inr ?? ''}
                onChange={(e) =>
                  setForm({ ...form, annual_income_inr: e.target.value ? Number(e.target.value) : null })
                }
                className="field"
                placeholder="e.g. 180000"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-200 mb-1">Social Category</label>
              <select
                value={form.social_category ?? ''}
                onChange={(e) => setForm({ ...form, social_category: e.target.value || null })}
                className="field dark:[color-scheme:dark]"
              >
                <option value="">Not specified</option>
                <option value="General">General</option>
                <option value="OBC">OBC</option>
                <option value="SC">SC</option>
                <option value="ST">ST</option>
                <option value="EWS">EWS</option>
                <option value="Minority">Minority</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-200 mb-1">Occupation</label>
              <input
                type="text"
                value={form.occupation ?? ''}
                onChange={(e) => setForm({ ...form, occupation: e.target.value || null })}
                className="field"
                placeholder="Farmer / Student / Artisan"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-200 mb-1">Education</label>
              <input
                type="text"
                value={form.education_level ?? ''}
                onChange={(e) => setForm({ ...form, education_level: e.target.value || null })}
                className="field"
                placeholder="B.Tech / 12th / Graduate"
              />
            </div>
          </div>

          <div className="flex items-center gap-5 pt-1">
            <label className="inline-flex items-center gap-2 text-xs text-slate-700 dark:text-slate-200 cursor-pointer">
              <input
                type="checkbox"
                checked={Boolean(form.is_bpl)}
                onChange={(e) => setForm({ ...form, is_bpl: e.target.checked })}
                className="accent-indiaNavy dark:accent-indiaSaffron"
              />
              BPL Cardholder
            </label>
            <label className="inline-flex items-center gap-2 text-xs text-slate-700 dark:text-slate-200 cursor-pointer">
              <input
                type="checkbox"
                checked={Boolean(form.is_pwd)}
                onChange={(e) => setForm({ ...form, is_pwd: e.target.checked })}
                className="accent-indiaNavy dark:accent-indiaSaffron"
              />
              Person with Disability (PwD)
            </label>
          </div>

          {feedback && (
            <div className="p-2.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs dark:bg-emerald-500/15 dark:border-emerald-500/30 dark:text-emerald-200">
              {feedback}
            </div>
          )}

          <button
            type="submit"
            disabled={saving}
            className="btn-primary w-full"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : 'Save Citizen Profile'}
          </button>

          <div className="mt-6 pt-5 border-t border-slate-900/10 dark:border-white/10">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-800 dark:text-slate-200 mb-1.5">
              <ShieldCheck className="w-4 h-4 text-indiaGreen dark:text-emerald-400" />
              DPDP Act 2023 — Privacy & Right to Erasure
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">
              Aadhaar, PAN, phone, and IFSC numbers are masked automatically before LLM processing.
              You can permanently erase your session profile and chat messages anytime.
            </p>
            <button
              type="button"
              onClick={handleErase}
              disabled={erasing}
              className="w-full flex items-center justify-center gap-2 rounded-full border border-rose-300 bg-rose-50 hover:bg-rose-100 text-rose-700 py-2 px-4 font-medium text-xs transition dark:border-rose-500/40 dark:bg-rose-500/15 dark:text-rose-300 dark:hover:bg-rose-500/25 disabled:opacity-50"
            >
              <Trash2 className="w-4 h-4" />
              {erasing ? 'Erasing Data...' : 'Delete My Data (DPDP Right to Erasure)'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
