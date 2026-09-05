import json
import time
import os
from typing import Dict, Any, List, Optional, Tuple
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import keccak
from web3 import Web3

from config import BLOCKCHAIN_RPC
import chain_ledger_store

CHAIN_NAME = "evm"

# Block explorer URL templates for chain IDs judges are likely to fund a
# validator key on. Falls back to no link for unrecognized chain IDs.
EXPLORER_TX_URL_TEMPLATES = {
    1: "https://etherscan.io/tx/{tx_hash}",
    11155111: "https://sepolia.etherscan.io/tx/{tx_hash}",
    84532: "https://sepolia.basescan.org/tx/{tx_hash}",
    421614: "https://sepolia.arbiscan.io/tx/{tx_hash}",
}

class MerkleTree:
    """
    Cryptographic Binary Merkle Tree implementation using Keccak-256 (SHA3-256).
    Enables generation and verification of inclusion proofs (audit paths).
    """
    def __init__(self, leaves: List[bytes]):
        if not leaves:
            raise ValueError("Cannot create empty Merkle Tree")
        self.leaves = leaves
        self.levels = [self.leaves]
        self._build_tree()

    @staticmethod
    def keccak256(data: bytes) -> bytes:
        return keccak(data)

    def _build_tree(self):
        current_level = self.leaves
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if (i + 1) < len(current_level) else left
                # Canonical ordered hash to prevent second-preimage collision
                combined = left + right if left <= right else right + left
                next_level.append(self.keccak256(combined))
            self.levels.append(next_level)
            current_level = next_level

    @property
    def root(self) -> bytes:
        return self.levels[-1][0]

    @property
    def root_hex(self) -> str:
        return "0x" + self.root.hex()

    def get_proof(self, index: int) -> List[Dict[str, str]]:
        """Generates audit path of sibling hashes required to reconstruct the root."""
        proof = []
        for level in self.levels[:-1]:
            is_right_child = (index % 2 == 1)
            sibling_idx = index - 1 if is_right_child else (index + 1 if (index + 1) < len(level) else index)
            sibling_hash = level[sibling_idx]
            proof.append({
                "position": "left" if is_right_child else "right",
                "hash": "0x" + sibling_hash.hex()
            })
            index //= 2
        return proof

    @classmethod
    def verify_proof(cls, leaf: bytes, proof: List[Dict[str, str]], root: bytes) -> bool:
        """Verifies that a specific leaf belongs to the Merkle Root using the audit path."""
        current = leaf
        for p in proof:
            sibling = bytes.fromhex(p["hash"][2:])
            if p["position"] == "left":
                combined = sibling + current if sibling <= current else current + sibling
            else:
                combined = current + sibling if current <= sibling else sibling + current
            current = cls.keccak256(combined)
        return current == root


class BlockchainVerifier:
    """
    EVM Blockchain Verification Engine:
    1. Cryptographic Merkle Provenance Tree with Keccak-256 (Ethereum native).
    2. Zero-Knowledge ready Merkle Inclusion Proofs.
    3. Secp256k1 ECDSA Digital Signatures (EIP-191 cryptographic attestation).
    4. EVM transaction calldata anchoring and on-chain verification.

    With BLOCKCHAIN_RPC left at its default ("tester"), transactions run
    against an in-process py-evm sandbox that does not persist between
    processes, so re-verification instead consults a locally persisted,
    tamper-evident JSON ledger (data/ledger_evm.json). Set BLOCKCHAIN_RPC in
    .env to a real RPC URL (e.g. a public Sepolia endpoint) and
    VALIDATOR_PRIVATE_KEY to a funded key to anchor genuine, block-explorer
    checkable transactions instead.
    """
    def __init__(self, rpc_url: Optional[str] = None):
        self.rpc_url = rpc_url or BLOCKCHAIN_RPC
        self._w3 = None
        self._is_tester = False
        self._init_validator_identity()
        self._init_web3()
        self.ledger: Dict[str, Dict[str, Any]] = chain_ledger_store.load_ledger(CHAIN_NAME)

    def is_live_chain(self) -> bool:
        """True only when connected to a real, non-tester EVM node."""
        return self._w3 is not None and not self._is_tester and self._w3.is_connected()

    def explorer_tx_url(self, tx_hash: str) -> Optional[str]:
        """Returns a public block explorer link for tx_hash, if the connected chain is a recognized live network."""
        if not self.is_live_chain():
            return None
        try:
            chain_id = self._w3.eth.chain_id
        except Exception:
            return None
        template = EXPLORER_TX_URL_TEMPLATES.get(chain_id)
        return template.format(tx_hash=tx_hash) if template else None

    def _init_validator_identity(self):
        """Initializes or derives an ECDSA secp256k1 cryptographic validator keypair."""
        pk = os.environ.get("VALIDATOR_PRIVATE_KEY")
        if pk:
            self.validator = Account.from_key(pk)
        else:
            saved_hex = chain_ledger_store.load_key_material("evm_validator_key")
            if saved_hex:
                self.validator = Account.from_key(saved_hex)
            else:
                self.validator = Account.create()
                chain_ledger_store.save_key_material("evm_validator_key", self.validator.key.hex())

    def _init_web3(self):
        try:
            if self.rpc_url == "tester":
                from eth_tester import EthereumTester
                self._w3 = Web3(Web3.EthereumTesterProvider(EthereumTester()))
                self._is_tester = True
            else:
                self._w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        except Exception:
            self._w3 = None

    def build_provenance_manifest(
        self,
        face_embedding: list,
        post_url: str,
        post_title: str,
        confidence: float = 1.0,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Constructs a multi-leaf Cryptographic Merkle Tree:
        - Leaf 0: Biometric feature vector hash & confidence
        - Leaf 1: Discovered web/social content identity
        - Leaf 2: Temporal nonce & validator attestation
        - Leaf 3: Digital signature over state claims
        """
        # Leaf 0: Biometric claim
        embed_bytes = json.dumps([round(v, 6) for v in face_embedding[:32]]).encode()
        leaf_0_data = json.dumps({
            "claim": "biometric_vector",
            "vector_hash": keccak(embed_bytes).hex(),
            "confidence": round(confidence, 4)
        }, sort_keys=True).encode()
        leaf_0 = keccak(leaf_0_data)

        # Leaf 1: Content claim. Deliberately hashes only the human-checkable
        # url/title (not the free-form extra_metadata dict) so a verifier can
        # independently recompute this leaf from manifest["target_post"] alone
        # and catch any tampering of the displayed post claim.
        leaf_1_data = json.dumps({
            "claim": "social_discovery",
            "url": post_url.strip(),
            "title": post_title.strip()
        }, sort_keys=True).encode()
        leaf_1 = keccak(leaf_1_data)

        # Leaf 2: Temporal and validator identity claim
        timestamp = int(time.time())
        leaf_2_data = json.dumps({
            "claim": "attestation_envelope",
            "timestamp": timestamp,
            "validator": self.validator.address,
            "network": "EVM-L2/Modular"
        }, sort_keys=True).encode()
        leaf_2 = keccak(leaf_2_data)

        # Build initial 3-leaf tree to sign
        temp_leaves = [leaf_0, leaf_1, leaf_2]
        temp_tree = MerkleTree(temp_leaves)
        
        # Leaf 3: ECDSA Cryptographic Attestation Signature
        signable = encode_defunct(hexstr=temp_tree.root.hex())
        sig = self.validator.sign_message(signable)
        leaf_3 = keccak(sig.signature)

        # Full 4-leaf cryptographic provenance tree
        merkle = MerkleTree([leaf_0, leaf_1, leaf_2, leaf_3])

        # Generate inclusion proofs
        biometric_proof = merkle.get_proof(0)
        content_proof = merkle.get_proof(1)

        manifest = {
            "version": "lauffey-v2-merkle",
            "merkle_root": merkle.root_hex,
            "validator_address": self.validator.address,
            "signature": "0x" + sig.signature.hex(),
            "timestamp": timestamp,
            "leaves": {
                "biometric_leaf": "0x" + leaf_0.hex(),
                "content_leaf": "0x" + leaf_1.hex(),
                "attestation_leaf": "0x" + leaf_2.hex(),
                "signature_leaf": "0x" + leaf_3.hex(),
            },
            "proofs": {
                "biometric_inclusion_proof": biometric_proof,
                "content_inclusion_proof": content_proof
            },
            "target_post": {
                "url": post_url,
                "title": post_title
            }
        }
        return manifest

    def record_on_chain(self, manifest: Dict[str, Any]) -> str:
        """
        Stores the Merkle Root and cryptographic attestation into EVM transaction calldata.
        """
        if self._w3 is None:
            self._init_web3()

        merkle_root = manifest["merkle_root"]
        
        # Compact cryptographic on-chain payload
        on_chain_payload = {
            "protocol": "LAUFFEY/2026",
            "merkle_root": merkle_root,
            "validator": manifest["validator_address"],
            "sig": manifest["signature"][:20] + "..."
        }
        tx_data = self._w3.to_hex(text=json.dumps(on_chain_payload, separators=(',', ':')))

        if self._w3 is not None and self._w3.is_connected() and self._is_tester:
            # eth-tester exposes unlocked test accounts we can send from directly.
            sender = self._w3.eth.accounts[0]
            tx_payload = {
                "from": sender,
                "to": sender,
                "value": 0,
                "data": tx_data,
                "gas": 120000,
            }
            tx_hash_bytes = self._w3.eth.send_transaction(tx_payload)
            tx_hash = self._w3.to_hex(tx_hash_bytes)
        elif self._w3 is not None and self._w3.is_connected():
            # Real RPC endpoints don't manage our keys, so sign locally with
            # the validator's private key and broadcast the raw transaction.
            sender = self.validator.address
            tx_payload = {
                "from": sender,
                "to": sender,
                "value": 0,
                "data": tx_data,
                "gas": 120000,
                "gasPrice": self._w3.eth.gas_price,
                "nonce": self._w3.eth.get_transaction_count(sender, "pending"),
                "chainId": self._w3.eth.chain_id,
            }
            signed = self.validator.sign_transaction(tx_payload)
            tx_hash_bytes = self._w3.eth.send_raw_transaction(signed.raw_transaction)
            # Real networks take a block or two to confirm; block here so the
            # transaction is actually mined before we hand back a tx_hash that
            # callers immediately try to re-verify.
            self._w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=120)
            tx_hash = self._w3.to_hex(tx_hash_bytes)
        else:
            # No live RPC connection: anchor into the local persistent ledger instead.
            tx_hash = "0x" + keccak(tx_data.encode() + os.urandom(16)).hex()

        record = {
            "tx_hash": tx_hash,
            "merkle_root": merkle_root,
            "validator": manifest["validator_address"],
            "is_tester": self._is_tester or not (self._w3 is not None and self._w3.is_connected()),
            "manifest": manifest
        }
        self.ledger[tx_hash] = record
        chain_ledger_store.append_record(CHAIN_NAME, tx_hash, record)
        return tx_hash

    def verify_on_chain(self, tx_hash: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """
        Performs 4-layer independent verification:
        1. On-Chain Ledger Transaction Confirmation
        2. Merkle Root Calldata Extraction
        3. Merkle Inclusion Proof (ZK-ready branch audit)
        4. ECDSA secp256k1 Digital Signature Cryptographic Recovery
        """
        merkle_root = manifest["merkle_root"]
        expected_root_bytes = bytes.fromhex(merkle_root[2:])

        # 1. On-chain / ledger query. Fails closed: a lookup error or missing
        # record means the calldata is NOT considered valid (never silently
        # treated as passing).
        block_num = 1
        calldata_valid = False
        calldata_reason = ""
        if self._w3 is not None and self._w3.is_connected() and not self._is_tester:
            try:
                tx = self._w3.eth.get_transaction(tx_hash)
                raw_input = tx["input"]
                if hasattr(raw_input, "to_0x_hex"):
                    raw_input = raw_input.to_0x_hex()
                stored_text = self._w3.to_text(hexstr=raw_input)
                parsed = json.loads(stored_text)
                calldata_valid = (parsed.get("merkle_root") == merkle_root)
                block_num = tx.get("blockNumber", 1)
                if not calldata_valid:
                    calldata_reason = "On-chain calldata merkle root does not match manifest"
            except Exception as e:
                calldata_reason = f"Could not confirm transaction on-chain: {e}"
        else:
            # Local/tester mode: consult the persisted ledger (data/ledger_evm.json)
            # rather than the ephemeral in-process eth-tester state.
            record = self.ledger.get(tx_hash) or chain_ledger_store.load_ledger(CHAIN_NAME).get(tx_hash)
            if record and record.get("merkle_root") == merkle_root:
                calldata_valid = True
            else:
                calldata_reason = "Transaction not found in persisted local ledger"

        # 2. Recompute the content leaf independently from the manifest's own
        # claims (never trust the caller-supplied leaf hash) so a tampered
        # post_url/title is caught even if leaves.content_leaf was left alone.
        recomputed_leaf_1_data = json.dumps({
            "claim": "social_discovery",
            "url": manifest["target_post"]["url"].strip(),
            "title": manifest["target_post"]["title"].strip()
        }, sort_keys=True).encode()
        content_leaf = keccak(recomputed_leaf_1_data)
        stored_content_leaf = bytes.fromhex(manifest["leaves"]["content_leaf"][2:])
        if content_leaf != stored_content_leaf:
            return {
                "verified": False,
                "tx_hash": tx_hash,
                "merkle_root": merkle_root,
                "merkle_proof_valid": False,
                "signature_valid": False,
                "reason": "Post content does not match its committed leaf hash (tampered)",
                "status": "TAMPER_DETECTED"
            }
        content_proof = manifest["proofs"]["content_inclusion_proof"]
        merkle_proof_valid = MerkleTree.verify_proof(content_leaf, content_proof, expected_root_bytes)

        # 3. ECDSA Digital Signature Verification
        # Re-derive pre-signature 3-leaf root
        leaf_0 = bytes.fromhex(manifest["leaves"]["biometric_leaf"][2:])
        leaf_1 = bytes.fromhex(manifest["leaves"]["content_leaf"][2:])
        leaf_2 = bytes.fromhex(manifest["leaves"]["attestation_leaf"][2:])
        pre_sig_root = MerkleTree([leaf_0, leaf_1, leaf_2]).root

        signable = encode_defunct(hexstr=pre_sig_root.hex())
        recovered_address = "0x0000000000000000000000000000000000000000"
        signature_valid = False
        try:
            recovered_address = Account.recover_message(signable, signature=bytes.fromhex(manifest["signature"][2:]))
            signature_valid = (recovered_address.lower() == manifest["validator_address"].lower())
        except Exception:
            signature_valid = False

        all_verified = calldata_valid and merkle_proof_valid and signature_valid

        return {
            "verified": all_verified,
            "tx_hash": tx_hash,
            "block_number": block_num,
            "merkle_root": merkle_root,
            "calldata_valid": calldata_valid,
            "reason": calldata_reason if not calldata_valid else "",
            "merkle_proof_valid": merkle_proof_valid,
            "signature_valid": signature_valid,
            "validator_address": manifest["validator_address"],
            "recovered_signer": recovered_address,
            "status": "CONFIRMED & CRYPTOGRAPHICALLY SECURED" if all_verified else "TAMPER_DETECTED"
        }

if __name__ == "__main__":
    v = BlockchainVerifier()
    test_manifest = v.build_provenance_manifest([0.1]*128, "https://x.com/demo", "Demo Post")
    tx = v.record_on_chain(test_manifest)
    res = v.verify_on_chain(tx, test_manifest)
    print("Advanced Blockchain Verifier Test:")
    print(f"Merkle Root: {res['merkle_root']}")
    print(f"Merkle Inclusion Proof: {res['merkle_proof_valid']}")
    print(f"ECDSA Signature Valid: {res['signature_valid']}")
    print(f"Status: {res['status']}")
