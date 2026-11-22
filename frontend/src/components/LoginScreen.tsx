import React, { useEffect, useState } from 'react'
import {
  ShieldCheck,
  UserCheck,
  Lock,
  LogIn,
  Eye,
  EyeOff,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  BookOpen,
  FileCheck2,
  Globe2,
} from 'lucide-react'
import { AuthUser, StoredAuth } from '../types'

interface Props {
  onLoginSuccess: (auth: StoredAuth) => void
}

const CivicHeroIllustration: React.FC = () => (
  <div className="relative w-full max-w-md mx-auto py-4 select-none" aria-hidden="true">
    <svg viewBox="0 0 420 260" className="w-full h-auto drop-shadow-xs">
      <defs>
        <linearGradient id="civicBg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#1B365D" stopOpacity="0.06" />
          <stop offset="100%" stopColor="#D96B16" stopOpacity="0.09" />
        </linearGradient>
        <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#E86F1C" />
          <stop offset="50%" stopColor="#1B365D" />
          <stop offset="100%" stopColor="#138808" />
        </linearGradient>
      </defs>

      {/* Soft backdrop */}
      <rect x="16" y="14" width="388" height="232" rx="24" fill="url(#civicBg)" stroke="#E2E8F0" strokeWidth="1" />

      {/* Rotating subtle Ashoka-inspired ring */}
      <g className="animate-slow-spin" style={{ transformOrigin: '210px 130px' }}>
        <circle cx="210" cy="130" r="76" fill="none" stroke="url(#ringGrad)" strokeWidth="1.5" strokeDasharray="6 6" opacity="0.55" />
        <circle cx="210" cy="130" r="54" fill="none" stroke="#1B365D" strokeWidth="1" strokeDasharray="3 5" opacity="0.3" />
      </g>

      {/* Center Emblem */}
      <circle cx="210" cy="130" r="36" fill="#0F2942" />
      <circle cx="210" cy="130" r="29" fill="none" stroke="#F59E0B" strokeWidth="1.5" opacity="0.7" />
      <text x="210" y="126" textAnchor="middle" fill="#FFFFFF" fontSize="14" fontWeight="700" fontFamily="Inter, sans-serif">
        जन
      </text>
      <text x="210" y="142" textAnchor="middle" fill="#FDE68A" fontSize="10" fontWeight="600" fontFamily="Inter, sans-serif">
        SAHAYAK
      </text>

      {/* Floating Citizen Service Nodes */}
      <g className="animate-float-slow">
        <rect x="34" y="38" width="118" height="44" rx="12" fill="#FFFFFF" stroke="#CBD5E1" strokeWidth="1" />
        <circle cx="54" cy="60" r="9" fill="#DCFCE7" />
        <circle cx="54" cy="60" r="4" fill="#15803D" />
        <text x="70" y="57" fill="#0F2942" fontSize="10" fontWeight="700" fontFamily="Inter, sans-serif">Kisan &amp; Rural</text>
        <text x="70" y="70" fill="#64748B" fontSize="8.5" fontFamily="Inter, sans-serif">PM-KISAN &amp; DBT</text>
      </g>

      <g className="animate-float-delayed">
        <rect x="268" y="38" width="122" height="44" rx="12" fill="#FFFFFF" stroke="#CBD5E1" strokeWidth="1" />
        <circle cx="288" cy="60" r="9" fill="#DBEAFE" />
        <circle cx="288" cy="60" r="4" fill="#1D4ED8" />
        <text x="304" y="57" fill="#0F2942" fontSize="10" fontWeight="700" fontFamily="Inter, sans-serif">Education</text>
        <text x="304" y="70" fill="#64748B" fontSize="8.5" fontFamily="Inter, sans-serif">NSP Scholarships</text>
      </g>

      <g className="animate-float-delayed">
        <rect x="34" y="178" width="124" height="44" rx="12" fill="#FFFFFF" stroke="#CBD5E1" strokeWidth="1" />
        <circle cx="54" cy="200" r="9" fill="#FFEDD5" />
        <circle cx="54" cy="200" r="4" fill="#C2410C" />
        <text x="70" y="197" fill="#0F2942" fontSize="10" fontWeight="700" fontFamily="Inter, sans-serif">Artisans &amp; MSME</text>
        <text x="70" y="210" fill="#64748B" fontSize="8.5" fontFamily="Inter, sans-serif">Vishwakarma &amp; Mudra</text>
      </g>

      <g className="animate-float-slow">
        <rect x="262" y="178" width="128" height="44" rx="12" fill="#FFFFFF" stroke="#CBD5E1" strokeWidth="1" />
        <circle cx="282" cy="200" r="9" fill="#FEE2E2" />
        <circle cx="282" cy="200" r="4" fill="#B91C1C" />
        <text x="298" y="197" fill="#0F2942" fontSize="10" fontWeight="700" fontFamily="Inter, sans-serif">CPGRAMS Desk</text>
        <text x="298" y="210" fill="#64748B" fontSize="8.5" fontFamily="Inter, sans-serif">File &amp; Track Status</text>
      </g>
    </svg>
  </div>
)

export const LoginScreen: React.FC<Props> = ({ onLoginSuccess }) => {
  const [loginMode, setLoginMode] = useState<'citizen' | 'admin'>('citizen')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showDemoHelper, setShowDemoHelper] = useState(false)
  const [personas, setPersonas] = useState<AuthUser[]>([])

  useEffect(() => {
    fetch('/api/auth/personas')
      .then((r) => (r.ok ? r.json() : { personas: [] }))
      .then((d) => setPersonas(d.personas || []))
      .catch(() => {})
  }, [])

  const applyDemoPersona = (p: AuthUser) => {
    setLoginMode(p.role === 'admin' ? 'admin' : 'citizen')
    setUsername(p.username)
    setPassword(p.role === 'admin' ? 'admin123' : 'citizen123')
    setError(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      })
      const data = await resp.json()
      if (!resp.ok) {
        throw new Error(data.detail || 'Invalid username or password')
      }
      onLoginSuccess({ token: data.access_token, user: data.user })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to sign in. Please check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#F7F6F2] flex flex-col">
      <div className="h-1.5 tricolor-bar w-full" />

      {/* Top Civic Strip */}
      <header className="bg-white border-b border-slate-200/80">
        <div className="max-w-6xl mx-auto px-5 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indiaNavy text-white flex items-center justify-center font-bold text-sm shadow-xs border-b-2 border-indiaSaffron">
              जन
            </div>
            <div>
              <h1 className="text-lg font-bold text-indiaNavy leading-tight tracking-tight">JanSahayak</h1>
              <p className="text-[11px] text-slate-500">Citizen Welfare Schemes &amp; Public Grievance Portal</p>
            </div>
          </div>
          <div className="hidden sm:flex items-center gap-4 text-xs text-slate-600">
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-indiaGreen" /> Verified Official Schemes
            </span>
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-indiaNavy" /> Privacy Protected (DPDP Act)
            </span>
          </div>
        </div>
      </header>

      {/* Main Split Content */}
      <main className="flex-1 flex items-center justify-center px-4 py-8 sm:py-12">
        <div className="w-full max-w-6xl grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          {/* Left: Authentic Public Service Hero + Animated Illustration */}
          <div className="lg:col-span-7 space-y-5">
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-indiaSaffron">
                Digital Public Service Assistant
              </p>
              <h2 className="text-3xl sm:text-4xl font-bold text-indiaNavy leading-tight tracking-tight">
                Find Government Schemes You Qualify For — In Your Own Language.
              </h2>
              <p className="text-sm sm:text-base text-slate-600 leading-relaxed max-w-xl">
                Check eligibility across <strong>649 Central Government schemes</strong>, prepare the right
                documents before visiting a CSC, and draft or track official public grievances without middlemen.
              </p>
            </div>

            <CivicHeroIllustration />

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
              <div className="bg-white border border-slate-200/90 rounded-xl p-3.5 flex items-start gap-2.5">
                <BookOpen className="w-4 h-4 text-indiaNavy mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs font-bold text-slate-900">649 Central Schemes</p>
                  <p className="text-[11px] text-slate-500">Official guidelines &amp; 7,724 FAQs across 51 Ministries</p>
                </div>
              </div>
              <div className="bg-white border border-slate-200/90 rounded-xl p-3.5 flex items-start gap-2.5">
                <Globe2 className="w-4 h-4 text-indiaGreen mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs font-bold text-slate-900">6 Indian Languages</p>
                  <p className="text-[11px] text-slate-500">Type or speak in Hindi, Hinglish, Marathi, Bengali, Tamil &amp; Telugu</p>
                </div>
              </div>
              <div className="bg-white border border-slate-200/90 rounded-xl p-3.5 flex items-start gap-2.5">
                <FileCheck2 className="w-4 h-4 text-indiaSaffron mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs font-bold text-slate-900">CPGRAMS Support</p>
                  <p className="text-[11px] text-slate-500">Draft complaints, confirm before sending &amp; track ticket status</p>
                </div>
              </div>
            </div>
          </div>

          {/* Right: Dignified Sign-In Card */}
          <div className="lg:col-span-5">
            <div className="bg-white border border-slate-200 rounded-2xl shadow-md p-6 sm:p-7 space-y-5">
              <div>
                <h3 className="text-xl font-bold text-indiaNavy">Sign In to Continue</h3>
                <p className="text-xs text-slate-500 mt-1">
                  Enter your portal credentials to access your personalised citizen profile and services.
                </p>
              </div>

              {/* Citizen vs Admin Role Switcher */}
              <div className="grid grid-cols-2 gap-1.5 p-1 bg-slate-100 rounded-xl text-xs font-semibold">
                <button
                  type="button"
                  onClick={() => {
                    setLoginMode('citizen')
                    setError(null)
                  }}
                  className={`py-2 rounded-lg transition ${
                    loginMode === 'citizen' ? 'bg-white text-indiaNavy shadow-xs' : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  Citizen Login
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setLoginMode('admin')
                    setError(null)
                  }}
                  className={`py-2 rounded-lg transition ${
                    loginMode === 'admin' ? 'bg-white text-indiaNavy shadow-xs' : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  Administrator
                </button>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    {loginMode === 'admin' ? 'Administrator ID' : 'Citizen Username / ID'}
                  </label>
                  <div className="relative">
                    <UserCheck className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                    <input
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      required
                      autoComplete="username"
                      className="w-full pl-9 pr-3 py-2.5 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 placeholder-slate-400 text-sm focus:bg-white focus:border-indiaNavy focus:outline-none"
                      placeholder={loginMode === 'admin' ? 'Enter admin ID' : 'Enter your username'}
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">Password</label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      autoComplete="current-password"
                      className="w-full pl-9 pr-10 py-2.5 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 placeholder-slate-400 text-sm focus:bg-white focus:border-indiaNavy focus:outline-none"
                      placeholder="Enter your password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((prev) => !prev)}
                      className="absolute right-2.5 top-2 p-1 rounded-lg text-slate-500 hover:text-indiaNavy hover:bg-slate-200/60 transition"
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      title={showPassword ? 'Hide password' : 'Show password'}
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {error && (
                  <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs">
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-indiaNavy hover:bg-slate-800 disabled:opacity-50 text-white font-semibold text-sm shadow-xs transition"
                >
                  <LogIn className="w-4 h-4" />
                  {loading ? 'Signing in...' : 'Sign In'}
                </button>
              </form>

              <p className="text-[11px] text-slate-500 leading-relaxed pt-1">
                Your personal identifiers (such as Aadhaar, PAN, or mobile number) are masked automatically and you can erase your session data anytime.
              </p>

              {/* Discreet, Collapsed-by-Default Demo/Evaluator Access Drawer */}
              <div className="border-t border-slate-100 pt-3">
                <button
                  type="button"
                  onClick={() => setShowDemoHelper((v) => !v)}
                  className="w-full flex items-center justify-between text-[11px] font-medium text-slate-500 hover:text-indiaNavy transition"
                >
                  <span>Need a sandbox / evaluator demo account?</span>
                  {showDemoHelper ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                </button>
                {showDemoHelper && (
                  <div className="mt-2.5 space-y-1.5 bg-slate-50 border border-slate-200 rounded-xl p-2.5">
                    {personas.map((p) => (
                      <button
                        key={p.user_id}
                        type="button"
                        onClick={() => applyDemoPersona(p)}
                        className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-white hover:shadow-2xs text-left text-xs transition"
                      >
                        <div>
                          <span className="font-semibold text-slate-800">{p.display_name}</span>
                          <span className="text-slate-400 ml-1.5 text-[11px]">({p.title})</span>
                        </div>
                        <span
                          className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                            p.role === 'admin' ? 'bg-amber-100 text-amber-900' : 'bg-emerald-100 text-emerald-800'
                          }`}
                        >
                          {p.username}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>

      <footer className="border-t border-slate-200/80 bg-white py-3 text-center text-[11px] text-slate-500">
        JanSahayak Citizen Portal &bull; Aligned with Official myScheme.gov.in &amp; CPGRAMS (pgportal.gov.in) Guidelines
      </footer>
    </div>
  )
}
