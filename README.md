# Lauffey: Biometric Face-to-Blockchain Verification Pipeline

**Lauffey** is an end-to-end Python pipeline that:
1. Takes an input face scan / image.
2. Extracts biometric features and localizes the facial region using GPU-accelerated deep learning.
3. Conducts a reverse visual search across the web and social media (X, Instagram, LinkedIn, Reddit, etc.) via Google Lens.
4. Computes a deterministic SHA-256 fingerprint linking the biometric vector to the discovered post data.
5. Anchors the cryptographic fingerprint into an EVM blockchain transaction calldata.
6. Independently re-verifies the on-chain ledger record to guarantee tamper-proof provenance.

---

## Hardware Optimization
Designed to take advantage of high-performance workstation hardware:
- **GPU**: NVIDIA GeForce RTX 5070 8GB (Blackwell sm_120 architecture) utilized for face detection, RetinaFace alignment, and deep feature embedding extraction.
- **CPU**: AMD Ryzen 9 9955HX (32 threads) for concurrent network I/O, image processing, and cryptographic verification.
- **Memory**: 32GB RAM ensuring frictionless tensor caching and model residency.

---

## Pipeline Architecture

```
[ Input Face Scan (.jpg / .png) ]
               │
               ▼
   [ Stage 1: Face Processing ]
   • Bounding box localization (RetinaFace / Haar Cascade)
   • 20% margin padding & portrait cropping
   • Deep embedding extraction (Facenet512 / Biometric vector)
   • GPU acceleration on RTX 5070
               │
               ▼
   [ Stage 2: Reverse Visual Discovery ]
   • Temporary image hosting (ephemeral 1h TTL)
   • SerpAPI Google Lens visual match indexing
   • Social domain filtering (X, Instagram, LinkedIn, etc.)
   • Local SHA-256 caching (prevents wasting API quota)
               │
               ▼
   [ Stage 3: Blockchain Cryptographic Anchoring ]
   • Deterministic SHA-256 fingerprinting of {embedding, URL, metadata, timestamp}
   • Packing fingerprint into Ethereum transaction calldata
   • Immutable transaction broadcast
               │
               ▼
   [ Stage 4: On-Chain Ledger Verification ]
   • Querying transaction by TX hash directly from the chain
   • Decoding calldata payload & comparing against computed fingerprint
   • Verification proof (TAMPERED vs UNTAMPERED)
```

---

## Blockchain Specification

- **Chain Type**: Ethereum Virtual Machine (EVM).
- **Default Engine**: In-memory EVM (`EthereumTesterProvider` via `eth-tester[py-evm]`) with zero external daemon requirements, zero gas faucets, and instant block finality.
- **Calldata Storage**: Rather than deploying gas-heavy bespoke smart contracts, Lauffey stores the canonical SHA-256 fingerprint directly in the transaction's `data` (calldata) field. This is the gold-standard lightweight pattern for immutable data anchoring on Ethereum.
- **Public Network Support**: Pointing `BLOCKCHAIN_RPC` in `config.py` (or `.env`) to any public EVM node (e.g. Sepolia, Arbitrum, or Mainnet) immediately transitions the pipeline to a live public chain.

---

## Installation & Setup

### 1. Prerequisites
- Python 3.10 - 3.12 (or virtual environment via `uv`)
- CUDA 12.6+ / NVIDIA Driver 565+ (for RTX 5070 GPU acceleration)

### 2. Environment Configuration
Clone the repository and copy the environment template:
```bash
cp .env.example .env
```
Edit `.env` and configure your credentials:
```env
SERPAPI_KEY=your_serpapi_key_here
```
*(Sensitive environment files `.env` are strictly excluded in `.gitignore`)*

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## How to Run

### Standard End-to-End Pipeline
```bash
python main.py --image path/to/face.jpg
```

### Dry-Run Mode (Preserve SerpAPI Free Quota)
If you have limited API calls and want to verify the pipeline logic without hitting external APIs:
```bash
python main.py --image path/to/face.jpg --dry-run
```

### Force Search (Bypass Local Cache)
```bash
python main.py --image path/to/face.jpg --force-search
```

---

## Known Limitations

1. **General Visual Match vs. Biometric Lookup**: Google Lens is a general visual search engine rather than a dedicated facial recognition database like Clearview AI or PimEyes. While cropping to the face with padding significantly biases Lens towards social profile pictures and avatars, very obscure faces with low public web presence may return general visual matches rather than direct social profile links.
2. **Ephemeral In-Memory Chain**: The default `EthereumTesterProvider` is an in-memory EVM state that lives for the lifetime of the process. For persistent cross-process historical lookup, configure `BLOCKCHAIN_RPC` to an active Ganache or Sepolia endpoint.
3. **Free Tier Quotas**: Free-tier SerpAPI accounts provide 100 requests/month. Lauffey incorporates a local SHA-256 caching layer in `.cache/` to ensure identical images never consume duplicate credits.
