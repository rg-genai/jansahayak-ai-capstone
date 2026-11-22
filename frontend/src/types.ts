export interface CitizenProfile {
  age?: number | null
  gender?: string | null
  state?: string | null
  annual_income_inr?: number | null
  social_category?: string | null
  occupation?: string | null
  is_bpl?: boolean | null
  is_pwd?: boolean | null
  education_level?: string | null
  preferred_language?: string
}

export interface AuthUser {
  user_id: string
  username: string
  display_name: string
  title: string
  role: 'admin' | 'citizen'
  session_id: string
  preferred_language: string
  description: string
  default_profile: CitizenProfile
  permissions: string[]
}

export interface StoredAuth {
  token: string
  user: AuthUser
}

export interface CitationItem {
  index: number
  citation_id?: string
  scheme_slug?: string
  scheme_name: string
  ministry?: string
  section?: string
  faq_numbers?: number[]
  source_url: string
  source_type?: string
  scores?: {
    bm25?: number
    dense?: number
    rrf?: number
    rerank?: number
  }
}

export interface EligibilityCardData {
  scheme_slug: string
  scheme_name: string
  ministry?: string
  verdict: 'ELIGIBLE' | 'PARTIALLY_ELIGIBLE' | 'NOT_ELIGIBLE' | 'NEEDS_MORE_INFO'
  matched_criteria: string[]
  unmet_criteria?: string[]
  exclusion_warnings: string[]
  missing_fields: string[]
  clarifying_questions: string[]
  documents_required: string[]
  source_url: string
}

export interface GrievanceDraft {
  draft_id: string
  scheme_slug?: string
  scheme_name: string
  ministry_code: string
  ministry_name: string
  subject: string
  grievance_text: string
  char_count: number
  within_cpgrams_limit: boolean
  requires_user_confirmation: boolean
  portal_handoff_url: string
}

export interface AssistedHandoffPacket {
  portal_url: string
  ministry: string
  ministry_code: string
  subject: string
  body: string
  char_count: number
  registration_number?: string | null
  next_steps: string[]
}

export interface GrievanceReceipt {
  mode: string
  registration_number: string
  status: string
  ministry_code: string
  ministry_name: string
  submitted_at: string
  expected_sla_days: number
  fallback_used?: boolean
  fallback_reason?: string
  assisted_handoff_packet: AssistedHandoffPacket
}

export interface EmailNotification {
  id?: number
  registration_number: string
  draft_id?: string
  recipient_email: string
  applicant_name?: string
  subject: string
  body_text: string
  body_html: string
  delivery_status: string
  delivery_detail: string
  sent_at: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: CitationItem[]
  eligibility_cards?: EligibilityCardData[]
  grievance_draft?: GrievanceDraft | null
  grievance_receipt?: GrievanceReceipt | null
  trace_id?: string
  cache_hit?: string
  latency_ms?: number
  guardrail_flags?: string[]
  created_at: string
}

export interface SchemeSummary {
  slug: string
  scheme_name: string
  short_title: string
  level: string
  ministry: string
  ministry_code: string
  categories: string
  benefit_type: string
  dbt_scheme: boolean
  application_mode: string
  age_min: number | null
  age_max: number | null
  income_cap_inr: number | null
  social_categories: string[]
  beneficiary_groups: string[]
  brief_description: string
  source_url: string
  faq_count: number
}

export interface TraceSpan {
  span_id: string
  name: string
  type: 'GUARDRAIL' | 'LLM' | 'RETRIEVAL' | 'TOOL' | string
  start_offset_ms: number
  duration_ms: number
  status: string
  input?: unknown
  output?: unknown
  tokens?: {
    prompt: number
    completion: number
    total: number
  }
  error?: string | null
}

export interface TraceRecord {
  trace_id: string
  session_id: string
  user_id?: string
  user_role?: string
  timestamp: string
  user_query_masked: string
  final_answer?: string
  detected_lang: string
  cache_hit: string
  model_name?: string
  planner: Record<string, unknown>
  retrieved_chunks: CitationItem[]
  tool_calls: Array<Record<string, unknown>>
  critic: Record<string, unknown>
  guardrail_flags: string[]
  spans?: TraceSpan[]
  prompt_tokens: number
  completion_tokens: number
  total_latency_ms: number
  step_latencies: Record<string, number>
  status: string
  error_message?: string | null
}

export const LANGUAGE_OPTIONS = [
  { code: 'en', speech: 'en-IN', label: 'English (IN)' },
  { code: 'hi', speech: 'hi-IN', label: 'हिन्दी (Hindi)' },
  { code: 'mr', speech: 'mr-IN', label: 'मराठी (Marathi)' },
  { code: 'bn', speech: 'bn-IN', label: 'বাংলা (Bengali)' },
  { code: 'ta', speech: 'ta-IN', label: 'தமிழ் (Tamil)' },
  { code: 'te', speech: 'te-IN', label: 'తెలుగు (Telugu)' },
] as const
