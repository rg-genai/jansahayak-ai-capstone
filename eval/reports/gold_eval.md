# Gold Q&A Evaluation

- Gold set: 60 questions written from scheme text (not the FAQs); review status {'unreviewed': 60}.
- Every run: FAQ chunks excluded from retrieval; live web fallback disabled (noted per answer).
- ROUGE-L F1 and BLEU on answers with citations/links/markdown removed; BERTScore F1 = `roberta-large`, rescaled. Judge = `gemini-3.5-flash-lite` (1-5; correct = score >= 4).

## Answer quality

| Config | Model | n | ROUGE-L | BLEU | BERTScore | Judge (1-5) | Judge correct | Gold scheme in context |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `main` | Qwen/Qwen3-8B | 60 | 0.230 | 7.196 | 0.172 | 4.533 (n=60) | 88.3% | 94.9% |
| `main_before_guards` | Qwen/Qwen3-8B | 60 | 0.185 | 5.570 | 0.120 | - (n=0) | - | 96.5% |
| `main_guards_only` | Qwen/Qwen3-8B | 60 | 0.202 | 5.967 | 0.144 | 3.914 (n=58) | 69.0% | 96.6% |
| `no_corpus` | Qwen/Qwen3-8B | 60 | 0.224 | 5.342 | 0.233 | 2.586 (n=58) | 19.0% | - |
| `single_pass` | Qwen/Qwen3-8B | 60 | 0.250 | 8.060 | 0.206 | 4.717 (n=60) | 93.3% | 96.6% |
| `top1` | Qwen/Qwen3-8B | 30 | 0.255 | 8.766 | 0.242 | 4.600 (n=30) | 93.3% | 100.0% |
| `top3` | Qwen/Qwen3-8B | 30 | 0.241 | 8.322 | 0.225 | 4.700 (n=30) | 93.3% | 100.0% |
| `top5` | Qwen/Qwen3-8B | 30 | 0.237 | 8.774 | 0.217 | 4.733 (n=30) | 96.7% | 100.0% |

## Latency and cost

| Config | Retrieval | Planning | Answer writing | Total (avg) | Total (p95) | Tokens | Web fallback skipped |
|---|---:|---:|---:|---:|---:|---:|---:|
| `main` | 3.25s | 4.53s | 6.86s | 14.75s | 18.15s | 9258 | 0.0% |
| `main_before_guards` | 2.21s | 4.34s | 6.75s | 13.40s | 22.26s | 7117 | 0.0% |
| `main_guards_only` | 2.37s | 4.52s | 7.54s | 14.50s | 22.37s | 7811 | 0.0% |
| `no_corpus` | 0.00s | 0.00s | 1.73s | 1.73s | 2.35s | 153 | 0.0% |
| `single_pass` | 2.55s | 2.25s | 6.04s | 10.91s | 14.37s | 7156 | 0.0% |
| `top1` | 2.53s | 3.49s | 5.35s | 11.43s | 17.09s | 3870 | 0.0% |
| `top3` | 2.23s | 3.54s | 5.41s | 11.23s | 15.71s | 5285 | 0.0% |
| `top5` | 2.25s | 6.03s | 5.66s | 13.98s | 36.42s | 6628 | 0.0% |

## Compared with the main pipeline on the same questions

| Config | n | ROUGE-L (config / main) | BERTScore (config / main) | Judge (config / main) |
|---|---:|---:|---:|---:|
| `main_before_guards` | 60 | 0.185 / 0.230 | 0.120 / 0.172 | - / 4.533 |
| `main_guards_only` | 60 | 0.202 / 0.230 | 0.144 / 0.172 | 3.914 / 4.533 |
| `no_corpus` | 60 | 0.224 / 0.230 | 0.233 / 0.172 | 2.586 / 4.533 |
| `single_pass` | 60 | 0.250 / 0.230 | 0.206 / 0.172 | 4.717 / 4.533 |
| `top1` | 30 | 0.255 / 0.211 | 0.242 / 0.152 | 4.600 / 4.367 |
| `top3` | 30 | 0.241 / 0.211 | 0.225 / 0.152 | 4.700 / 4.367 |
| `top5` | 30 | 0.237 / 0.211 | 0.217 / 0.152 | 4.733 / 4.367 |

### Is the difference real? (paired tests on questions both configs were judged on)

| Config | n | Only config correct | Only main correct | McNemar p | Judge score diff (config - main), 95% CI |
|---|---:|---:|---:|---:|---|
| `main_guards_only` | 58 | 3 | 14 | 0.0127 | -0.60 (-1.00 to -0.22) |
| `no_corpus` | 58 | 1 | 41 | 0.0 | -1.93 (-2.26 to -1.59) |
| `single_pass` | 60 | 4 | 1 | 0.375 | +0.18 (+0.00 to +0.38) |
| `top1` | 30 | 4 | 1 | 0.375 | +0.23 (-0.13 to +0.63) |
| `top3` | 30 | 4 | 1 | 0.375 | +0.33 (+0.00 to +0.70) |
| `top5` | 30 | 4 | 0 | 0.125 | +0.37 (+0.07 to +0.70) |

## Retrievers on the gold questions (no LLM)

| Retriever | n | Hit@1 | Hit@3 | Hit@5 | MRR | Source section in top 5 | Avg latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| `bm25` | 60 | 96.7% | 100.0% | 100.0% | 0.983 | 98.3% | 88 ms |
| `dense` | 60 | 88.3% | 98.3% | 98.3% | 0.931 | 98.3% | 4 ms |
| `hybrid_rrf` | 60 | 100.0% | 100.0% | 100.0% | 1.000 | 98.3% | 89 ms |
| `hybrid_rerank` | 60 | 98.3% | 98.3% | 100.0% | 0.987 | 100.0% | 2344 ms |

## Answer status counts

- `main`: {'ok': 60} (errors excluded: 0)
- `main_before_guards`: {'ok': 52, 'awaiting_user_input': 6, 'out_of_scope': 2} (errors excluded: 0)
- `main_guards_only`: {'ok': 60} (errors excluded: 0)
- `no_corpus`: {'ok': 60} (errors excluded: 0)
- `single_pass`: {'ok': 60} (errors excluded: 0)
- `top1`: {'ok': 30} (errors excluded: 0)
- `top3`: {'ok': 30} (errors excluded: 0)
- `top5`: {'ok': 30} (errors excluded: 0)
