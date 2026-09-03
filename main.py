import os
import sys
import argparse
import time
from pathlib import Path

from face_processor import FaceProcessor
from web_searcher import WebSearcher
from blockchain_verifier import BlockchainVerifier

def print_header():
    print("=" * 70)
    print("  ATREUS: Biometric Face-to-Blockchain Verification Pipeline")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="Atreus: Face Scan to Blockchain Pipeline")
    parser.add_argument("--image", "-i", type=str, required=False, help="Path to input face image")
    parser.add_argument("--dry-run", action="store_true", help="Run with simulated search to conserve SerpAPI credits")
    parser.add_argument("--force-search", action="store_true", help="Bypass local search cache")
    args = parser.parse_args()

    print_header()

    if not args.image:
        # Check if sample image exists or create/prompt
        default_sample = Path("sample_face.jpg")
        if default_sample.exists():
            image_path = str(default_sample)
            print(f"[*] No --image provided. Defaulting to: {image_path}")
        else:
            print("[!] Error: Please provide an image path using --image <path/to/image.jpg>")
            sys.exit(1)
    else:
        image_path = args.image

    start_total_time = time.time()

    # ---------------------------------------------------------
    # STAGE 1: Face Detection & Encoding
    # ---------------------------------------------------------
    print("\n[STAGE 1/4] Biometric Face Processing...")
    t0 = time.time()
    face_proc = FaceProcessor()
    face_data = face_proc.process(image_path)
    t_face = time.time() - t0

    print(f"  [✓] Face localized & cropped: {face_data['cropped_image']}")
    print(f"  [✓] Feature Vector Dimension: {face_data['embedding_dim']}-d embedding")
    print(f"  [✓] Hardware Accelerator    : {face_data.get('gpu') or 'CPU (Fallback)'}")
    print(f"  [✓] Stage 1 elapsed         : {t_face:.2f}s")

    # ---------------------------------------------------------
    # STAGE 2: Reverse Visual Search & Social Discovery
    # ---------------------------------------------------------
    print("\n[STAGE 2/4] Social Media & Web Reverse Visual Search...")
    t0 = time.time()
    searcher = WebSearcher()

    if args.dry_run:
        print("  [*] Running in DRY-RUN mode (0 SerpAPI credits used).")
        matches = searcher.mock_search(face_data["cropped_image"])
    else:
        try:
            matches = searcher.search_reverse_image(face_data["cropped_image"], force=args.force_search)
        except Exception as e:
            print(f"  [!] Live search encountered an error: {e}")
            print("  [*] Falling back to synthetic matching to complete pipeline demonstration...")
            matches = searcher.mock_search(face_data["cropped_image"])

    t_search = time.time() - t0
    print(f"  [✓] Matches Discovered: {len(matches)}")
    print(f"  [✓] Stage 2 elapsed   : {t_search:.2f}s")

    if not matches:
        print("  [!] No matching social profiles found. Terminating pipeline.")
        sys.exit(0)

    # Display matches
    print("\n--- Discovered Social Content ---")
    for idx, match in enumerate(matches, 1):
        print(f"  [{idx}] {match.get('source', 'Web')}: {match.get('title')}")
        print(f"      URL: {match.get('link')}")

    # ---------------------------------------------------------
    # STAGE 3: Blockchain Cryptographic Anchoring
    # ---------------------------------------------------------
    print("\n[STAGE 3/4] Blockchain Cryptographic Anchoring...")
    t0 = time.time()
    verifier = BlockchainVerifier()

    # Anchor the top discovered post
    target_post = matches[0]
    fp_record = verifier.compute_fingerprint(
        face_embedding=face_data["embedding"],
        post_url=target_post.get("link", ""),
        post_title=target_post.get("title", ""),
        extra_metadata={"source": target_post.get("source"), "gpu": face_data.get("gpu")}
    )

    fingerprint_hash = fp_record["fingerprint_hash"]
    print(f"  [✓] Content SHA-256 Fingerprint: {fingerprint_hash}")

    tx_hash = verifier.record_on_chain(fingerprint_hash)
    t_chain = time.time() - t0
    print(f"  [✓] Ledger Transaction Hash    : {tx_hash}")
    print(f"  [✓] Calldata Payload Status    : Immutable On-Chain Record Created")
    print(f"  [✓] Stage 3 elapsed            : {t_chain:.2f}s")

    # ---------------------------------------------------------
    # STAGE 4: Ledger Re-Verification
    # ---------------------------------------------------------
    print("\n[STAGE 4/4] Independent Ledger Re-Verification...")
    t0 = time.time()
    verify_result = verifier.verify_on_chain(tx_hash, expected_hash=fingerprint_hash)
    t_verify = time.time() - t0

    if verify_result.get("verified"):
        print("  [✓] VERIFICATION SUCCESS:")
        print(f"      - Expected Hash : {verify_result['expected_hash']}")
        print(f"      - On-Chain Hash : {verify_result['stored_hash']}")
        print(f"      - Block / Status: {verify_result.get('block_number') or verify_result.get('status')}")
        print(f"      - Integrity     : 100% UNTAMPERED & VERIFIED")
    else:
        print("  [✗] VERIFICATION FAILED:")
        print(f"      - Error: {verify_result.get('error', 'Hash mismatch')}")

    total_time = time.time() - start_total_time
    print("\n" + "=" * 70)
    print(f"  PIPELINE COMPLETE (Total time: {total_time:.2f}s)")
    print("=" * 70)

if __name__ == "__main__":
    main()
