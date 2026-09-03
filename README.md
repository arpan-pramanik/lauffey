# Lauffey: Advanced Biometric-to-Blockchain Provenance Pipeline

**Lauffey** is an end-to-end provenance architecture that:
1. Takes an input face scan / image or captures directly from your laptop's camera (`/dev/video0`).
2. **Highest-Accuracy Biometric Processing**: Localizes and geometrically aligns faces with **RetinaFace** (5-point landmark regression) and extracts **512-dimensional ArcFace embeddings** (99.83% SOTA accuracy). Supports fast YuNet+SFace mode on demand.
3. **On-Device Biometric Discovery Engine (`local_engine.py`)**: Executes real vector similarity search against a local gallery of profiles on device with **0 API quota used**.
4. **Live Visual Search Mode (`--live`)**: Queries Google Lens via SerpAPI across social networks (X, Facebook, GitHub, Medium) with intelligent SHA-256 caching.
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

### 1. Dynamic On-Device Biometric Discovery (0 API Quota Consumed)
Executes real vector similarity search against the dynamically indexed biometric gallery:
```bash
# Automatically discovers available queries in test_images/
python main.py

# Query with ANY arbitrary image
python main.py --image path/to/any_face.jpg
python main.py --image test_images/messi_query.jpg
python main.py --image test_images/biden_query.jpg
python main.py --image test_images/lena_query.jpg

# List all dynamically indexed identities in the gallery
python main.py --list-profiles

# Register ANY novel identity into the biometric gallery at runtime
python main.py --register path/to/new_face.jpg --name "Full Name"
```

### 2. Live Reverse Visual Search (Google Lens via SerpAPI)
Queries external live web search across social networks for any face image (requires `SERPAPI_KEY` in `.env`):
```bash
python main.py --image path/to/any_face.jpg --live
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

Lauffey provides a **Dual Multi-Chain Architecture** supporting both EVM Layer-2 rollups and the Solana high-throughput network:

### 1. Solana Engine (`--chain solana`)
- **Ledger Architecture**: Solana high-speed attestation engine with sub-second execution (400ms slots).
- **Instruction Anchoring**: Formats and anchors state commitments directly into the **Solana SPL Memo Program (`MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr`)**.
- **Cryptographic Primitives**:
  - **Ed25519 Signatures**: Solana's native high-performance signature curve over Twisted Edwards Curve25519.
  - **Base58 Encoding**: Standard Solana public key and transaction signature representation.
  - **SHA-256 Merkle Provenance Tree**: Solana-native binary tree generating cryptographic audit paths.

### 2. EVM Layer-2 Engine (`--chain evm`, Default)
- **Ledger Standard**: Ethereum Virtual Machine (EVM) calldata anchoring compatible with Ethereum Mainnet, Arbitrum, Base, Optimism, Monad, and local EVM nodes.
- **Local Testing Engine**: Integrated `py-evm` in-memory blockchain via `eth-tester` and `web3.py` for deterministic, zero-cost execution without testnet faucets.
- **Configurable RPC**: Connect to any live public testnet (Sepolia, Base Sepolia, Arbitrum Sepolia) via `BLOCKCHAIN_RPC` in `.env`.
- **Cryptographic Primitives**:
  - **Keccak-256 (SHA3-256)**: Ethereum-native hashing for Merkle Provenance Trees.
  - **ECDSA secp256k1 (EIP-191)**: Decentralized validator key recovery and digital attestation.

---

## Known Limitations

1. **Third-Party API Rate Limits in Live Mode**: Live web search requires SerpAPI credits. If quota is exhausted or network fails, the pipeline automatically falls back to the on-device discovery engine.
2. **Private Social Media Posts**: Reverse image search only discovers publicly indexed web and social media content. Private accounts (e.g. locked Instagram or private X accounts) cannot be crawled by search engines.
3. **Extreme Facial Occlusion**: Heavy masks, extreme sunglasses, or severe profile angles (>60° yaw) may degrade biometric landmark detection confidence below verification thresholds.
4. **L1 State Storage Economics**: Storing raw 512-dimensional floating point vectors directly in Ethereum L1 storage is economically impractical. Lauffey overcomes this limitation by anchoring the 32-byte Merkle Root commitment into transaction calldata, keeping verification costs minimal (<$0.001 on Layer-2 rollups).


