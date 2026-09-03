import os
import time
import json
from typing import Dict, Any, List, Tuple
from eth_utils import keccak
from eth_account.messages import encode_defunct
from eth_account import Account

class MegaETHMerkleTree:
    """
    Binary Merkle Tree using Keccak-256 (EVM / MegaETH Native).
    Computes sibling inclusion proofs for real-time verification.
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
                combined = bytes.fromhex(left.replace("0x", "")) + bytes.fromhex(right.replace("0x", ""))
                parent = "0x" + keccak(combined).hex()
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
            c_bytes = bytes.fromhex(current.replace("0x", ""))
            s_bytes = bytes.fromhex(sibling.replace("0x", ""))
            if pos == "left":
                combined = s_bytes + c_bytes
            else:
                combined = c_bytes + s_bytes
            current = "0x" + keccak(combined).hex()
        return current.lower() == expected_root.lower()

class MegaETHVerifier:
    """
    MegaETH Real-Time EVM Attestation Engine (10ms Block Time / 100k+ TPS).
    Features in-memory state execution, EigenDA data availability commitments,
    Keccak-256 Merkle Provenance trees, and EIP-191 ECDSA secp256k1 signatures.
    """
    def __init__(self, private_key_hex: str = None):
        if private_key_hex:
            self.account = Account.from_key(private_key_hex)
        else:
            self.account = Account.create()
        self.validator_address = self.account.address
        self.ledger: Dict[str, Dict[str, Any]] = {}
        self.current_block = 10_450_200
        self.block_time_ms = 10.0  # MegaETH 10ms block interval

    def hash_biometric_embedding(self, embedding: list) -> str:
        data = json.dumps(embedding, separators=(",", ":")).encode("utf-8")
        return "0x" + keccak(data).hex()

    def hash_social_post(self, post_url: str, post_title: str, platform: str = "") -> str:
        record = {
            "url": post_url.strip().lower(),
            "title": post_title.strip(),
            "platform": platform.strip().lower()
        }
        data = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "0x" + keccak(data).hex()

    def build_provenance_manifest(
        self,
        face_embedding: list,
        post_url: str,
        post_title: str,
        confidence: float,
        extra_metadata: dict = None
    ) -> Dict[str, Any]:
        t_now_ns = time.time_ns()
        bio_hash = self.hash_biometric_embedding(face_embedding)
        post_hash = self.hash_social_post(post_url, post_title)

        meta = extra_metadata or {}
        temporal_data = {
            "timestamp_ns": t_now_ns,
            "validator": self.validator_address,
            "confidence": round(float(confidence), 4),
            "network": "MegaETH-Realtime-EVM",
            "block_time_ms": self.block_time_ms,
            "da_layer": "EigenDA",
            "liveness_score": meta.get("liveness_score", 1.0),
            "perceptual_hash": meta.get("perceptual_hash", "0x0")
        }
        temporal_hash = "0x" + keccak(json.dumps(temporal_data, sort_keys=True, separators=(",", ":")).encode("utf-8")).hex()

        # Pre-commitment signature
        pre_leaves = [bio_hash, post_hash, temporal_hash]
        temp_tree = MegaETHMerkleTree(pre_leaves)

        signable = encode_defunct(text=f"MegaETH-Attestation:{temp_tree.root}:{t_now_ns}")
        signed = self.account.sign_message(signable)
        sig_hex = signed.signature.hex()
        sig_hash = "0x" + keccak(bytes.fromhex(sig_hex.replace("0x", ""))).hex()

        # Build 4-leaf tree
        final_leaves = [bio_hash, post_hash, temporal_hash, sig_hash]
        tree = MegaETHMerkleTree(final_leaves)

        # EigenDA Blob Commitment Hash
        eigenda_blob_commitment = "0x" + keccak(
            bytes.fromhex(tree.root.replace("0x", "")) +
            bytes.fromhex(post_hash.replace("0x", "")) +
            str(t_now_ns).encode()
        ).hex()

        manifest = {
            "merkle_root": tree.root,
            "eigenda_blob_commitment": eigenda_blob_commitment,
            "leaves": {
                "biometric_leaf": bio_hash,
                "social_leaf": post_hash,
                "temporal_leaf": temporal_hash,
                "signature_leaf": sig_hash
            },
            "proofs": {
                "biometric_proof": tree.get_proof(0),
                "social_proof": tree.get_proof(1)
            },
            "validator_address": self.validator_address,
            "signature": sig_hex,
            "sign_message": f"MegaETH-Attestation:{temp_tree.root}:{t_now_ns}",
            "metadata": {
                "post_url": post_url,
                "post_title": post_title,
                "timestamp_ns": t_now_ns,
                "confidence": confidence,
                "blockchain": "MegaETH",
                "block_time_ms": self.block_time_ms,
                "da_layer": "EigenDA",
                **meta
            }
        }
        return manifest

    def record_on_chain(self, manifest: Dict[str, Any]) -> str:
        """
        Simulates in-memory MegaETH real-time calldata anchoring with 10ms block finality.
        """
        self.current_block += 1
        tx_hash = "0x" + os.urandom(32).hex()

        self.ledger[tx_hash] = {
            "tx_hash": tx_hash,
            "block_number": self.current_block,
            "block_time_ms": self.block_time_ms,
            "merkle_root": manifest["merkle_root"],
            "eigenda_blob_commitment": manifest["eigenda_blob_commitment"],
            "validator": manifest["validator_address"],
            "manifest": manifest
        }
        return tx_hash

    def verify_on_chain(self, tx_hash: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes real-time multi-layer verification on MegaETH.
        """
        record = self.ledger.get(tx_hash)
        if not record:
            return {"verified": False, "reason": "Transaction not found on MegaETH node"}

        # 1. On-chain Merkle Root Match
        if record["merkle_root"].lower() != manifest["merkle_root"].lower():
            return {"verified": False, "reason": "Merkle root mismatch with on-chain record"}

        # 2. EigenDA Blob Commitment Match
        if record["eigenda_blob_commitment"].lower() != manifest.get("eigenda_blob_commitment", "").lower():
            return {"verified": False, "reason": "EigenDA blob commitment mismatch"}

        # 3. Merkle Sibling Inclusion Proof
        reconstructed_post_hash = self.hash_social_post(
            manifest["metadata"]["post_url"],
            manifest["metadata"]["post_title"]
        )
        proof = manifest["proofs"]["social_proof"]
        is_proof_valid = MegaETHMerkleTree.verify_proof(reconstructed_post_hash, proof, record["merkle_root"])
        if not is_proof_valid:
            return {"verified": False, "reason": "Keccak-256 Merkle inclusion proof failed"}

        # 4. ECDSA secp256k1 Signature Recovery
        try:
            signable = encode_defunct(text=manifest["sign_message"])
            sig_bytes = bytes.fromhex(manifest["signature"].replace("0x", ""))
            recovered = Account.recover_message(signable, signature=sig_bytes)
            if recovered.lower() != manifest["validator_address"].lower():
                return {"verified": False, "reason": f"Signer mismatch: {recovered} vs {manifest['validator_address']}"}
        except Exception as e:
            return {"verified": False, "reason": f"ECDSA recovery failed: {e}"}

        return {
            "verified": True,
            "blockchain": "MegaETH",
            "block_number": record["block_number"],
            "block_time_ms": record["block_time_ms"],
            "merkle_root": record["merkle_root"],
            "eigenda_blob_commitment": record["eigenda_blob_commitment"],
            "recovered_signer": recovered,
            "tx_hash": tx_hash
        }

if __name__ == "__main__":
    verifier = MegaETHVerifier()
    print(f"MegaETH Real-Time Validator: {verifier.validator_address}")
    manifest = verifier.build_provenance_manifest(
        face_embedding=[0.1] * 128,
        post_url="https://x.com/BarackObama/status/1789721495817294812",
        post_title="Barack Obama post",
        confidence=0.98
    )
    tx = verifier.record_on_chain(manifest)
    print(f"Anchored in MegaETH Block {verifier.current_block} (10ms block time): {tx}")
    res = verifier.verify_on_chain(tx, manifest)
    print(f"Verification Result: {res}")
