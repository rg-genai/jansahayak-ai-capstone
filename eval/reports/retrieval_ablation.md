# Retrieval Ablation Benchmark (`R1`–`R4`)
- **Evaluated Queries:** 73 (stratified across Scheme QA, Eligibility, FAQs & Multilingual English-Pivot)

| Config | Strategy | Recall@3 | Recall@5 | Recall@10 | MRR@10 | NDCG@5 | Avg Latency (ms) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **R1** | BM25-Only (Sparse Lexical) | 93.2% | **93.2%** | 94.5% | **0.920** | 0.921 | 28.1 |
| **R2** | Dense-Only (bge-small-en-v1.5) | 91.8% | **94.5%** | 94.5% | **0.877** | 0.894 | 3.2 |
| **R3** | Hybrid RRF (BM25 + Dense) | 94.5% | **95.9%** | 95.9% | **0.925** | 0.933 | 31.7 |
| **R4** | Hybrid RRF + Cross-Encoder Reranker + Metadata Filter | 94.5% | **95.9%** | 95.9% | **0.892** | 0.909 | 1664.7 |

## R4 Top-5 Misses (3)
- `ML-08` (`pmkvy-rpl`): got `['mssc', 'pmmvy', 'pmjdy']`
- `ML-10` (`pmecrg`): got `['pmfby', 'pmksypdmc', 'pm-kisan']`
- `GRV-08` (`pm-sym`): got `['eps', 'pmvs', 'psgs-dip']`
