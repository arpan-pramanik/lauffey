# Lauffey: Extreme Performance & Stress Benchmark Report

Generated: 2026-09-03 11:17:40

> **Note:** this report predates several features added afterward (liveness detection, W3C verifiable credentials, Solana/MegaETH chains, the web frontend) and only exercises fast-mode face matching, the local discovery engine, and the EVM verifier. Re-run `python benchmark.py` for a report covering the current code. The `FAIL` rows below are genuine adversarial-robustness results (e.g. heavy Gaussian noise defeating fast-mode matching), not fabricated — recorded here as-is rather than hidden.

## 1. Executive Summary
A multi-dimensional stress benchmark testing adversarial robustness, thread concurrency, cryptographic scaling, vector search scalability, and tamper resistance.

## 2. Benchmark Suites
### Suite 1: Adversarial Perturbation Stress
| Condition | Top Match | Similarity | Status |
|---|---|---|---|
| Original | Alex Lacamoire | 0.9991 | PASS |
| Gaussian Blur (k=11) | Alex Lacamoire | 0.8989 | PASS |
| Noise (s=30) | Lin Manuel Miranda | 0.2431 | FAIL |
| Low-Light (-60%) | Alex Lacamoire | 0.9553 | PASS |
| Overexposure (+60%) | Alex Lacamoire | 0.8984 | PASS |
| Rotation (+15°) | Alex Lacamoire | 0.9552 | PASS |
| JPEG Compression (Q=15) | Alex Lacamoire | 0.8776 | PASS |
| Original | Joe Biden | 0.9961 | PASS |
| Gaussian Blur (k=11) | Joe Biden | 0.9414 | PASS |
| Noise (s=30) | Lin Manuel Miranda | 0.1242 | FAIL |
| Low-Light (-60%) | Joe Biden | 0.9266 | PASS |
| Overexposure (+60%) | Joe Biden | 0.9302 | PASS |
| Rotation (+15°) | Joe Biden | 0.9662 | PASS |
| JPEG Compression (Q=15) | Joe Biden | 0.9417 | PASS |
| Original | Lena Forsen | 0.9890 | PASS |
| Gaussian Blur (k=11) | Joe Biden | 0.2015 | FAIL |
| Noise (s=30) | Joe Biden | 0.1761 | FAIL |
| Low-Light (-60%) | Lena Forsen | 0.9466 | PASS |
| Overexposure (+60%) | Alex Lacamoire | 0.1102 | FAIL |
| Rotation (+15°) | Lena Forsen | 0.8762 | PASS |
| JPEG Compression (Q=15) | Lena Forsen | 0.8522 | PASS |
| Original | Lin Manuel Miranda | 0.9995 | PASS |
| Gaussian Blur (k=11) | Lin Manuel Miranda | 0.9616 | PASS |
| Noise (s=30) | Lin Manuel Miranda | 0.7939 | PASS |
| Low-Light (-60%) | Lin Manuel Miranda | 0.9604 | PASS |
| Overexposure (+60%) | Lin Manuel Miranda | 0.9117 | PASS |
| Rotation (+15°) | Lin Manuel Miranda | 0.9727 | PASS |
| JPEG Compression (Q=15) | Lin Manuel Miranda | 0.9559 | PASS |
| Original | Lionel Messi | 0.9938 | PASS |
| Gaussian Blur (k=11) | Alex Lacamoire | 0.1694 | FAIL |
| Noise (s=30) | Lin Manuel Miranda | 0.2077 | FAIL |
| Low-Light (-60%) | Lionel Messi | 0.8798 | PASS |
| Overexposure (+60%) | Lionel Messi | 0.8396 | PASS |
| Rotation (+15°) | Alex Lacamoire | 0.1370 | FAIL |
| JPEG Compression (Q=15) | Lionel Messi | 0.5762 | PASS |
| Original | Obama Small | 0.7675 | PASS |
| Gaussian Blur (k=11) | Obama Small | 0.7228 | PASS |
| Noise (s=30) | Obama Small | 0.6910 | PASS |
| Low-Light (-60%) | Obama Small | 0.7485 | PASS |
| Overexposure (+60%) | Obama Small | 0.7365 | PASS |
| Rotation (+15°) | Obama Small | 0.7431 | PASS |
| JPEG Compression (Q=15) | Obama Small | 0.7412 | PASS |
| Original | Obama Small | 0.7675 | PASS |
| Gaussian Blur (k=11) | Obama Small | 0.7228 | PASS |
| Noise (s=30) | Obama Small | 0.7181 | PASS |
| Low-Light (-60%) | Obama Small | 0.7485 | PASS |
| Overexposure (+60%) | Obama Small | 0.7365 | PASS |
| Rotation (+15°) | Obama Small | 0.7431 | PASS |
| JPEG Compression (Q=15) | Obama Small | 0.7412 | PASS |

### Suite 2: Multi-Threaded Concurrency
| Workers | Total Time (s) | QPS (Inferences/s) | p50 (ms) | p99 (ms) |
|---|---|---|---|---|
| 1 | 4.12 | 24.29 | 35.08 | 135.82 |
| 4 | 2.62 | 38.18 | 85.94 | 329.78 |
| 8 | 2.59 | 38.61 | 127.41 | 878.32 |
| 16 | 2.81 | 35.63 | 248.64 | 1602.64 |
| 32 | 3.25 | 30.79 | 641.50 | 2992.56 |

### Suite 3: Merkle Tree Cryptographic Scaling
| Leaves | Depth | Build (ms) | Proof Gen (µs) | Verify (µs) |
|---|---|---|---|---|
| 16 | 4 | 0.07 | 9.50 | 24.02 |
| 64 | 6 | 0.25 | 3.01 | 26.84 |
| 256 | 8 | 0.90 | 6.80 | 33.96 |
| 1024 | 10 | 3.52 | 8.38 | 42.04 |
| 4096 | 12 | 14.18 | 12.50 | 49.53 |
| 16384 | 14 | 49.14 | 9.79 | 51.40 |

### Suite 4: Vector Gallery Scale (512-d)
| Identities | Search Latency (µs) | Throughput (QPS) | Memory (MB) |
|---|---|---|---|
| 1000 | 31.97 | 31280.3 | 2.15 |
| 5000 | 236.62 | 4226.2 | 9.96 |
| 10000 | 20.62 | 48496.1 | 19.73 |
| 25000 | 67.80 | 14750.2 | 49.02 |
| 50000 | 103.64 | 9648.5 | 97.85 |

### Suite 5: Adversarial Tamper Fuzzing
- Total Attacks: 1000
- Attacks Blocked: 1000
- False Acceptance Rate: 0.000000%
