import React, { useState, useEffect } from 'react'
import { BarChart3, ShieldCheck, Wrench, Sparkles, RefreshCw, Download, FileJson, FileText } from 'lucide-react'
import { apiFetch, downloadAuthenticatedFile } from '../api'
import { TraceRecord } from '../types'

interface EvalSummaryResponse {
  available_reports: number
  total_expected: number
  reports: {
    retrieval_ablation?: {
      eval_trace_id?: string
      num_queries: number
      configs: Array<{
        id: string
        name: string
        recall_at_3: number
        recall_at_5: number
        recall_at_10: number
        mrr_at_10: number
        ndcg_at_5: number
        avg_latency_ms: number
      }>
    } | null
    prompt_comparison?: {
      eval_trace_id?: string
      num_queries: number
      strategies: Array<{
        id: string
        name: string
        answer_accuracy: number
        citation_adherence: number
        hallucination_rate: number
        avg_latency_s: number
        avg_tokens: number
      }>
    } | null
    agent_reliability?: {
      eval_trace_id?: string
      num_scenarios: number
      metrics: {
        tool_selection_accuracy: number
        json_repair_recovery_rate: number
        graceful_fallback_rate: number
        hitl_enforcement_rate: number
      }
    } | null
    red_team_report?: {
      eval_trace_id?: string
      num_tests: number
      overall_pass_rate: number
      pii_masking_rate: number
      injection_block_rate: number
      failure_taxonomy: Array<{ code: string; category: string; count: number; mitigation: string }>
    } | null
  }
}

export const EvalDashboard: React.FC = () => {
  const [data, setData] = useState<EvalSummaryResponse | null>(null)
  const [recentTraces, setRecentTraces] = useState<TraceRecord[]>([])
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [evRes, trRes] = await Promise.all([
        apiFetch('/api/evals/summary'),
        apiFetch('/api/traces?limit=12&hide_erased=true'),
      ])
      if (evRes.ok) setData(await evRes.json())
      if (trRes.ok) {
        const td = await trRes.json()
        setRecentTraces(td.items || [])
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const retrieval = data?.reports?.retrieval_ablation
  const prompts = data?.reports?.prompt_comparison
  const agent = data?.reports?.agent_reliability
  const redteam = data?.reports?.red_team_report

  const renderExportButtons = (reportKey: string, traceId?: string) => (
    <div className="flex items-center gap-1.5">
      {traceId && (
        <span className="px-2 py-0.5 rounded bg-slate-100 font-mono text-[10px] font-semibold text-indiaNavy">
          {traceId}
        </span>
      )}
      <button
        type="button"
        onClick={() => downloadAuthenticatedFile(`/api/evals/export/${reportKey}?format=json`, `${reportKey}.json`)}
        className="inline-flex items-center gap-1 px-2 py-1 rounded border border-slate-300 hover:bg-slate-50 text-[10px] font-medium"
      >
        <FileJson className="w-3 h-3 text-indiaNavy" /> JSON
      </button>
      <button
        type="button"
        onClick={() => downloadAuthenticatedFile(`/api/evals/export/${reportKey}?format=md`, `${reportKey}.md`)}
        className="inline-flex items-center gap-1 px-2 py-1 rounded border border-slate-300 hover:bg-slate-50 text-[10px] font-medium"
      >
        <FileText className="w-3 h-3 text-emerald-700" /> MD
      </button>
    </div>
  )

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-indiaNavy" />
            Track B Quantitative Benchmarks &amp; Downloadable Debug Traces
          </h3>
          <p className="text-xs text-slate-500">
            Real evaluation outputs on fixed `Qwen/Qwen3-8B` + `bge-small-en-v1.5`, with one-click JSON/Markdown exports for debugging.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-xs font-medium"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Reload ({data?.available_reports ?? 0}/{data?.total_expected ?? 4})
        </button>
      </div>

      {/* 1. Retrieval Ablation R1-R4 */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="font-bold text-sm text-slate-900">
            1. Retrieval Ablation (R1 BM25 vs R2 Dense vs R3 Hybrid RRF vs R4 Hybrid + Reranker)
          </h4>
          {retrieval && renderExportButtons('retrieval_ablation', retrieval.eval_trace_id)}
        </div>
        {!retrieval ? (
          <p className="text-xs text-slate-400">Run `python eval/run_all_evals.py` to populate retrieval ablation metrics.</p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-center">
            <div className="lg:col-span-6 space-y-2.5">
              {retrieval.configs.map((c) => (
                <div key={c.id} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="font-semibold text-slate-800">{c.id}: {c.name}</span>
                    <span className="font-mono text-indiaNavy">
                      R@5: {(c.recall_at_5 * 100).toFixed(1)}% | MRR@10: {c.mrr_at_10.toFixed(3)}
                    </span>
                  </div>
                  <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${c.id === 'R4' ? 'bg-indiaGreen' : 'bg-indiaNavy/80'}`}
                      style={{ width: `${Math.min(100, c.recall_at_5 * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <div className="lg:col-span-6 overflow-x-auto">
              <table className="w-full text-xs border border-slate-200 rounded-lg">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="p-2 text-left">Config</th>
                    <th className="p-2 text-right">R@3</th>
                    <th className="p-2 text-right">R@5</th>
                    <th className="p-2 text-right">R@10</th>
                    <th className="p-2 text-right">MRR@10</th>
                    <th className="p-2 text-right">NDCG@5</th>
                    <th className="p-2 text-right">Latency</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono">
                  {retrieval.configs.map((c) => (
                    <tr key={c.id} className={c.id === 'R4' ? 'bg-emerald-50/50 font-semibold' : ''}>
                      <td className="p-2 font-sans">{c.id}</td>
                      <td className="p-2 text-right">{(c.recall_at_3 * 100).toFixed(1)}%</td>
                      <td className="p-2 text-right">{(c.recall_at_5 * 100).toFixed(1)}%</td>
                      <td className="p-2 text-right">{(c.recall_at_10 * 100).toFixed(1)}%</td>
                      <td className="p-2 text-right">{c.mrr_at_10.toFixed(3)}</td>
                      <td className="p-2 text-right">{c.ndcg_at_5.toFixed(3)}</td>
                      <td className="p-2 text-right">{c.avg_latency_ms.toFixed(0)}ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* 2. Prompting Comparison P1-P3 */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="font-bold text-sm text-slate-900 flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-indiaSaffron" />
            2. Prompting Strategy Comparison (P1 Zero-Shot vs P2 Few-Shot vs P3 Planner-Critic)
          </h4>
          {prompts && renderExportButtons('prompt_comparison', prompts.eval_trace_id)}
        </div>
        {!prompts ? (
          <p className="text-xs text-slate-400">Prompt comparison report not yet generated.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs border border-slate-200 rounded-lg">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="p-2.5 text-left">Strategy</th>
                  <th className="p-2.5 text-right">Answer Accuracy</th>
                  <th className="p-2.5 text-right">Citation Adherence</th>
                  <th className="p-2.5 text-right">Hallucination Rate</th>
                  <th className="p-2.5 text-right">Avg Latency</th>
                  <th className="p-2.5 text-right">Avg Tokens</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {prompts.strategies.map((s) => (
                  <tr key={s.id} className={s.id === 'P3' ? 'bg-emerald-50/50 font-semibold' : ''}>
                    <td className="p-2.5 font-sans">{s.id}: {s.name}</td>
                    <td className="p-2.5 text-right">{(s.answer_accuracy * 100).toFixed(1)}%</td>
                    <td className="p-2.5 text-right">{(s.citation_adherence * 100).toFixed(1)}%</td>
                    <td className="p-2.5 text-right">{(s.hallucination_rate * 100).toFixed(1)}%</td>
                    <td className="p-2.5 text-right">{s.avg_latency_s.toFixed(2)}s</td>
                    <td className="p-2.5 text-right">{Math.round(s.avg_tokens)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 3 & 4. Agent Reliability & Red-Team Safety */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="font-bold text-sm text-slate-900 flex items-center gap-1.5">
              <Wrench className="w-4 h-4 text-indiaNavy" />
              3. Agent Reliability ({agent?.num_scenarios ?? 0})
            </h4>
            {agent && renderExportButtons('agent_reliability', agent.eval_trace_id)}
          </div>
          {!agent ? (
            <p className="text-xs text-slate-400">Agent reliability report not yet generated.</p>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <p className="text-[11px] text-slate-500">Tool Selection Accuracy</p>
                <p className="text-xl font-bold text-indiaNavy">{(agent.metrics.tool_selection_accuracy * 100).toFixed(1)}%</p>
              </div>
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <p className="text-[11px] text-slate-500">JSON Repair Recovery</p>
                <p className="text-xl font-bold text-emerald-700">{(agent.metrics.json_repair_recovery_rate * 100).toFixed(1)}%</p>
              </div>
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <p className="text-[11px] text-slate-500">Graceful 503/Timeout Fallback</p>
                <p className="text-xl font-bold text-emerald-700">{(agent.metrics.graceful_fallback_rate * 100).toFixed(1)}%</p>
              </div>
              <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200">
                <p className="text-[11px] text-emerald-800">HITL Gate Enforcement</p>
                <p className="text-xl font-bold text-emerald-800">{(agent.metrics.hitl_enforcement_rate * 100).toFixed(1)}%</p>
              </div>
            </div>
          )}
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="font-bold text-sm text-slate-900 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-indiaGreen" />
              4. Red-Team Safety ({redteam?.num_tests ?? 0})
            </h4>
            {redteam && renderExportButtons('red_team_report', redteam.eval_trace_id)}
          </div>
          {!redteam ? (
            <p className="text-xs text-slate-400">Red-team report not yet generated.</p>
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2">
                <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200">
                  <p className="text-[10px] text-emerald-800">Overall Defense</p>
                  <p className="text-lg font-bold text-emerald-800">{(redteam.overall_pass_rate * 100).toFixed(1)}%</p>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                  <p className="text-[10px] text-slate-500">Injection Block</p>
                  <p className="text-lg font-bold text-indiaNavy">{(redteam.injection_block_rate * 100).toFixed(1)}%</p>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                  <p className="text-[10px] text-slate-500">PII Masking</p>
                  <p className="text-lg font-bold text-indiaNavy">{(redteam.pii_masking_rate * 100).toFixed(1)}%</p>
                </div>
              </div>
              {redteam.failure_taxonomy && redteam.failure_taxonomy.length > 0 && (
                <div className="text-xs space-y-1">
                  <p className="font-semibold text-slate-700">Tracked Failure Taxonomy</p>
                  {redteam.failure_taxonomy.map((ft) => (
                    <div key={ft.code} className="flex items-center justify-between bg-slate-50 px-2.5 py-1.5 rounded">
                      <span><strong>{ft.code}</strong>: {ft.category}</span>
                      <span className="font-mono text-slate-500">count: {ft.count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 5. Recent Live Traces Quick-Export Table right inside Evals */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2">
          <h4 className="font-bold text-xs text-slate-800">
            5. Recent Live Execution Traces (Download Structured JSON / Markdown by Trace ID)
          </h4>
          <button
            type="button"
            onClick={() => downloadAuthenticatedFile('/api/traces/export/all?format=json&hide_erased=true', 'jansahayak_traces.json')}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-indiaNavy text-white text-[11px] font-medium"
          >
            <Download className="w-3 h-3" /> Export All Traces (JSON)
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-slate-50 text-slate-500 border-b border-slate-200">
              <tr>
                <th className="p-2.5 text-left">Trace ID</th>
                <th className="p-2.5 text-left">Persona</th>
                <th className="p-2.5 text-left">Query</th>
                <th className="p-2.5 text-right">Latency</th>
                <th className="p-2.5 text-right">Tokens</th>
                <th className="p-2.5 text-right">Download</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {recentTraces.map((t) => (
                <tr key={t.trace_id} className="hover:bg-slate-50">
                  <td className="p-2.5 font-mono font-semibold text-indiaNavy">{t.trace_id}</td>
                  <td className="p-2.5 text-slate-600">@{t.user_id || 'anonymous'}</td>
                  <td className="p-2.5 max-w-xs truncate text-slate-800">{t.user_query_masked}</td>
                  <td className="p-2.5 text-right font-mono">{(t.total_latency_ms / 1000).toFixed(2)}s</td>
                  <td className="p-2.5 text-right font-mono">{t.prompt_tokens + t.completion_tokens}</td>
                  <td className="p-2.5 text-right">
                    <div className="inline-flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => downloadAuthenticatedFile(`/api/traces/${t.trace_id}/export?format=json`, `trace_${t.trace_id}.json`)}
                        className="px-2 py-0.5 rounded border border-slate-300 hover:bg-slate-100 text-[10px] font-mono"
                      >
                        JSON
                      </button>
                      <button
                        type="button"
                        onClick={() => downloadAuthenticatedFile(`/api/traces/${t.trace_id}/export?format=md`, `trace_${t.trace_id}.md`)}
                        className="px-2 py-0.5 rounded border border-slate-300 hover:bg-slate-100 text-[10px] font-mono"
                      >
                        MD
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {recentTraces.length === 0 && (
                <tr>
                  <td colSpan={6} className="p-4 text-center text-slate-400">
                    No active live traces yet. Send a message in Citizen Copilot.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
