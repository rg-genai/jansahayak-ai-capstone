# Gold Q&A Evaluation

- Gold set: 60 questions written from scheme text (not the FAQs); review status {'unreviewed': 60}.
- Every run: FAQ chunks excluded from retrieval; live web fallback disabled (noted per answer).
- ROUGE-L F1 and BLEU on answers with citations/links/markdown removed; BERTScore F1 = `roberta-large`, rescaled. Judge = `gemini-3.8-flash` (1-5; correct = score >= 4).

## Answer quality

| Config | Model | n | ROUGE-L | BLEU | BERTScore | Judge (1-5) | Judge correct | Gold scheme in context |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `main` | Qwen/Qwen3-8B | 60 | 0.202 | 5.967 | 0.144 | - (n=0) | - | 96.6% |
| `main_before_guards` | Qwen/Qwen3-8B | 60 | 0.185 | 5.570 | 0.120 | - (n=0) | - | 96.5% |
| `no_corpus` | Qwen/Qwen3-8B | 60 | 0.224 | 5.342 | 0.233 | - (n=0) | - | - |

## Latency and cost

| Config | Retrieval | Planning | Answer writing | Total (avg) | Total (p95) | Tokens | Web fallback skipped |
|---|---:|---:|---:|---:|---:|---:|---:|
| `main` | 2.37s | 4.52s | 7.54s | 14.50s | 22.37s | 7811 | 0.0% |
| `main_before_guards` | 2.21s | 4.34s | 6.75s | 13.40s | 22.26s | 7117 | 0.0% |
| `no_corpus` | 0.00s | 0.00s | 1.73s | 1.73s | 2.35s | 153 | 0.0% |

## Compared with the main pipeline on the same questions

| Config | n | ROUGE-L (config / main) | BERTScore (config / main) | Judge (config / main) |
|---|---:|---:|---:|---:|
| `main_before_guards` | 60 | 0.185 / 0.202 | 0.120 / 0.144 | - / - |
| `no_corpus` | 60 | 0.224 / 0.202 | 0.233 / 0.144 | - / - |

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
- `no_corpus`: {'ok': 60} (errors excluded: 0)
