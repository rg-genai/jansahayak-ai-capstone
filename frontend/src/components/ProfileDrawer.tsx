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
      <div className="w-full max-w-md bg-white h-full shadow-2xl flex flex-col overflow-hidden">
        <div className="px-5 py-4 bg-indiaNavy text-white flex items-center justify-between">
          <div className="flex items-center gap-2">
            <User className="w-5 h-5 text-indiaSaffron" />
            <div>
              <h3 className="font-semibold text-base">Citizen Profile</h3>
              <p className="text-[11px] text-slate-300">Session: {sessionId}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-white/10" aria-label="Close drawer">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSave} className="flex-1 overflow-y-auto p-5 space-y-3.5 text-sm">
          <p className="text-xs text-slate-500">
            Fields are automatically extracted from your chat turns or can be edited here for sharper eligibility matching.
          </p>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Age (Years)</label>
              <input
                type="number"
                min={0}
                max={120}
                value={form.age ?? ''}
                onChange={(e) => setForm({ ...form, age: e.target.value ? Number(e.target.value) : null })}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indiaNavy focus:outline-none"
                placeholder="e.g. 46"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Gender</label>
              <select
                value={form.gender ?? ''}
                onChange={(e) => setForm({ ...form, gender: e.target.value || null })}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indiaNavy focus:outline-none"
              >
                <option value="">Not specified</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">State / UT</label>
            <input
              type="text"
              value={form.state ?? ''}
              onChange={(e) => setForm({ ...form, state: e.target.value || null })}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="e.g. Uttar Pradesh, Maharashtra, Tamil Nadu"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Annual Income (₹)</label>
              <input
                type="number"
                min={0}
                value={form.annual_income_inr ?? ''}
                onChange={(e) =>
                  setForm({ ...form, annual_income_inr: e.target.value ? Number(e.target.value) : null })
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                placeholder="e.g. 180000"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Social Category</label>
              <select
                value={form.social_category ?? ''}
                onChange={(e) => setForm({ ...form, social_category: e.target.value || null })}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
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
              <label className="block text-xs font-medium text-slate-700 mb-1">Occupation</label>
              <input
                type="text"
                value={form.occupation ?? ''}
                onChange={(e) => setForm({ ...form, occupation: e.target.value || null })}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                placeholder="Farmer / Student / Artisan"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Education</label>
              <input
                type="text"
                value={form.education_level ?? ''}
                onChange={(e) => setForm({ ...form, education_level: e.target.value || null })}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                placeholder="B.Tech / 12th / Graduate"
              />
            </div>
          </div>

          <div className="flex items-center gap-5 pt-1">
            <label className="inline-flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
              <input
                type="checkbox"
                checked={Boolean(form.is_bpl)}
                onChange={(e) => setForm({ ...form, is_bpl: e.target.checked })}
                className="accent-indiaNavy"
              />
              BPL Cardholder
            </label>
            <label className="inline-flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
              <input
                type="checkbox"
                checked={Boolean(form.is_pwd)}
                onChange={(e) => setForm({ ...form, is_pwd: e.target.checked })}
                className="accent-indiaNavy"
              />
              Person with Disability (PwD)
            </label>
          </div>

          {feedback && (
            <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs">
              {feedback}
            </div>
          )}

          <button
            type="submit"
            disabled={saving}
            className="w-full flex items-center justify-center gap-2 bg-indiaNavy hover:bg-slate-800 text-white py-2.5 px-4 rounded-lg font-medium text-sm transition"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : 'Save Citizen Profile'}
          </button>

          <div className="mt-6 pt-5 border-t border-slate-200">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-800 mb-1.5">
              <ShieldCheck className="w-4 h-4 text-indiaGreen" />
              DPDP Act 2023 — Privacy & Right to Erasure
            </div>
            <p className="text-xs text-slate-500 mb-3">
              Aadhaar, PAN, phone, and IFSC numbers are masked automatically before LLM processing.
              You can permanently erase your session profile and chat messages anytime.
            </p>
            <button
              type="button"
              onClick={handleErase}
              disabled={erasing}
              className="w-full flex items-center justify-center gap-2 border border-rose-300 bg-rose-50 hover:bg-rose-100 text-rose-700 py-2 px-4 rounded-lg font-medium text-xs transition"
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
