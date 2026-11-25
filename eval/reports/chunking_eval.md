# Chunking Experiments

Each strategy re-chunks the official text of all 649 schemes into a temporary hybrid index; FAQ chunks are identical in every strategy. Retrieval only (no LLM).

- `section_440_ov35` is production; it reproduces the live index exactly: **yes**.
- Top-5 chunks per query. Evidence hit@5 = the gold evidence sentence (at least 80% of it, contiguous) is inside one top-5 chunk of the right scheme.
- p-values: exact McNemar against production on the same queries (paired); p < 0.05 = a real difference.

## Index size

| Strategy | Description | Official-text chunks | Avg / max tokens (estimate) | Newly embedded | Split to fit 512 |
|---|---|---:|---|---:|---:|
| `section_440_ov35` | Production: section-aware, 440 tokens, 35-word overlap | 3204 | 305 / 440 | 0 | 0 |
| `section_256_ov20` | Section-aware, 256 tokens, 20-word overlap | 5350 | 203 / 256 | 4677 | 0 |
| `section_128_ov10` | Section-aware, 128 tokens, 10-word overlap | 12264 | 110 / 242 | 11909 | 0 |
| `section_440_ov0` | Section-aware, 440 tokens, no overlap | 3101 | 294 / 440 | 1098 | 1 |
| `fixed_440_ov35` | Fixed 440-token windows across section boundaries, 35-word overlap | 2623 | 372 / 440 | 2623 | 1 |

## Gold Q&A questions (FAQ chunks excluded)

### `bm25`

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR | Evidence hit@5 (95% CI) | Context tokens | Latency | p (Hit@5 vs prod) | p (evidence vs prod) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `section_440_ov35` | 96.7% | 100.0% | 100.0% | 0.983 | 91.7% (81.9%-96.4%) | 1522 | 69 ms | - | - |
| `section_256_ov20` | 96.7% | 100.0% | 100.0% | 0.983 | 86.7% (75.8%-93.1%) | 1001 | 102 ms | 1.0 | 0.375 |
| `section_128_ov10` | 98.3% | 100.0% | 100.0% | 0.992 | 68.3% (55.8%-78.7%) | 552 | 215 ms | 1.0 | 0.0001 |
| `section_440_ov0` | 96.7% | 100.0% | 100.0% | 0.983 | 90.0% (79.8%-95.3%) | 1493 | 92 ms | 1.0 | 1.0 |
| `fixed_440_ov35` | 98.3% | 100.0% | 100.0% | 0.992 | 98.3% (91.1%-99.7%) | 1907 | 93 ms | 1.0 | 0.125 |

### `dense`

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR | Evidence hit@5 (95% CI) | Context tokens | Latency | p (Hit@5 vs prod) | p (evidence vs prod) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `section_440_ov35` | 88.3% | 98.3% | 98.3% | 0.931 | 96.7% (88.6%-99.1%) | 1502 | 4 ms | - | - |
| `section_256_ov20` | 90.0% | 96.7% | 96.7% | 0.933 | 90.0% (79.8%-95.3%) | 995 | 6 ms | 1.0 | 0.125 |
| `section_128_ov10` | 96.7% | 100.0% | 100.0% | 0.983 | 83.3% (72.0%-90.7%) | 562 | 14 ms | 1.0 | 0.0215 |
| `section_440_ov0` | 95.0% | 98.3% | 98.3% | 0.964 | 93.3% (84.1%-97.4%) | 1447 | 4 ms | 1.0 | 0.5 |
| `fixed_440_ov35` | 86.7% | 95.0% | 95.0% | 0.906 | 90.0% (79.8%-95.3%) | 1791 | 4 ms | 0.5 | 0.125 |

### `hybrid_rrf`

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR | Evidence hit@5 (95% CI) | Context tokens | Latency | p (Hit@5 vs prod) | p (evidence vs prod) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `section_440_ov35` | 100.0% | 100.0% | 100.0% | 1.000 | 96.7% (88.6%-99.1%) | 1520 | 71 ms | - | - |
| `section_256_ov20` | 96.7% | 100.0% | 100.0% | 0.983 | 95.0% (86.3%-98.3%) | 1000 | 104 ms | 1.0 | 1.0 |
| `section_128_ov10` | 100.0% | 100.0% | 100.0% | 1.000 | 83.3% (72.0%-90.7%) | 558 | 214 ms | 1.0 | 0.0215 |
| `section_440_ov0` | 100.0% | 100.0% | 100.0% | 1.000 | 95.0% (86.3%-98.3%) | 1486 | 93 ms | 1.0 | 1.0 |
| `fixed_440_ov35` | 95.0% | 98.3% | 100.0% | 0.971 | 96.7% (88.6%-99.1%) | 1835 | 94 ms | 1.0 | 1.0 |

### `hybrid_rerank` (production retriever)

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR | Evidence hit@5 (95% CI) | Context tokens | Latency | p (Hit@5 vs prod) | p (evidence vs prod) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `section_440_ov35` | 98.3% | 98.3% | 100.0% | 0.987 | 98.3% (91.1%-99.7%) | 1560 | 1731 ms | - | - |
| `section_256_ov20` | 96.7% | 98.3% | 98.3% | 0.972 | 96.7% (88.6%-99.1%) | 1020 | 1045 ms | 1.0 | 1.0 |
| `section_128_ov10` | 98.3% | 98.3% | 98.3% | 0.983 | 88.3% (77.8%-94.2%) | 563 | 810 ms | 1.0 | 0.0312 |
| `section_440_ov0` | 96.7% | 98.3% | 100.0% | 0.979 | 96.7% (88.6%-99.1%) | 1518 | 1856 ms | 1.0 | 1.0 |
| `fixed_440_ov35` | 93.3% | 96.7% | 96.7% | 0.950 | 95.0% (86.3%-98.3%) | 1835 | 1951 ms | 0.5 | 0.5 |


## Task-suite scheme queries (FAQ chunks included, as live)

### `bm25`

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR | Context tokens | Latency | p (Hit@5 vs prod) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `section_440_ov35` | 90.4% | 93.2% | 93.2% | 0.918 | 1202 | 62 ms | - |
| `section_256_ov20` | 90.4% | 93.2% | 93.2% | 0.918 | 1004 | 93 ms | 1.0 |
| `section_128_ov10` | 91.8% | 93.2% | 93.2% | 0.925 | 684 | 199 ms | 1.0 |
| `section_440_ov0` | 91.8% | 93.2% | 93.2% | 0.925 | 1185 | 83 ms | 1.0 |
| `fixed_440_ov35` | 90.4% | 93.2% | 94.5% | 0.920 | 1288 | 83 ms | 1.0 |

### `dense`

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR | Context tokens | Latency | p (Hit@5 vs prod) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `section_440_ov35` | 83.6% | 91.8% | 94.5% | 0.877 | 1394 | 7 ms | - |
| `section_256_ov20` | 79.5% | 89.0% | 91.8% | 0.843 | 1018 | 9 ms | 0.5 |
| `section_128_ov10` | 80.8% | 90.4% | 90.4% | 0.849 | 632 | 17 ms | 0.375 |
| `section_440_ov0` | 80.8% | 93.2% | 93.2% | 0.863 | 1362 | 8 ms | 1.0 |
| `fixed_440_ov35` | 79.5% | 90.4% | 91.8% | 0.848 | 1572 | 8 ms | 0.5 |

### `hybrid_rrf`

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR | Context tokens | Latency | p (Hit@5 vs prod) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `section_440_ov35` | 90.4% | 94.5% | 95.9% | 0.925 | 1338 | 66 ms | - |
| `section_256_ov20` | 90.4% | 94.5% | 94.5% | 0.922 | 1052 | 99 ms | 1.0 |
| `section_128_ov10` | 90.4% | 94.5% | 94.5% | 0.922 | 666 | 199 ms | 1.0 |
| `section_440_ov0` | 89.0% | 94.5% | 95.9% | 0.918 | 1314 | 86 ms | 1.0 |
| `fixed_440_ov35` | 87.7% | 94.5% | 95.9% | 0.909 | 1455 | 87 ms | 1.0 |

### `hybrid_rerank` (production retriever)

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR | Context tokens | Latency | p (Hit@5 vs prod) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `section_440_ov35` | 83.6% | 94.5% | 95.9% | 0.892 | 1430 | 1620 ms | - |
| `section_256_ov20` | 84.9% | 95.9% | 95.9% | 0.904 | 1060 | 1298 ms | 1.0 |
| `section_128_ov10` | 83.6% | 95.9% | 95.9% | 0.893 | 677 | 1250 ms | 1.0 |
| `section_440_ov0` | 83.6% | 93.2% | 95.9% | 0.887 | 1431 | 1787 ms | 1.0 |
| `fixed_440_ov35` | 79.5% | 93.2% | 95.9% | 0.868 | 1600 | 1852 ms | 1.0 |

