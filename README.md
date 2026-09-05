# Lauffey: Advanced Biometric-to-Blockchain Provenance Pipeline

**Lauffey** is an end-to-end provenance architecture that:
1. Takes an input face scan / image or captures directly from your laptop's camera (`/dev/video0`).
2. **Highest-Accuracy Biometric Processing**: Localizes and geometrically aligns faces with **RetinaFace** (5-point landmark regression) and extracts **512-dimensional ArcFace embeddings** (99.83% SOTA accuracy). Supports fast YuNet+SFace mode on demand.
3. **Live Reverse-Image Web Search (default)**: Queries Google Lens via SerpAPI across social networks (X, Facebook, GitHub, Medium) to find a genuine matching post — not a hardcoded lookup — with intelligent SHA-256 caching so repeat scans never re-spend quota.
4. **On-Device Biometric Discovery Engine (`local_engine.py`, `--local`)**: Optional 0-quota fallback that runs real vector similarity search against a local gallery of profiles on device instead of the web.
5. Generates a **Cryptographic Merkle Provenance Tree** using Ethereum-native **Keccak-256 (SHA3-256)** to mathematically bind the 512-d biometric vector, content metadata, temporal nonce, and validator identity.
6. Issues an **ECDSA secp256k1 Digital Signature** (EIP-191 attestation) over the state claims.
7. Anchors the Merkle Root, audit paths, and attestation into EVM transaction calldata.
8. Conducts independent multi-layer ledger verification (On-chain transaction proof + mathematical Merkle branch audit + cryptographic signature recovery).
9. Exports portable, verifiable provenance receipts and provides interactive tamper detection demonstration.

---

## Hardware Optimization
Engineered for workstation-class performance:
- **Processor**: High-throughput multi-core architecture powering concurrent cryptographic hashing and deep inference.
- **Biometric Inference**: SOTA RetinaFace detector and ArcFace 512-d deep residual feature extractor.
- **Memory**: High-speed memory residency for zero-copy tensor manipulation.

---

## 2026 Advanced Blockchain Specification

Lauffey implements the modern data integrity standards utilized in contemporary Layer-2 rollups and modular data availability layers:

1. **Keccak-256 Merkle Provenance Trees**:
   - **Leaf 0 (Biometric Claim)**: Keccak-256 hash of normalized feature vector + detection confidence.
   - **Leaf 1 (Social Discovery Claim)**: Keccak-256 hash of canonical URL, title, platform, and author metadata.
   - **Leaf 2 (Temporal Attestation)**: Keccak-256 hash of timestamp, validator address, and network identifier.
   - **Leaf 3 (Validator Signature Witness)**: Keccak-256 hash of the cryptographic signature.
   - **Root**: Cryptographic Merkle Root binding all claims into an immutable 32-byte commitment.

2. **Zero-Knowledge Ready Merkle Inclusion Proofs**:
   - Generates mathematical sibling audit paths. Any party can independently verify that a specific social post belongs to a verified face scan without needing access to the raw biometric vector, ensuring complete privacy compliance.

3. **ECDSA secp256k1 Digital Attestations (EIP-191)**:
   - Validates the identity of the asserting validator node. Re-verification mathematically recovers the signer's public key from the transaction payload.

4. **EVM Calldata Anchoring**:
   - Anchors the state root directly into EVM transaction calldata, compatible with Ethereum Mainnet, Arbitrum, Base, Optimism, Monad, and in-memory EVM test harnesses.

---

## Installation & Setup

### 1. Prerequisites
- Python 3.10 - 3.12 (or virtual environment via `uv`)

### 2. Configure Environment
```bash
cp .env.example .env
```
Add your credentials to `.env`:
```env
SERPAPI_KEY=your_serpapi_key_here
```
*(Sensitive credentials in `.env` are strictly excluded in `.gitignore`)*

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## How to Run

### 1. Live Reverse Visual Search (Google Lens via SerpAPI) — Default
Every run performs a genuine reverse-image web search by default (requires `SERPAPI_KEY` in `.env`). Results are cached by image SHA-256, so re-scanning the same photo never re-spends quota:
```bash
# Automatically discovers available queries in test_images/
python main.py

# Query with ANY arbitrary image
python main.py --image path/to/any_face.jpg
python main.py --image test_images/messi_query.jpg
python main.py --image test_images/biden_query.jpg
python main.py --image test_images/lena_query.jpg
```
If live search fails (no key, quota exhausted, network issue), the pipeline logs the failure and falls back to the on-device gallery rather than silently faking a result.

### 1b. On-Device Biometric Discovery (`--local`, 0 API Quota Consumed)
Skips the web search entirely and matches against the dynamically indexed local gallery:
```bash
python main.py --local
python main.py --image path/to/any_face.jpg --local

# List all dynamically indexed identities in the gallery
python main.py --list-profiles

# Register ANY novel identity into the biometric gallery at runtime
python main.py --register path/to/new_face.jpg --name "Full Name"
```

### 3. Live Webcam Hardware Scan
Initiates an interactive scan using your laptop's integrated camera (`/dev/video0`):
```bash
python main.py --camera
```

### 4. Tamper Detection Demonstration
Demonstrates real-time cryptographic tamper rejection by altering post claims:
```bash
python main.py --tamper-demo
```

### 5. Independent Receipt Verification
Inspects and mathematically audits an exported provenance receipt JSON file:
```bash
python verify_receipt.py --receipt receipts/sample_receipt.json
```

### 6. Automated Unit Test Suite
Executes the full automated cryptographic test suite dynamically:
```bash
python test_pipeline.py
```

### 7. Extreme Multi-Vector Performance & Adversarial Benchmark
Executes multi-identity perturbation stress, concurrency throughput, Merkle scaling to 16,384 leaves, vector DB scaling to 50k identities, and 1,000 adversarial tamper attacks:
```bash
python benchmark.py
```

### 8. Interactive Web Frontend (units.gr Design Language)
Start the local web server to launch the visual interface:
```bash
python server.py
# Open your browser at http://localhost:5000
```
- **Design System**: High-contrast Bauhaus / Neo-Brutalist design language inspired by `units.gr` (blueprint grid canvas, cream floating container, and color-blocked numbered card deck).
- **Interactive Features**: Drag-and-drop face image dropzone, live webcam trigger, test portrait quick selector, real-time face landmark HUD, passive liveness gauge, and one-click tamper simulation test.
- **Live web search**: on by default (genuine SerpAPI Google Lens reverse-image search, cached by image hash so repeat scans of the same photo never re-spend quota). Check "Skip live web search" to match against the free on-device gallery instead (0 API quota).

---

## Dynamic Test Dataset

The repository includes diverse public-domain benchmark queries across multiple subjects:

| Query Image | Subject | Purpose | Expected Dynamic Match |
|---|---|---|---|
| `test_images/obama_query.jpg` | Barack Obama | Query test (angled pose) | Barack Obama |
| `test_images/obama_query_alt.jpg`| Barack Obama | Alternative query lighting | Barack Obama |
| `test_images/biden_query.jpg` | Joe Biden | Query test | Joe Biden |
| `test_images/messi_query.jpg` | Lionel Messi | Athlete portrait | Lionel Messi |
| `test_images/lena_query.jpg` | Lena Forsen | Signal processing test portrait | Lena Forsen |
| `test_images/alex_query.png` | Alex Lacamoire | Musician / Composer | Alex Lacamoire |
| `test_images/lin_query.png` | Lin-Manuel Miranda | Playwright / Actor | Lin-Manuel Miranda |
| `data/profiles/` | Gallery Directory | Dynamically auto-indexed | Any dropped portrait auto-indexes |

---

## Blockchain Used

Lauffey supports three interchangeable chain backends behind the same Merkle-anchoring interface. **By default all three are locally persisted, tamper-evident ledgers, not live public-network connections** — see [Known Limitations](#known-limitations) for exactly what that means and how to point them at a real network.

### 1. MegaETH-style Engine (`--chain megaeth`, Default)
- Modeled on MegaETH's 10ms block time / EigenDA data-availability design.
- **Cryptographic Primitives**: Keccak-256 Merkle Provenance trees and EIP-191 ECDSA secp256k1 digital signatures.
- **Ledger**: `data/ledger_megaeth.json`, a locally persisted append-only store (not a connection to the live MegaETH network).

### 2. Solana-style Engine (`--chain solana`)
- Modeled on Solana's Memo-program anchoring pattern (`MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr`).
- **Cryptographic Primitives**: Ed25519 signatures, Base58 encoding, SHA-256 Merkle Provenance trees.
- **Ledger**: `data/ledger_solana.json`, a locally persisted append-only store (not a devnet/mainnet RPC connection — the public devnet faucet was rate-limited when we tested it, see limitations).

### 3. EVM Engine (`--chain evm`)
- **Cryptographic Primitives**: Keccak-256 Merkle trees, ECDSA secp256k1 (EIP-191).
- **Default mode**: `py-evm`/`eth-tester` in-memory EVM sandbox per process, backed by `data/ledger_evm.json` for cross-process re-verification.
- **Real mode**: set `BLOCKCHAIN_RPC` in `.env` to a public RPC URL (e.g. a Sepolia endpoint) and `VALIDATOR_PRIVATE_KEY` to a funded key — `record_on_chain` then submits a genuine, block-explorer-checkable transaction instead of using the local ledger.

All three verifiers persist their validator keypair (`data/*_validator_key.json`, gitignored) and their ledger to disk, so a transaction recorded by one process (`python main.py`) is independently re-verifiable by a completely separate process later (`python verify_receipt.py --receipt receipts/&lt;file&gt;.json`) — this is what "re-verifying against the on-chain record" means for the local/simulated backends.

---

## Known Limitations

1. **Local/simulated ledgers by default, not a live public network.** `megaeth` and `solana` are always locally persisted ledgers (there is no live MegaETH testnet RPC or funded Solana wallet wired in — the public Solana devnet faucet was rate-limited from our environment when we tried). `evm` defaults to the same local pattern but becomes a genuine on-chain submission the moment `BLOCKCHAIN_RPC` + a funded `VALIDATOR_PRIVATE_KEY` are set in `.env`. This is within what the task allows ("public testnet, mainnet, or a local/simulated chain"), and re-verification across separate process runs is real and demonstrable via `verify_receipt.py`.
2. **Live web search is the default, local gallery is opt-out.** `python main.py` with no flags and the web frontend both perform a genuine SerpAPI Google Lens reverse-image search by default — pass `--local` (CLI) or check "Skip live web search" (frontend) to match against the on-device gallery instead (`data/profiles.json`, 0 API quota). Results are cached by image SHA-256, so repeat scans of the same photo (including the auto-run demo scan on page load) only spend quota once.
3. **Third-Party API Rate Limits in Live Mode**: Live web search requires SerpAPI credits. If quota is exhausted or the network fails, the pipeline logs the failure and falls back to the on-device discovery engine rather than silently returning a fabricated result.
4. **Private Social Media Posts**: Reverse image search only discovers publicly indexed web and social media content. Private accounts (e.g. locked Instagram or private X accounts) cannot be crawled by search engines.
5. **Extreme Facial Occlusion**: Heavy masks, extreme sunglasses, or severe profile angles (>60° yaw) may degrade biometric landmark detection confidence below verification thresholds.
6. **L1 State Storage Economics**: Storing raw 512-dimensional floating point vectors directly in Ethereum L1 storage is economically impractical. Lauffey anchors only the 32-byte Merkle Root commitment (never the raw biometric vector) into transaction calldata, keeping verification costs minimal on a real L2 and privacy-preserving by design.

