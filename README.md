# Lauffey: Biometric-to-Blockchain Provenance Pipeline

Face scan in, verified on-chain proof out. Lauffey takes a face, finds a real matching social media post for it on the web, and anchors that finding to a blockchain in a way anyone can independently re-check later.

**Live demo:** https://lauffey-frontend.vercel.app (frontend on Vercel, backend on AWS EC2)

## What it does

1. **Detect and encode the face.** RetinaFace + ArcFace (512-d, default) or YuNet + SFace (128-d, faster) via `face_processor.py`. Also does passive liveness detection (screen-replay / print-attack heuristics), so it's checking for a live face, not just a photo of a photo.
2. **Search the web for a real matching post.** Default behavior, not opt-in: every scan runs a genuine reverse-image search (Google Lens via SerpAPI, with Serper.dev as a fallback) and returns whatever it actually finds - a real Reddit thread, a real Instagram post, a real news article. Nothing is hardcoded or pre-picked. Results are cached by image hash so re-scanning the same photo never spends API quota twice.
3. **Anchor it to a blockchain.** The matched post (or a hash of it) gets Merkle-proofed, ECDSA/Ed25519-signed, and recorded on-chain. Supports three backends (MegaETH-style, Solana-style, EVM) - see [Blockchain Used](#blockchain-used) below for exactly what "on-chain" means for each.
4. **Re-verify independently.** `verify_receipt.py` takes an exported receipt and re-checks it from scratch in a completely separate process - recomputes the Merkle proof, recovers the signer, and (for the EVM path with a real RPC configured) looks the transaction up on a public block explorer.

Also included: a W3C Verifiable Credential is issued per scan, tamper detection can be demonstrated live (mutate a claim, watch the cryptographic proof reject it), and there's a web frontend on top of all of this.

## Setup in 5 minutes (Docker)

```bash
git clone <this-repo>
cd lauffey
cp .env.example .env
# add SERPER_API_KEY and/or SERPAPI_KEY to .env - either is enough
docker compose up --build
```
Then open http://localhost:5000. No Python, no dependency wrangling - the container has everything (OpenCV, ArcFace, torch, the works) already baked in. First build pulls a few GB of ML libraries, so it takes longer than 5 minutes on a slow connection; after that, `docker compose up` alone starts it in seconds.

## Quick start (without Docker)

```bash
git clone <this-repo>
cd lauffey
cp .env.example .env
# add SERPER_API_KEY and/or SERPAPI_KEY to .env - either is enough
pip install -r requirements.txt
python main.py
```

That's it - `python main.py` with no arguments picks a test image, runs the full pipeline, and prints a receipt. Python 3.10-3.12.

## How to run

**Default (live search, on-chain, all in one go):**
```bash
python main.py
python main.py --image path/to/any_face.jpg
python main.py --image path/to/any_face.jpg --chain solana   # or evm
```

**Skip the live search** (uses a free on-device gallery match instead, 0 API quota - useful for testing without burning your key):
```bash
python main.py --local
```

**Webcam scan:**
```bash
python main.py --camera
```

**Tamper detection demo** (mutates a claim and shows the chain reject it):
```bash
python main.py --tamper-demo
```

**Re-verify a receipt independently, in a fresh process:**
```bash
python verify_receipt.py --receipt receipts/sample_receipt.json
```

**Run the tests:**
```bash
python test_pipeline.py
```

**Web frontend:**
```bash
python server.py
# http://localhost:5000
```
Live search is on by default here too - there's a checkbox to switch to the local gallery if you want to conserve quota while poking around the UI. `docker compose up --build` runs this same server containerized (see [Setup in 5 minutes](#setup-in-5-minutes-docker) above); `.env` is read via `env_file`, and `data/`/`receipts/` are mounted so the chain ledgers and receipts survive a container restart.

## Blockchain used

Three interchangeable backends, same Merkle-anchoring interface (`blockchain_verifier.py`, `solana_verifier.py`, `megaeth_verifier.py`):

- **MegaETH-style** (`--chain megaeth`, default) - Keccak-256 Merkle trees, ECDSA secp256k1 signatures, modeled on MegaETH's block-time/EigenDA design.
- **Solana-style** (`--chain solana`) - Ed25519 signatures, SHA-256 Merkle trees, Memo-program-shaped payloads.
- **EVM** (`--chain evm`) - Keccak-256 Merkle trees, ECDSA secp256k1. Defaults to a local `py-evm`/`eth-tester` sandbox; point `BLOCKCHAIN_RPC` and `VALIDATOR_PRIVATE_KEY` in `.env` at a funded testnet wallet (e.g. Sepolia) and it submits genuine, Etherscan-checkable transactions instead. We've done this and confirmed it live - real transaction, real block, independently re-verified from a separate process against the public RPC.

By default, `megaeth` and `solana` are locally persisted ledgers (`data/ledger_*.json`) rather than live public-network connections. The part that actually matters - re-verifying a recorded transaction independently, in a separate process, later - works and is demonstrable via `verify_receipt.py` regardless of which backend you pick. All three verifiers persist their validator keypair (`data/*_validator_key.json`, gitignored) alongside the ledger, so a transaction recorded by `python main.py` today is still there and still verifiable next week.

## Test images

Public-domain / fair-use portraits for quick testing:

| Image | Subject |
|---|---|
| `test_images/obama_query.jpg`, `obama_query_alt.jpg` | Barack Obama |
| `test_images/biden_query.jpg` | Joe Biden |
| `test_images/messi_query.jpg` | Lionel Messi |
| `test_images/lena_query.jpg` | Lena Forsen (the classic image-processing test photo) |
| `test_images/alex_query.png` | Alex Lacamoire |
| `test_images/lin_query.png` | Lin-Manuel Miranda |

Drop in any other face and it works the same way - nothing here is special-cased.

## Deployment

Current setup: static frontend on Vercel, Flask backend on an AWS EC2 instance (Mumbai region), connected via a Vercel rewrite so the browser only ever talks to Vercel's HTTPS domain (Vercel proxies to the backend server-side, so the backend doesn't need its own TLS certificate).

**Managing the EC2 instance** (it bills hourly while running, ~$0.09/hr on a t3.large - stop it when you're not demoing):
```bash
aws ec2 stop-instances --instance-ids i-06b44fd7ac5249f1b --region ap-south-1
aws ec2 start-instances --instance-ids i-06b44fd7ac5249f1b --region ap-south-1
```
The backend is a systemd service (`lauffey.service`) that starts automatically when the instance boots - no manual step needed after `start-instances`, just give it a minute to come up. The instance has an Elastic IP, so the public address doesn't change across stop/start.

## Design notes

Things worth knowing about how this is built:

- **The default chains are local, not testnet/mainnet.** Re-verification against the recorded state genuinely works across separate processes, which is the part that actually proves something. The EVM backend can also run against a real funded testnet wallet when you want the extra credibility of a public explorer link, and we've verified that path works too.
- **Reverse-image search finds photo matches, not face matches.** Google Lens (via SerpAPI/Serper) matches images by visual similarity, not facial recognition - it's very good at finding the same photo reposted elsewhere, and reasonably good at recognizing public figures by their face, but it won't reliably find a *different* photo of a private individual. Dedicated face-search engines exist (PimEyes, FaceCheck.ID) but they're paid, restrict third-party API use, and carry a privacy-surveillance reputation we didn't want attached to this project.
- **Private accounts are invisible, on purpose.** Reverse image search can only surface what's publicly indexed. A locked Instagram or private X account won't show up - that's a property of the web, not a bug here.
- **Only a 32-byte Merkle root ever touches the chain, never the raw biometric vector.** Storing a 512-dimensional float vector on-chain is both expensive and a privacy problem. The Merkle proof lets a third party confirm a specific claim was included without ever seeing the underlying face embedding.
- **Heavy occlusion (masks, extreme angles) degrades detection confidence.** Expected behavior for any face detector, flagged honestly in the output rather than forced through.

## Repo layout

Main pipeline: `main.py` (CLI), `server.py` (web API), `face_processor.py`, `web_searcher.py`, `local_engine.py`, `liveness_detector.py`, `zk_credential.py`. Blockchain: `blockchain_verifier.py`, `solana_verifier.py`, `megaeth_verifier.py`, `chain_ledger_store.py`. Verification: `verify_receipt.py`, `test_pipeline.py`. Frontend: `frontend/`.
