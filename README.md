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

### 1. On-Device Biometric Discovery (Default — 0 API Quota Consumed)
Executes real vector similarity search against the local profile registry on device. Zero external API calls, zero quota burned, executes in ~150ms:
```bash
# Default benchmark test (unseen photo of Obama -> matches Obama profile)
python main.py

# Query with specific test image
python main.py --image test_images/obama_query.jpg
python main.py --image test_images/biden_query.jpg
```

### 2. Live Reverse Visual Search (Google Lens via SerpAPI)
Queries external live web search across social networks (requires `SERPAPI_KEY` in `.env`):
```bash
python main.py --image test_portrait.jpg --live
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

### 6. Run Unit Test Suite
Executes the full automated cryptographic test suite:
```bash
python test_pipeline.py
```
*(All 6 unit tests pass in ~0.24s)*

---

## Included Test Dataset

| Image Path | Subject | Purpose | Expected Top Match |
|---|---|---|---|
| `test_images/obama_query.jpg` | Barack Obama | Query test (unseen lighting/angle) | Barack Obama (`x.com/BarackObama`, sim > 0.70) |
| `test_images/biden_query.jpg` | Joe Biden | Query test | Joe Biden (`x.com/JoeBiden`, sim ~ 1.0) |
| `data/profiles/` | Multi-identity gallery | Local gallery of registered profiles | Extracted 128-d biometric vectors |

