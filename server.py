import os
import sys
import time
import json
import base64
from pathlib import Path
from typing import Optional
from flask import Flask, request, jsonify, send_from_directory, send_file

from face_processor import FaceProcessor
from liveness_detector import LivenessDetector
from web_searcher import WebSearcher
from blockchain_verifier import BlockchainVerifier
from solana_verifier import SolanaVerifier
from megaeth_verifier import MegaETHVerifier
from zk_credential import ZKCredentialIssuer
from config import PRODUCTION_MODE

# The on-device local gallery engine is a dev-only convenience (see
# PRODUCTION_MODE) and isn't even present on the deployed backend, so it's
# only imported when actually available and needed.
if not PRODUCTION_MODE:
    from local_engine import LocalDiscoveryEngine

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
PROFILES_DIR = BASE_DIR / "data" / "profiles"
TEST_DIR = BASE_DIR / "test_images"
RECEIPTS_DIR = BASE_DIR / "receipts"
RECEIPTS_DIR.mkdir(exist_ok=True)
TEMP_DIR = BASE_DIR / "data" / "tmp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
# Only these directories may be selected by path for a scan - prevents
# arbitrary local file reads via a caller-supplied image_path.
ALLOWED_SCAN_DIRS = [TEST_DIR.resolve(), PROFILES_DIR.resolve(), TEMP_DIR.resolve()]

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB upload cap


def _sweep_temp_dir(max_age_sec: int = 300) -> None:
    """Deletes stale upload/crop derivatives so data/tmp/ doesn't grow unbounded across a session."""
    now = time.time()
    for f in TEMP_DIR.glob("*"):
        try:
            if f.is_file() and (now - f.stat().st_mtime) > max_age_sec:
                f.unlink()
        except OSError:
            pass


def _resolve_scan_path(rel_path: str) -> Optional[Path]:
    """Resolves a user-supplied image_path and confirms it stays inside an allowed directory."""
    try:
        candidate = (BASE_DIR / rel_path).resolve()
    except (OSError, ValueError):
        return None
    if not candidate.exists() or candidate.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        return None
    for allowed_dir in ALLOWED_SCAN_DIRS:
        if candidate.is_relative_to(allowed_dir):
            return candidate
    return None

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

@app.route("/")
def index():
    return send_from_directory(str(FRONTEND_DIR), "index.html")

@app.route("/images/<folder>/<filename>")
def serve_image(folder, filename):
    if folder == "profiles":
        return send_from_directory(str(PROFILES_DIR), filename)
    elif folder == "test":
        return send_from_directory(str(TEST_DIR), filename)
    elif folder == "temp":
        return send_from_directory(str(TEMP_DIR), filename)
    return jsonify({"error": "Folder not found"}), 404

@app.route("/api/status", methods=["GET"])
def get_status():
    gallery_count = 0 if PRODUCTION_MODE else len(LocalDiscoveryEngine(mode="fast").registry)
    return jsonify({
        "status": "online",
        "default_chain": "megaeth",
        "supported_chains": ["megaeth", "solana", "evm"],
        "gallery_count": gallery_count,
        "local_fallback_enabled": not PRODUCTION_MODE,
        "timestamp": int(time.time()),
        "network_info": {
            "megaeth": {"block_time_ms": 10.0, "type": "MegaETH-style local ledger", "da": "EigenDA-style commitment"},
            "solana": {"block_time_ms": 400.0, "type": "Solana-style local ledger", "da": "SPL Memo-style payload"},
            "evm": {"block_time_ms": 1000.0, "type": "EVM (local tester or live RPC)", "da": "Calldata"}
        }
    })

@app.route("/api/profiles", methods=["GET"])
def get_profiles():
    gallery = []
    if not PRODUCTION_MODE:
        local_eng = LocalDiscoveryEngine(mode="fast")
        for item in local_eng.registry:
            p = item["profile"]
            img_name = Path(p.get("image", "")).name
            gallery.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "source": p.get("source", "Verified Profile"),
                "title": p.get("title", ""),
                "link": p.get("link", ""),
                "image_url": f"/images/profiles/{img_name}"
            })

    # Available test query portraits
    test_queries = []
    for f in sorted(TEST_DIR.iterdir()):
        if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} and not f.name.startswith("temp_"):
            subj = f.stem.split("_")[0].title()
            test_queries.append({
                "filename": f.name,
                "subject": subj,
                "path": str(f.relative_to(BASE_DIR)),
                "image_url": f"/images/test/{f.name}"
            })

    return jsonify({
        "gallery": gallery,
        "test_queries": test_queries
    })

@app.route("/api/scan", methods=["POST"])
def run_scan():
    req_data = request.form.to_dict() if request.form else {}
    if request.is_json:
        req_data = request.get_json() or {}

    chain_type = req_data.get("chain", "megaeth").lower()
    mode = req_data.get("mode", "high").lower()  # SOTA ArcFace 512-d by default for better match accuracy
    # Live web search is the default (a genuine search, not a hardcoded local
    # lookup) - pass live_search=false to opt into the free on-device gallery
    # match instead. Results are cached by image hash either way. The
    # on-device gallery is a dev-only convenience: the deployed backend
    # (PRODUCTION_MODE) always searches live and never falls back to it.
    use_live_search = True if PRODUCTION_MODE else str(req_data.get("live_search", "true")).lower() not in {"0", "false", "no", "off"}

    # Determine image input
    target_image_path = None
    temp_uploaded = False

    if "file" in request.files:
        uploaded = request.files["file"]
        ext = Path(uploaded.filename or "").suffix.lower() or ".jpg"
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            return jsonify({"success": False, "error": f"Unsupported file type: {ext}"}), 400
        temp_path = TEMP_DIR / f"temp_upload_{int(time.time()*1000)}{ext}"
        uploaded.save(str(temp_path))
        target_image_path = str(temp_path)
        temp_uploaded = True
    elif "image_path" in req_data:
        resolved = _resolve_scan_path(req_data["image_path"])
        if resolved:
            target_image_path = str(resolved)
    elif "image_base64" in req_data:
        b64_str = req_data["image_base64"]
        if "," in b64_str:
            b64_str = b64_str.split(",")[1]
        img_bytes = base64.b64decode(b64_str)
        temp_path = TEMP_DIR / f"temp_upload_{int(time.time()*1000)}.jpg"
        with open(temp_path, "wb") as f:
            f.write(img_bytes)
        target_image_path = str(temp_path)
        temp_uploaded = True

    if not target_image_path or not Path(target_image_path).exists():
        # Default fallback to first query image
        default_query = TEST_DIR / "alex_query.png"
        target_image_path = str(default_query)

    _sweep_temp_dir()
    try:
        t0 = time.perf_counter()

        # 1. Biometric Feature Extraction
        processor = FaceProcessor(mode=mode)
        face_data = processor.process(target_image_path, crop_output_dir=str(TEMP_DIR))

        # 2. Passive Presentation Attack Detection (Liveness)
        detector = LivenessDetector()
        liveness_data = detector.analyze(target_image_path)
        
        # 3. Social Discovery Search: genuine live reverse-image web search when
        # explicitly requested (consumes SerpAPI quota, cached by image hash),
        # otherwise the free on-device gallery match (0 API quota). The
        # on-device gallery is dev-only and never used in PRODUCTION_MODE.
        search_mode = "local"
        if use_live_search:
            try:
                searcher = WebSearcher()
                matches = searcher.search_reverse_image(face_data["cropped_image"])
                search_mode = "live"
            except Exception as live_err:
                if PRODUCTION_MODE:
                    return jsonify({
                        "success": False,
                        "error": f"Live web search is temporarily unavailable: {live_err}"
                    }), 502
                print(f"[!] Live search failed, falling back to local gallery: {live_err}")
                engine = LocalDiscoveryEngine(mode=mode)
                matches = engine.search_by_embedding(face_data["embedding"])
                search_mode = "local_fallback"
        else:
            engine = LocalDiscoveryEngine(mode=mode)
            matches = engine.search_by_embedding(face_data["embedding"])

        top_match = matches[0] if matches else {
            "title": "No verified match found",
            "source": "Unverified",
            "link": "https://unverified.identity",
            "similarity_score": 0.0,
            "confidence": "LOW (NO MATCH)"
        }

        # 4. Cryptographic Blockchain Anchoring
        explorer_url = None
        if chain_type == "solana":
            verifier = SolanaVerifier()
            chain_label = "Solana local persistent ledger (Ed25519 / SPL Memo)"
        elif chain_type == "evm":
            verifier = BlockchainVerifier()
            chain_label = "EVM (live RPC)" if verifier.is_live_chain() else "EVM local persistent ledger (ECDSA secp256k1)"
        else:
            verifier = MegaETHVerifier()
            chain_label = "MegaETH-style local persistent ledger (10ms Finality)"

        manifest = verifier.build_provenance_manifest(
            face_embedding=face_data["embedding"],
            post_url=top_match.get("link", ""),
            post_title=top_match.get("title", ""),
            confidence=face_data["confidence"],
            extra_metadata={
                "source": top_match.get("source"),
                "similarity": top_match.get("similarity_score", 1.0),
                "liveness_score": liveness_data["liveness_score"],
                "perceptual_hash": face_data.get("perceptual_hash", "0x0")
            }
        )

        tx_hash = verifier.record_on_chain(manifest)
        verify_res = verifier.verify_on_chain(tx_hash, manifest)
        if chain_type == "evm":
            explorer_url = verifier.explorer_tx_url(tx_hash)

        # 5. Issue W3C Verifiable Credential
        issuer = ZKCredentialIssuer()
        subj_name = top_match.get("title", "Verified Subject").split("]")[0].replace("[", "").strip()
        cred_bundle = issuer.issue_credential(
            subject_did=f"did:key:{tx_hash[2:34]}",
            biometric_embedding=face_data["embedding"],
            claimed_identity=subj_name,
            tx_hash=tx_hash,
            merkle_root=manifest["merkle_root"],
            liveness_score=liveness_data["liveness_score"]
        )

        total_elapsed = round(time.perf_counter() - t0, 3)

        response_payload = {
            "success": True,
            "chain": chain_type,
            "chain_label": chain_label,
            "total_elapsed_sec": total_elapsed,
            "face": {
                "confidence": face_data["confidence"],
                "bbox": face_data["bbox"],
                "embedding_dim": face_data["embedding_dim"],
                "perceptual_hash": face_data.get("perceptual_hash"),
                "geometry": face_data.get("geometry", {}),
                "engine": face_data.get("engine"),
                "cropped_image": f"/images/temp/{Path(face_data['cropped_image']).name}" if Path(face_data['cropped_image']).exists() else None
            },
            "liveness": {
                "is_live": liveness_data["is_live"],
                "liveness_score": liveness_data["liveness_score"],
                "status": liveness_data["status"],
                "metrics": liveness_data["metrics"]
            },
            "discovery": {
                "search_mode": search_mode,
                "top_match": top_match,
                "all_matches": matches[:4]
            },
            "blockchain": {
                "tx_hash": tx_hash,
                "merkle_root": manifest["merkle_root"],
                "validator": manifest["validator_address"],
                "signature": manifest["signature"],
                "verified": verify_res.get("verified", False),
                "block_number": verify_res.get("block_number") or verify_res.get("slot"),
                "block_time_ms": verify_res.get("block_time_ms", 400.0 if chain_type == "solana" else 1000.0),
                "eigenda_blob": manifest.get("eigenda_blob_commitment"),
                "is_live": chain_type == "evm" and explorer_url is not None,
                "explorer_url": explorer_url
            },
            "manifest": manifest,
            "verifiable_credential": cred_bundle["verifiable_credential"]
        }
        return jsonify(response_payload)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if temp_uploaded and target_image_path and Path(target_image_path).exists():
            try:
                os.remove(target_image_path)
            except Exception:
                pass

@app.route("/api/tamper", methods=["POST"])
def simulate_tamper():
    try:
        req = request.get_json() or {}
        manifest = req.get("manifest")
        tx_hash = req.get("tx_hash")
        chain_type = req.get("chain", "megaeth").lower()

        if not manifest or not tx_hash:
            return jsonify({"success": False, "error": "Manifest and tx_hash required"}), 400

        if chain_type == "solana":
            verifier = SolanaVerifier()
        elif chain_type == "evm":
            verifier = BlockchainVerifier()
        else:
            verifier = MegaETHVerifier()

        # The persisted ledger (loaded on verifier init) should already have
        # this tx from the original /api/scan call. Only seed a stand-in
        # record if it's genuinely missing (e.g. ledger file was cleared).
        if tx_hash not in verifier.ledger:
            verifier.ledger[tx_hash] = {
                "tx_hash": tx_hash,
                "signature": tx_hash,
                "block_number": 1,
                "slot": 1,
                "block_time": int(time.time()),
                "block_time_ms": 10.0,
                "merkle_root": manifest["merkle_root"],
                "eigenda_blob_commitment": manifest.get("eigenda_blob_commitment", ""),
                "validator": manifest["validator_address"],
                "manifest": manifest
            }

        tampered_manifest = json.loads(json.dumps(manifest))
        if chain_type == "evm":
            tampered_manifest["target_post"]["url"] = "https://malicious-counterfeit-profile.com/fake"
        else:
            tampered_manifest["metadata"]["post_url"] = "https://malicious-counterfeit-profile.com/fake"

        res = verifier.verify_on_chain(tx_hash, tampered_manifest)
        return jsonify({
            "tamper_detected": not res.get("verified", False),
            "status": "REJECTED_BY_BLOCKCHAIN" if not res.get("verified") else "TAMPER_FAILED",
            "verification_result": res
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"[*] Starting Lauffey Web Server on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
