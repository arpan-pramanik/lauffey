import sys
import json
import argparse
from pathlib import Path
from blockchain_verifier import MerkleTree, BlockchainVerifier
from solana_verifier import SolanaVerifier
from megaeth_verifier import MegaETHVerifier

def _post_url(manifest: dict) -> str:
    if "target_post" in manifest:
        return manifest["target_post"].get("url", "")
    return manifest.get("metadata", {}).get("post_url", "")

def verify_receipt_file(receipt_path: str):
    path = Path(receipt_path)
    if not path.exists():
        print(f"[!] Receipt file not found: {receipt_path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    manifest = data.get("manifest")
    tx_hash = data.get("tx_hash")
    blockchain = (data.get("blockchain") or "").lower()

    if not manifest or not tx_hash:
        print("[!] Invalid receipt format: missing manifest or tx_hash")
        sys.exit(1)

    print("=" * 70)
    print("  LAUFFEY: Independent Receipt Cryptographic Verifier")
    print("=" * 70)
    print(f"[*] Inspecting Receipt: {path.name}")
    print(f"[*] Blockchain        : {data.get('blockchain', 'EVM')}")
    print(f"[*] Target Post URL   : {_post_url(manifest)}")
    print(f"[*] Claimed Merkle Root: {manifest.get('merkle_root')}")
    print(f"[*] Ledger TX Hash     : {tx_hash}")

    # Dispatch to the verifier that actually understands this receipt's
    # manifest shape and ledger — each chain's manifest/leaf fields differ,
    # so always using the EVM verifier silently mis-verifies non-EVM receipts.
    if blockchain == "solana":
        verifier = SolanaVerifier()
    elif blockchain == "megaeth":
        verifier = MegaETHVerifier()
    else:
        verifier = BlockchainVerifier()
    result = verifier.verify_on_chain(tx_hash, manifest)

    print("\n--- Cryptographic Audit Report ---")
    print(f"  [✓] On-Chain Merkle Root Match : {result.get('merkle_root') == manifest.get('merkle_root')}")
    if "merkle_proof_valid" in result:
        print(f"  [✓] Merkle Inclusion Proof     : {result.get('merkle_proof_valid')}")
    if "signature_valid" in result:
        print(f"  [✓] Validator Signature        : {result.get('signature_valid')} (Signer: {result.get('recovered_signer')})")
    print(f"  [✓] Ledger Finality Status     : {result.get('status', result.get('reason'))}")

    if result.get("verified"):
        print("\n[SUCCESS] The receipt is 100% UNTAMPERED and cryptographically proven.")
    else:
        print(f"\n[FAILURE] TAMPER DETECTED: {result.get('reason', 'Receipt does not match ledger state.')}")

def main():
    parser = argparse.ArgumentParser(description="Independently verify a Lauffey provenance receipt JSON")
    parser.add_argument("--receipt", "-r", type=str, required=True, help="Path to provenance receipt JSON file")
    args = parser.parse_args()
    verify_receipt_file(args.receipt)

if __name__ == "__main__":
    main()
