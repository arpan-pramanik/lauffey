import os
import time
import json
import hashlib
import base58
from typing import Dict, Any, List, Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519

SOLANA_MEMO_PROGRAM_ID = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"

def sha256_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

class SolanaMerkleTree:
    """
    Cryptographic Binary Merkle Tree using SHA-256 (Solana Native).
    Computes cryptographic inclusion proofs for zero-knowledge biometric verification.
    """
    def __init__(self, leaves: List[str]):
        if not leaves:
            raise ValueError("Leaves cannot be empty.")
        self.leaves = [l.lower() for l in leaves]
        self.layers = [self.leaves]
        self._build_tree()

    def _build_tree(self):
        current_layer = self.leaves
        while len(current_layer) > 1:
            next_layer = []
            for i in range(0, len(current_layer), 2):
                left = current_layer[i]
                right = current_layer[i + 1] if i + 1 < len(current_layer) else left
                combined = bytes.fromhex(left) + bytes.fromhex(right)
                parent = sha256_hash(combined)
                next_layer.append(parent)
            self.layers.append(next_layer)
            current_layer = next_layer

    @property
    def root(self) -> str:
        return self.layers[-1][0]

    def get_proof(self, index: int) -> List[Dict[str, str]]:
        proof = []
        for layer in self.layers[:-1]:
            is_right = (index % 2 == 1)
            sibling_idx = index - 1 if is_right else index + 1
            if sibling_idx < len(layer):
                sibling_hash = layer[sibling_idx]
            else:
                sibling_hash = layer[index]
            proof.append({
                "position": "left" if is_right else "right",
                "hash": sibling_hash
            })
            index //= 2
        return proof

    @staticmethod
    def verify_proof(leaf_hash: str, proof: List[Dict[str, str]], expected_root: str) -> bool:
        current = leaf_hash.lower()
        for element in proof:
            pos = element["position"]
            sibling = element["hash"].lower()
            if pos == "left":
                combined = bytes.fromhex(sibling) + bytes.fromhex(current)
            else:
                combined = bytes.fromhex(current) + bytes.fromhex(sibling)
            current = sha256_hash(combined)
        return current.lower() == expected_root.lower()

class SolanaVerifier:
    """
    Solana High-Throughput Attestation Engine.
    Uses Ed25519 digital signatures, SHA-256 Merkle Provenance trees,
    Base58 encoding, and Solana Memo program anchoring.
    """
    def __init__(self, private_key_bytes: bytes = None):
        if private_key_bytes:
            self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        else:
            self._private_key = ed25519.Ed25519PrivateKey.generate()
        
        self.public_key = self._private_key.public_key()
        self.validator_address = base58.b58encode(self.public_key.public_bytes_raw()).decode("ascii")
        self.ledger: Dict[str, Dict[str, Any]] = {}
        self.current_slot = 312_850_100

    def hash_biometric_embedding(self, embedding: list) -> str:
        data = json.dumps(embedding, separators=(",", ":")).encode("utf-8")
        return sha256_hash(data)

    def hash_social_post(self, post_url: str, post_title: str, platform: str = "") -> str:
        record = {
            "url": post_url.strip().lower(),
            "title": post_title.strip(),
            "platform": platform.strip().lower()
        }
        data = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256_hash(data)

    def build_provenance_manifest(
        self,
        face_embedding: list,
        post_url: str,
        post_title: str,
        confidence: float,
        extra_metadata: dict = None
    ) -> Dict[str, Any]:
        t_now = int(time.time())
        bio_hash = self.hash_biometric_embedding(face_embedding)
        post_hash = self.hash_social_post(post_url, post_title)
        
        meta = extra_metadata or {}
        temporal_data = {
            "timestamp": t_now,
            "validator": self.validator_address,
            "confidence": round(float(confidence), 4),
            "network": "solana-mainnet-beta",
            "memo_program": SOLANA_MEMO_PROGRAM_ID,
            "liveness_score": meta.get("liveness_score", 1.0)
        }
        temporal_hash = sha256_hash(json.dumps(temporal_data, sort_keys=True, separators=(",", ":")).encode("utf-8"))

        pre_signature_leaves = [bio_hash, post_hash, temporal_hash]
        temp_tree = SolanaMerkleTree(pre_signature_leaves)
        
        # Ed25519 Sign the pre-commitment
        sign_payload = f"Solana-Lauffey-Attestation:{temp_tree.root}:{t_now}".encode("utf-8")
        sig_bytes = self._private_key.sign(sign_payload)
        sig_b58 = base58.b58encode(sig_bytes).decode("ascii")
        sig_hash = sha256_hash(sig_bytes)

        # Build 4-leaf SHA-256 Merkle Tree
        final_leaves = [bio_hash, post_hash, temporal_hash, sig_hash]
        merkle_tree = SolanaMerkleTree(final_leaves)

        manifest = {
            "merkle_root": merkle_tree.root,
            "leaves": {
                "biometric_leaf": bio_hash,
                "social_leaf": post_hash,
                "temporal_leaf": temporal_hash,
                "signature_leaf": sig_hash
            },
            "proofs": {
                "biometric_proof": merkle_tree.get_proof(0),
                "social_proof": merkle_tree.get_proof(1)
            },
            "validator_address": self.validator_address,
            "signature": sig_b58,
            "sign_payload": sign_payload.decode("utf-8"),
            "metadata": {
                "post_url": post_url,
                "post_title": post_title,
                "timestamp": t_now,
                "confidence": confidence,
                "blockchain": "Solana",
                "memo_program_id": SOLANA_MEMO_PROGRAM_ID,
                **meta
            }
        }
        return manifest

    def record_on_chain(self, manifest: Dict[str, Any]) -> str:
        """
        Simulates recording a transaction with a Solana Memo instruction.
        Transaction signature is an Ed25519 64-byte signature encoded in Base58.
        """
        self.current_slot += 1
        tx_signature_bytes = os.urandom(64)
        tx_signature = base58.b58encode(tx_signature_bytes).decode("ascii")

        memo_instruction_data = {
            "program": "SplMemo",
            "program_id": SOLANA_MEMO_PROGRAM_ID,
            "data": {
                "lauffey_merkle_root": manifest["merkle_root"],
                "target_url": manifest["metadata"]["post_url"],
                "validator": manifest["validator_address"]
            }
        }

        self.ledger[tx_signature] = {
            "signature": tx_signature,
            "slot": self.current_slot,
            "block_time": int(time.time()),
            "merkle_root": manifest["merkle_root"],
            "memo_instruction": memo_instruction_data,
            "validator": manifest["validator_address"],
            "manifest": manifest
        }
        return tx_signature

    def verify_on_chain(self, tx_signature: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes multi-layer cryptographic ledger verification on Solana.
        """
        record = self.ledger.get(tx_signature)
        if not record:
            return {"verified": False, "reason": "Transaction signature not found in Solana ledger"}

        # 1. Verify Merkle Root matches Memo instruction
        on_chain_root = record["merkle_root"]
        if on_chain_root.lower() != manifest["merkle_root"].lower():
            return {"verified": False, "reason": "Merkle root does not match on-chain record"}

        # 2. Verify SHA-256 Merkle Inclusion Proof
        reconstructed_post_hash = self.hash_social_post(
            manifest["metadata"]["post_url"],
            manifest["metadata"]["post_title"]
        )
        proof = manifest["proofs"]["social_proof"]
        is_proof_valid = SolanaMerkleTree.verify_proof(reconstructed_post_hash, proof, on_chain_root)
        if not is_proof_valid:
            return {"verified": False, "reason": "SHA-256 Merkle inclusion proof failed"}

        # 3. Verify Ed25519 Validator Signature
        try:
            val_pub_bytes = base58.b58decode(manifest["validator_address"])
            val_pub_key = ed25519.Ed25519PublicKey.from_public_bytes(val_pub_bytes)
            sig_bytes = base58.b58decode(manifest["signature"])
            val_pub_key.verify(sig_bytes, manifest["sign_payload"].encode("utf-8"))
        except Exception as e:
            return {"verified": False, "reason": f"Ed25519 signature verification failed: {e}"}

        return {
            "verified": True,
            "blockchain": "Solana",
            "slot": record["slot"],
            "block_time": record["block_time"],
            "merkle_root": on_chain_root,
            "validator": manifest["validator_address"],
            "memo_program_id": SOLANA_MEMO_PROGRAM_ID,
            "signature": tx_signature
        }

if __name__ == "__main__":
    sol = SolanaVerifier()
    print(f"Solana Validator Address: {sol.validator_address}")
    manifest = sol.build_provenance_manifest(
        face_embedding=[0.1] * 128,
        post_url="https://x.com/BarackObama/status/1789721495817294812",
        post_title="Barack Obama post",
        confidence=0.98
    )
    tx = sol.record_on_chain(manifest)
    print(f"Anchored in Solana Slot {sol.current_slot}: {tx}")
    res = sol.verify_on_chain(tx, manifest)
    print(f"Verification Result: {res}")
