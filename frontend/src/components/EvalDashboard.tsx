import React, { useState, useEffect } from 'react'
import {
  BarChart3,
  ShieldCheck,
  Wrench,
  Sparkles,
  RefreshCw,
  Download,
  FileJson,
  FileText,
  Award,
  Clock,
  CheckCircle2,
} from 'lucide-react'
import { apiFetch, downloadAuthenticatedFile } from '../api'
import { TraceRecord } from '../types'

interface Gold60NLPBlock {
  rouge_1_f1: number
  rouge_2_f1: number
  rouge_l_f1: number
  bleu_corpus: number
  bleu_sentence_avg: number
  bertscore_precision: number
  bertscore_recall: number
  bertscore_f1: number
}

interface Gold60JudgeBlock {
  avg_accuracy_5: number
  avg_faithfulness_5: number
  avg_completeness_5: number
  overall_score_pct: number
  pass_rate: number
  hallucination_rate: number
}

interface Gold60Report {
  eval_trace_id?: string
  model_evaluated: string
  judge_model: string
  judge_note: string
  num_pairs: number
  leakage_verification: {
    corpus_faqs_checked: number
    exact_faq_question_matches: number
    max_jaccard_similarity_vs_faqs: number
    passed_zero_leakage_check: boolean
  }
  retrieval_top_k_ablation: Array<{
    id: string
    name: string
    recall_at_1: number
    recall_at_3: number
    recall_at_5: number
    mrr_at_5: number
    ndcg_at_5: number
    avg_latency_ms: number
  }>
  nlp_metrics: {
    vanilla_llm: Gold60NLPBlock
    agentic_rag: Gold60NLPBlock
  }
  independent_judge: {
    vanilla_llm: Gold60JudgeBlock
    agentic_rag: Gold60JudgeBlock
  }
  latency_breakdown: {
    vanilla_avg_llm_ms: number
    vanilla_avg_total_ms: number
    rag_avg_retrieval_ms: number
    rag_avg_llm_ms: number
    rag_avg_total_ms: number
    vanilla_avg_tokens: number
    rag_avg_tokens: number
  }
}

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
        recall_at_1?: number
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
    gold60_comprehensive_eval?: Gold60Report | null
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

  const gold60 = data?.reports?.gold60_comprehensive_eval
  const retrieval = data?.reports?.retrieval_ablation
  const prompts = data?.reports?.prompt_comparison
  const agent = data?.reports?.agent_reliability
  const redteam = data?.reports?.red_team_report

  const renderExportButtons = (reportKey: string, traceId?: string) => (
    <div className="flex items-center gap-1.5">
      {traceId && (
        <span className="px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-white/10 font-mono text-[10px] font-semibold text-indiaNavy dark:text-sky-300">
          {traceId}
        </span>
      )}
      <button
        type="button"
        onClick={() => downloadAuthenticatedFile(`/api/evals/export/${reportKey}?format=json`, `${reportKey}.json`)}
        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full border border-slate-300/80 bg-white/60 hover:bg-white text-[10px] font-medium text-slate-700 transition dark:border-white/15 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10"
      >
        <FileJson className="w-3 h-3 text-indiaNavy dark:text-sky-300" /> JSON
      </button>
      <button
        type="button"
        onClick={() => downloadAuthenticatedFile(`/api/evals/export/${reportKey}?format=md`, `${reportKey}.md`)}
        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full border border-slate-300/80 bg-white/60 hover:bg-white text-[10px] font-medium text-slate-700 transition dark:border-white/15 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10"
      >
        <FileText className="w-3 h-3 text-emerald-700 dark:text-emerald-400" /> MD
      </button>
    </div>
  )

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-base font-bold text-indiaNavy dark:text-slate-100 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-indiaNavy dark:text-sky-300" />
            Track B Quantitative Benchmarks, Unbiased External Judge &amp; Debug Traces
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Real evaluation outputs on fixed `Qwen/Qwen3-8B` + `bge-small-en-v1.5`, including ROUGE, BLEU, BERTScore, Vanilla LLM vs. RAG, Top-1/3/5 Ablation &amp; Independent Gemini Judge.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          className="btn-secondary gap-1.5 px-3 py-1.5 text-xs font-medium"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Reload ({data?.available_reports ?? 0}/{data?.total_expected ?? 5})
        </button>
      </div>

      {/* 0. NEW: 60-Pair Zero-Leakage Gold QA — Vanilla vs RAG + ROUGE/BLEU/BERTScore + Independent Gemini Judge */}
      {gold60 && (
        <div className="glass p-5 space-y-4 border-indiaSaffron/30">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h4 className="font-bold text-sm text-indiaNavy dark:text-slate-100 flex items-center gap-1.5">
                <Award className="w-4 h-4 text-indiaSaffron" />
                1. 60-Pair Zero-Leakage Gold QA: Vanilla LLM vs. Agentic Hybrid RAG (ROUGE, BLEU, BERTScore &amp; Independent Gemini Judge)
              </h4>
              <div className="flex flex-wrap items-center gap-2 mt-1">
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-100/80 text-emerald-900 dark:bg-emerald-500/20 dark:text-emerald-200 text-[10px] font-semibold">
                  <CheckCircle2 className="w-3 h-3" /> Zero FAQ Leakage ({gold60.leakage_verification.exact_faq_question_matches}/{gold60.leakage_verification.corpus_faqs_checked} exact matches)
                </span>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-sky-100/80 text-sky-900 dark:bg-sky-500/20 dark:text-sky-200 text-[10px] font-semibold">
                  Static External Judge: {gold60.judge_model} (Zero Qwen Self-Bias)
                </span>
              </div>
            </div>
            {renderExportButtons('gold60_comprehensive_eval', gold60.eval_trace_id)}
          </div>

          {/* KPI Strip: Independent Gemini Judge + NLP Highlights + Latency Breakdown */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            <div className="glass-subtle p-3.5 bg-emerald-50/75 border-emerald-300/70 dark:bg-emerald-500/15 dark:border-emerald-400/30">
              <p className="text-[10px] text-emerald-800 dark:text-emerald-300 font-semibold uppercase">Gemini Judge (RAG)</p>
              <p className="text-xl font-bold text-emerald-800 dark:text-emerald-200">
                {gold60.independent_judge.agentic_rag.avg_accuracy_5.toFixed(2)} / 5
              </p>
              <p className="text-[10px] text-emerald-700 dark:text-emerald-300">
                vs. {gold60.independent_judge.vanilla_llm.avg_accuracy_5.toFixed(2)}/5 Vanilla LLM
              </p>
            </div>
            <div className="glass-subtle p-3.5">
              <p className="text-[10px] text-slate-500 dark:text-slate-400 font-semibold uppercase">BERTScore F1 (RAG)</p>
              <p className="text-xl font-bold text-indiaNavy dark:text-sky-300">
                {(gold60.nlp_metrics.agentic_rag.bertscore_f1 * 100).toFixed(1)}%
              </p>
              <p className="text-[10px] text-slate-500 dark:text-slate-400">
                vs. {(gold60.nlp_metrics.vanilla_llm.bertscore_f1 * 100).toFixed(1)}% Vanilla
              </p>
            </div>
            <div className="glass-subtle p-3.5">
              <p className="text-[10px] text-slate-500 dark:text-slate-400 font-semibold uppercase">ROUGE-L F1 (RAG)</p>
              <p className="text-xl font-bold text-indiaNavy dark:text-sky-300">
                {(gold60.nlp_metrics.agentic_rag.rouge_l_f1 * 100).toFixed(1)}%
              </p>
              <p className="text-[10px] text-slate-500 dark:text-slate-400">
                vs. {(gold60.nlp_metrics.vanilla_llm.rouge_l_f1 * 100).toFixed(1)}% Vanilla
              </p>
            </div>
            <div className="glass-subtle p-3.5">
              <p className="text-[10px] text-slate-500 dark:text-slate-400 font-semibold uppercase">BLEU Score (RAG)</p>
              <p className="text-xl font-bold text-indiaNavy dark:text-sky-300">
                {(gold60.nlp_metrics.agentic_rag.bleu_corpus * 100).toFixed(1)}%
              </p>
              <p className="text-[10px] text-slate-500 dark:text-slate-400">
                vs. {(gold60.nlp_metrics.vanilla_llm.bleu_corpus * 100).toFixed(1)}% Vanilla
              </p>
            </div>
            <div className="glass-subtle p-3.5">
              <p className="text-[10px] text-slate-500 dark:text-slate-400 font-semibold uppercase flex items-center gap-1">
                <Clock className="w-3 h-3 text-indiaSaffron" /> Avg RAG Latency
              </p>
              <p className="text-xl font-bold text-indiaSaffron">
                {(gold60.latency_breakdown.rag_avg_total_ms / 1000).toFixed(2)}s
              </p>
              <p className="text-[10px] text-slate-500 dark:text-slate-400">
                Ret {(gold60.latency_breakdown.rag_avg_retrieval_ms / 1000).toFixed(2)}s + LLM {(gold60.latency_breakdown.rag_avg_llm_ms / 1000).toFixed(2)}s
              </p>
            </div>
          </div>

          {/* Side-by-Side Detailed Matrix: Vanilla LLM vs Agentic Hybrid RAG */}
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
            <div className="xl:col-span-7 overflow-x-auto">
              <p className="text-xs font-bold text-slate-700 dark:text-slate-200 mb-1.5">
                A. Generation Quality Matrix — Vanilla Qwen3-8B (No Corpus) vs. JanSahayak Agentic Hybrid RAG (60 Pairs)
              </p>
              <table className="w-full text-xs border border-slate-200/80 dark:border-white/10 rounded-lg">
                <thead className="bg-slate-100/70 text-slate-600 dark:bg-white/10 dark:text-slate-300">
                  <tr>
                    <th className="p-2 text-left">Metric</th>
                    <th className="p-2 text-right">Vanilla LLM (No RAG)</th>
                    <th className="p-2 text-right">Agentic Hybrid RAG</th>
                    <th className="p-2 text-right">Delta Gain</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200/70 dark:divide-white/10 font-mono">
                  {[
                    ['ROUGE-1 (F1)', gold60.nlp_metrics.vanilla_llm.rouge_1_f1 * 100, gold60.nlp_metrics.agentic_rag.rouge_1_f1 * 100, '%', true],
                    ['ROUGE-2 (F1)', gold60.nlp_metrics.vanilla_llm.rouge_2_f1 * 100, gold60.nlp_metrics.agentic_rag.rouge_2_f1 * 100, '%', true],
                    ['ROUGE-L (F1)', gold60.nlp_metrics.vanilla_llm.rouge_l_f1 * 100, gold60.nlp_metrics.agentic_rag.rouge_l_f1 * 100, '%', true],
                    ['BLEU (Corpus)', gold60.nlp_metrics.vanilla_llm.bleu_corpus * 100, gold60.nlp_metrics.agentic_rag.bleu_corpus * 100, '%', true],
                    ['BERTScore (F1)', gold60.nlp_metrics.vanilla_llm.bertscore_f1 * 100, gold60.nlp_metrics.agentic_rag.bertscore_f1 * 100, '%', true],
                    ['Gemini Judge: Accuracy (/5)', gold60.independent_judge.vanilla_llm.avg_accuracy_5, gold60.independent_judge.agentic_rag.avg_accuracy_5, '', false],
                    ['Gemini Judge: Faithfulness (/5)', gold60.independent_judge.vanilla_llm.avg_faithfulness_5, gold60.independent_judge.agentic_rag.avg_faithfulness_5, '', false],
                    ['Gemini Judge: Hallucination Rate', gold60.independent_judge.vanilla_llm.hallucination_rate * 100, gold60.independent_judge.agentic_rag.hallucination_rate * 100, '%', false],
                  ].map(([label, v, r, unit]) => {
                    const diff = Number(r) - Number(v)
                    const isHall = String(label).includes('Hallucination')
                    const good = isHall ? diff <= 0 : diff >= 0
                    return (
                      <tr key={String(label)} className={String(label).includes('Gemini') ? 'bg-sky-50/40 dark:bg-sky-500/10 font-semibold' : ''}>
                        <td className="p-2 font-sans">{String(label)}</td>
                        <td className="p-2 text-right">{Number(v).toFixed(2)}{String(unit)}</td>
                        <td className="p-2 text-right font-bold text-indiaNavy dark:text-sky-200">{Number(r).toFixed(2)}{String(unit)}</td>
                        <td className={`p-2 text-right font-semibold ${good ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                          {diff >= 0 ? '+' : ''}{diff.toFixed(2)}{String(unit)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <div className="xl:col-span-5 space-y-3">
              <div className="overflow-x-auto">
                <p className="text-xs font-bold text-slate-700 dark:text-slate-200 mb-1.5">
                  B. Top-1 / Top-3 / Top-5 Retrieval Ablation (60 Zero-Leakage Queries)
                </p>
                <table className="w-full text-xs border border-slate-200/80 dark:border-white/10 rounded-lg">
                  <thead className="bg-slate-100/70 text-slate-600 dark:bg-white/10 dark:text-slate-300">
                    <tr>
                      <th className="p-2 text-left">Config</th>
                      <th className="p-2 text-right">Top-1</th>
                      <th className="p-2 text-right">Top-3</th>
                      <th className="p-2 text-right">Top-5</th>
                      <th className="p-2 text-right">Lat.</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200/70 dark:divide-white/10 font-mono">
                    {gold60.retrieval_top_k_ablation.map((c) => (
                      <tr key={c.id} className={c.id === 'R4' || c.id === 'R3' ? 'bg-emerald-50/40 dark:bg-emerald-500/10 font-semibold' : ''}>
                        <td className="p-2 font-sans">{c.id}: {c.name.split(' ')[0]}</td>
                        <td className="p-2 text-right">{(c.recall_at_1 * 100).toFixed(1)}%</td>
                        <td className="p-2 text-right">{(c.recall_at_3 * 100).toFixed(1)}%</td>
                        <td className="p-2 text-right">{(c.recall_at_5 * 100).toFixed(1)}%</td>
                        <td className="p-2 text-right">{c.avg_latency_ms.toFixed(0)}ms</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="glass-subtle p-3 text-xs space-y-1.5">
                <p className="font-bold text-indiaNavy dark:text-slate-100">C. Latency Breakdown (Average Across 60 Queries)</p>
                <div className="flex justify-between">
                  <span className="text-slate-600 dark:text-slate-300">Hybrid Retrieval + Cross-Encoder:</span>
                  <span className="font-mono font-semibold">{gold60.latency_breakdown.rag_avg_retrieval_ms.toFixed(0)} ms</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600 dark:text-slate-300">Qwen3-8B Generation (RAG):</span>
                  <span className="font-mono font-semibold">{(gold60.latency_breakdown.rag_avg_llm_ms / 1000).toFixed(2)} s</span>
                </div>
                <div className="flex justify-between border-t border-slate-200/70 dark:border-white/10 pt-1">
                  <span className="font-semibold text-slate-800 dark:text-slate-100">Total End-to-End (RAG vs Vanilla):</span>
                  <span className="font-mono font-bold text-indiaSaffron">
                    {(gold60.latency_breakdown.rag_avg_total_ms / 1000).toFixed(2)}s vs {(gold60.latency_breakdown.vanilla_avg_total_ms / 1000).toFixed(2)}s
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 2. Retrieval Ablation R1-R4 (73-Query Stratified Suite) */}
      <div className="glass p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="font-bold text-sm text-indiaNavy dark:text-slate-100">
            2. Stratified Retrieval Ablation (73 Queries — Top-1, Top-3, Top-5, MRR@10 &amp; NDCG@5)
          </h4>
          {retrieval && renderExportButtons('retrieval_ablation', retrieval.eval_trace_id)}
        </div>
        {!retrieval ? (
          <p className="text-xs text-slate-400 dark:text-slate-500">Run `python eval/run_all_evals.py` to populate retrieval ablation metrics.</p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-center">
            <div className="lg:col-span-5 space-y-2.5">
              {retrieval.configs.map((c) => (
                <div key={c.id} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="font-semibold text-slate-800 dark:text-slate-100">{c.id}: {c.name}</span>
                    <span className="font-mono text-indiaNavy dark:text-sky-300">
                      R@5: {(c.recall_at_5 * 100).toFixed(1)}% | MRR: {c.mrr_at_10.toFixed(3)}
                    </span>
                  </div>
                  <div className="w-full h-3 bg-slate-200/80 dark:bg-white/10 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${c.id === 'R4' ? 'bg-indiaGreen dark:bg-emerald-400' : 'bg-indiaNavy/80 dark:bg-sky-400/80'}`}
                      style={{ width: `${Math.min(100, c.recall_at_5 * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <div className="lg:col-span-7 overflow-x-auto">
              <table className="w-full text-xs border border-slate-200/80 dark:border-white/10 rounded-lg">
                <thead className="bg-slate-100/70 text-slate-600 dark:bg-white/10 dark:text-slate-300">
                  <tr>
                    <th className="p-2 text-left">Config</th>
                    <th className="p-2 text-right">R@1</th>
                    <th className="p-2 text-right">R@3</th>
                    <th className="p-2 text-right">R@5</th>
                    <th className="p-2 text-right">MRR@10</th>
                    <th className="p-2 text-right">NDCG@5</th>
                    <th className="p-2 text-right">Latency</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200/70 dark:divide-white/10 font-mono">
                  {retrieval.configs.map((c) => (
                    <tr key={c.id} className={c.id === 'R4' ? 'bg-emerald-50/50 font-semibold dark:bg-emerald-400/15 dark:text-emerald-200' : ''}>
                      <td className="p-2 font-sans">{c.id}</td>
                      <td className="p-2 text-right">{c.recall_at_1 !== undefined ? `${(c.recall_at_1 * 100).toFixed(1)}%` : '—'}</td>
                      <td className="p-2 text-right">{(c.recall_at_3 * 100).toFixed(1)}%</td>
                      <td className="p-2 text-right">{(c.recall_at_5 * 100).toFixed(1)}%</td>
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

      {/* 3. Prompting Comparison P1-P3 */}
      <div className="glass p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="font-bold text-sm text-indiaNavy dark:text-slate-100 flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-indiaSaffron" />
            3. Prompting Strategy Comparison (P1 Zero-Shot vs P2 Few-Shot vs P3 Planner-Critic)
          </h4>
          {prompts && renderExportButtons('prompt_comparison', prompts.eval_trace_id)}
        </div>
        {!prompts ? (
          <p className="text-xs text-slate-400 dark:text-slate-500">Prompt comparison report not yet generated.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs border border-slate-200/80 dark:border-white/10 rounded-lg">
              <thead className="bg-slate-100/70 text-slate-600 dark:bg-white/10 dark:text-slate-300">
                <tr>
                  <th className="p-2.5 text-left">Strategy</th>
                  <th className="p-2.5 text-right">Answer Accuracy</th>
                  <th className="p-2.5 text-right">Citation Adherence</th>
                  <th className="p-2.5 text-right">Hallucination Rate</th>
                  <th className="p-2.5 text-right">Avg Latency</th>
                  <th className="p-2.5 text-right">Avg Tokens</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200/70 dark:divide-white/10 font-mono">
                {prompts.strategies.map((s) => (
                  <tr key={s.id} className={s.id === 'P3' ? 'bg-emerald-50/50 font-semibold dark:bg-emerald-400/15 dark:text-emerald-200' : ''}>
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

      {/* 4 & 5. Agent Reliability & Red-Team Safety */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="glass p-5 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="font-bold text-sm text-indiaNavy dark:text-slate-100 flex items-center gap-1.5">
              <Wrench className="w-4 h-4 text-indiaNavy dark:text-sky-300" />
              4. Agent Reliability ({agent?.num_scenarios ?? 0})
            </h4>
            {agent && renderExportButtons('agent_reliability', agent.eval_trace_id)}
          </div>
          {!agent ? (
            <p className="text-xs text-slate-400 dark:text-slate-500">Agent reliability report not yet generated.</p>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <div className="glass-subtle p-4">
                <p className="text-[11px] text-slate-500 dark:text-slate-400">Tool Selection Accuracy</p>
                <p className="text-xl font-bold text-indiaNavy dark:text-sky-300">{(agent.metrics.tool_selection_accuracy * 100).toFixed(1)}%</p>
              </div>
              <div className="glass-subtle p-4">
                <p className="text-[11px] text-slate-500 dark:text-slate-400">JSON Repair Recovery</p>
                <p className="text-xl font-bold text-emerald-700 dark:text-emerald-400">{(agent.metrics.json_repair_recovery_rate * 100).toFixed(1)}%</p>
              </div>
              <div className="glass-subtle p-4">
                <p className="text-[11px] text-slate-500 dark:text-slate-400">Graceful 503/Timeout Fallback</p>
                <p className="text-xl font-bold text-emerald-700 dark:text-emerald-400">{(agent.metrics.graceful_fallback_rate * 100).toFixed(1)}%</p>
              </div>
              <div className="glass-subtle p-4 bg-emerald-50/80 border-emerald-300/70 dark:bg-emerald-400/15 dark:border-emerald-400/30">
                <p className="text-[11px] text-emerald-800 dark:text-emerald-300">HITL Gate Enforcement</p>
                <p className="text-xl font-bold text-emerald-800 dark:text-emerald-300">{(agent.metrics.hitl_enforcement_rate * 100).toFixed(1)}%</p>
              </div>
            </div>
          )}
        </div>

        <div className="glass p-5 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="font-bold text-sm text-indiaNavy dark:text-slate-100 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-indiaGreen" />
              5. Red-Team Safety ({redteam?.num_tests ?? 0})
            </h4>
            {redteam && renderExportButtons('red_team_report', redteam.eval_trace_id)}
          </div>
          {!redteam ? (
            <p className="text-xs text-slate-400 dark:text-slate-500">Red-team report not yet generated.</p>
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2">
                <div className="glass-subtle p-2.5 bg-emerald-50/80 border-emerald-300/70 dark:bg-emerald-400/15 dark:border-emerald-400/30">
                  <p className="text-[10px] text-emerald-800 dark:text-emerald-300">Overall Defense</p>
                  <p className="text-lg font-bold text-emerald-800 dark:text-emerald-300">{(redteam.overall_pass_rate * 100).toFixed(1)}%</p>
                </div>
                <div className="glass-subtle p-2.5">
                  <p className="text-[10px] text-slate-500 dark:text-slate-400">Injection Block</p>
                  <p className="text-lg font-bold text-indiaNavy dark:text-sky-300">{(redteam.injection_block_rate * 100).toFixed(1)}%</p>
                </div>
                <div className="glass-subtle p-2.5">
                  <p className="text-[10px] text-slate-500 dark:text-slate-400">PII Masking</p>
                  <p className="text-lg font-bold text-indiaNavy dark:text-sky-300">{(redteam.pii_masking_rate * 100).toFixed(1)}%</p>
                </div>
              </div>
              {redteam.failure_taxonomy && redteam.failure_taxonomy.length > 0 && (
                <div className="text-xs space-y-1">
                  <p className="font-semibold text-slate-700 dark:text-slate-200">Tracked Failure Taxonomy</p>
                  {redteam.failure_taxonomy.map((ft) => (
                    <div key={ft.code} className="flex items-center justify-between bg-white/50 dark:bg-white/5 px-2.5 py-1.5 rounded-lg">
                      <span><strong>{ft.code}</strong>: {ft.category}</span>
                      <span className="font-mono text-slate-500 dark:text-slate-400">count: {ft.count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 6. Recent Live Traces Quick-Export Table right inside Evals */}
      <div className="glass overflow-hidden">
        <div className="px-4 py-3 bg-white/40 dark:bg-white/5 border-b border-slate-200/70 dark:border-white/10 flex flex-wrap items-center justify-between gap-2">
          <h4 className="font-bold text-xs text-indiaNavy dark:text-slate-100">
            6. Recent Live Execution Traces (Download Structured JSON / Markdown by Trace ID)
          </h4>
          <button
            type="button"
            onClick={() => downloadAuthenticatedFile('/api/traces/export/all?format=json&hide_erased=true', 'jansahayak_traces.json')}
            className="btn-primary gap-1 px-3 py-1.5 text-[11px] font-medium"
          >
            <Download className="w-3 h-3" /> Export All Traces (JSON)
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-slate-100/70 text-slate-600 dark:bg-white/10 dark:text-slate-300 border-b border-slate-200/70 dark:border-white/10">
              <tr>
                <th className="p-2.5 text-left">Trace ID</th>
                <th className="p-2.5 text-left">Persona</th>
                <th className="p-2.5 text-left">Query</th>
                <th className="p-2.5 text-right">Latency</th>
                <th className="p-2.5 text-right">Tokens</th>
                <th className="p-2.5 text-right">Download</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200/70 dark:divide-white/10">
              {recentTraces.map((t) => (
                <tr key={t.trace_id} className="hover:bg-white/60 dark:hover:bg-white/10 transition">
                  <td className="p-2.5 font-mono font-semibold text-indiaNavy dark:text-sky-300">{t.trace_id}</td>
                  <td className="p-2.5 text-slate-600 dark:text-slate-300">@{t.user_id || 'anonymous'}</td>
                  <td className="p-2.5 max-w-xs truncate text-slate-800 dark:text-slate-200">{t.user_query_masked}</td>
                  <td className="p-2.5 text-right font-mono">{(t.total_latency_ms / 1000).toFixed(2)}s</td>
                  <td className="p-2.5 text-right font-mono">{t.prompt_tokens + t.completion_tokens}</td>
                  <td className="p-2.5 text-right">
                    <div className="inline-flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => downloadAuthenticatedFile(`/api/traces/${t.trace_id}/export?format=json`, `trace_${t.trace_id}.json`)}
                        className="px-2 py-0.5 rounded-full border border-slate-300/80 bg-white/60 hover:bg-white text-[10px] font-mono text-slate-700 transition dark:border-white/15 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10"
                      >
                        JSON
                      </button>
                      <button
                        type="button"
                        onClick={() => downloadAuthenticatedFile(`/api/traces/${t.trace_id}/export?format=md`, `trace_${t.trace_id}.md`)}
                        className="px-2 py-0.5 rounded-full border border-slate-300/80 bg-white/60 hover:bg-white text-[10px] font-mono text-slate-700 transition dark:border-white/15 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10"
                      >
                        MD
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {recentTraces.length === 0 && (
                <tr>
                  <td colSpan={6} className="p-4 text-center text-slate-500 dark:text-slate-400">
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
