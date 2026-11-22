# Prompting Strategy Comparison (`P1` vs `P2` vs `P3`)
- **Fixed Model:** `Qwen/Qwen3-8B` | **Retrieval:** `R4` (Hybrid RRF + Cross-Encoder Reranker) | **Queries:** 30 stratified

| Strategy | Description | Answer Accuracy | Citation Adherence | Hallucination Rate | Eligibility Acc | Avg Latency (s) | Avg Tokens |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **P1** | Zero-Shot Direct Prompt | **93.3%** | **10.0%** | 66.7% | 100.0% | 4.18s | 1660 |
| **P2** | Few-Shot Structured Prompt | **96.7%** | **100.0%** | 6.7% | 100.0% | 4.11s | 1968 |
| **P3** | Grounded Planner-Executor-Synthesizer-Critic | **100.0%** | **100.0%** | 0.0% | 100.0% | 4.49s | 2193 |
