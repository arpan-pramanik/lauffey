# Lauffey: Advanced Biometric-to-Blockchain Provenance Pipeline

**Lauffey** is an end-to-end provenance architecture that:
1. Takes an input face scan / image.
2. Localizes and crops facial features with portrait padding using sub-20ms deep learning (OpenCV YuNet + SFace).
3. Executes a live reverse visual search across the web and social networks (Google Lens via SerpAPI), filtering for real posts on X (Twitter), Facebook, GitHub, Medium, and LinkedIn.
4. Generates a **Cryptographic Merkle Provenance Tree** using Ethereum-native **Keccak-256 (SHA3-256)** to mathematically bind the biometric vector, content metadata, temporal nonce, and validator identity.
5. Issues an **ECDSA secp256k1 Digital Signature** (EIP-191 attestation) over the state claims.
6. Anchors the Merkle Root, audit paths, and attestation into EVM transaction calldata.
7. Conducts independent multi-layer ledger verification (On-chain transaction proof + mathematical Merkle branch audit + cryptographic signature recovery).

---

## Hardware Optimization
Engineered for workstation-class performance:
- **Processor**: AMD Ryzen 9 9955HX (32 threads) powering concurrent cryptographic hashing and image operations.
- **Biometric Inference**: C++ ONNX deep learning engines running in sub-50ms without framework initialization delays.
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

### Live End-to-End Pipeline
```bash
python main.py --image path/to/face.jpg
```

### Dry-Run Mode (Preserves API Quota)
Runs full biometric feature extraction, synthetic discovery, Merkle Tree construction, and on-chain verification with 0 API calls:
```bash
python main.py --image path/to/face.jpg --dry-run
```

### Force Refresh (Bypass Local Cache)
```bash
python main.py --image path/to/face.jpg --force-search
```
