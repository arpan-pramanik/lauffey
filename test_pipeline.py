import os
import sys
import json
import unittest
from pathlib import Path
import numpy as np
from eth_utils import keccak

from blockchain_verifier import MerkleTree, BlockchainVerifier
from face_processor import FaceProcessor
from web_searcher import WebSearcher
from local_engine import LocalDiscoveryEngine

class TestLauffeyPipeline(unittest.TestCase):
    def setUp(self):
        # Force the local in-memory tester chain regardless of any
        # BLOCKCHAIN_RPC configured in .env, so tests stay fast and
        # deterministic instead of submitting real transactions.
        self.verifier = BlockchainVerifier(rpc_url="tester")

    def test_01_merkle_tree_integrity(self):
        """Verify binary Merkle tree construction and inclusion proof verification."""
        leaves = [keccak(f"leaf_{i}".encode()) for i in range(4)]
        tree = MerkleTree(leaves)
        root = tree.root

        # Test valid inclusion proof for leaf 1
        proof_1 = tree.get_proof(1)
        self.assertTrue(MerkleTree.verify_proof(leaves[1], proof_1, root))

        # Test valid inclusion proof for leaf 3
        proof_3 = tree.get_proof(3)
        self.assertTrue(MerkleTree.verify_proof(leaves[3], proof_3, root))

    def test_02_merkle_tamper_detection(self):
        """Verify that altering even a single bit of a leaf causes proof verification to fail."""
        leaves = [keccak(f"leaf_{i}".encode()) for i in range(4)]
        tree = MerkleTree(leaves)
        root = tree.root
        proof_0 = tree.get_proof(0)

        # Altered leaf
        tampered_leaf = keccak(b"tampered_data")
        self.assertFalse(MerkleTree.verify_proof(tampered_leaf, proof_0, root))

    def test_03_ecdsa_signature_verification(self):
        """Verify that EIP-191 ECDSA signatures are mathematically recoverable."""
        manifest = self.verifier.build_provenance_manifest(
            face_embedding=[0.05] * 128,
            post_url="https://x.com/verified/status/100",
            post_title="Identity Test Post"
        )
        tx_hash = self.verifier.record_on_chain(manifest)
        result = self.verifier.verify_on_chain(tx_hash, manifest)

        self.assertTrue(result["verified"])
        self.assertTrue(result["signature_valid"])
        self.assertTrue(result["merkle_proof_valid"])
        self.assertEqual(result["status"], "CONFIRMED & CRYPTOGRAPHICALLY SECURED")

    def test_04_tampered_manifest_rejection(self):
        """Verify that tampering with manifest post data fails cryptographic verification."""
        manifest = self.verifier.build_provenance_manifest(
            face_embedding=[0.05] * 128,
            post_url="https://x.com/verified/status/100",
            post_title="Original Post Title"
        )
        tx_hash = self.verifier.record_on_chain(manifest)

        # Tamper: Attacker tries to claim a different URL with the same Merkle proof
        tampered_manifest = dict(manifest)
        tampered_manifest["leaves"] = dict(manifest["leaves"])
        tampered_manifest["leaves"]["content_leaf"] = "0x" + keccak(b"https://evil.com/fake_post").hex()

        result = self.verifier.verify_on_chain(tx_hash, tampered_manifest)
        self.assertFalse(result["verified"])
        self.assertFalse(result["merkle_proof_valid"])
        self.assertEqual(result["status"], "TAMPER_DETECTED")

    def test_05_mock_web_searcher(self):
        """Verify that the searcher produces well-structured social results in test mode."""
        searcher = WebSearcher()
        results = searcher.mock_search("test_portrait.jpg")
        self.assertGreater(len(results), 0)
        self.assertIn("link", results[0])
        self.assertIn("title", results[0])

    def test_06_on_device_biometric_discovery_engine(self):
        """Verify that the local biometric discovery engine accurately identifies identities dynamically."""
        engine = LocalDiscoveryEngine()
        self.assertGreater(len(engine.registry), 0)

        # Test dynamic matching across all available query images in test_images/
        test_dir = Path("test_images")
        queries = sorted([
            f for f in test_dir.iterdir()
            if f.is_file() and f.suffix.lower() in {".jpg", ".png", ".jpeg"} and not f.name.startswith("temp_")
        ])
        self.assertGreater(len(queries), 0)

        for q in queries[:3]:
            matches = engine.search_by_image(str(q))
            self.assertGreater(len(matches), 0)
            top = matches[0]
            self.assertGreater(top["similarity_score"], 0.35)
            self.assertIn("HIGH", top["confidence"])

        # Test dynamic runtime registration of a novel identity
        first_img = str(queries[0])
        novel_profile = engine.register_identity(
            image_path=first_img,
            name="Novel Registered Test Subject",
            source="Test Suite Registry",
            link="https://test.suite/novel_subject"
        )
        self.assertEqual(novel_profile["name"], "Novel Registered Test Subject")

        # Verify that querying it matches the newly registered record
        matches = engine.search_by_image(first_img)
        matching_titles = [m["title"] for m in matches if m["similarity_score"] > 0.90]
        self.assertTrue(any("Novel Registered Test Subject" in t for t in matching_titles))

        # Cleanup registered file
        registered_path = Path(novel_profile["image"])
        if registered_path.exists():
            registered_path.unlink()

    def test_07_passive_liveness_detection(self):
        """Verify presentation attack detection on face portraits."""
        from liveness_detector import LivenessDetector
        detector = LivenessDetector()
        res = detector.analyze("test_images/obama_query.jpg")
        self.assertTrue(res["is_live"])
        self.assertGreater(res["liveness_score"], 0.50)
        self.assertEqual(res["status"], "GENUINE_LIVE_SUBJECT")

    def test_08_w3c_verifiable_credential(self):
        """Verify W3C Verifiable Credential issuance, cryptographic audit, and tamper detection."""
        from zk_credential import ZKCredentialIssuer
        issuer = ZKCredentialIssuer()
        bundle = issuer.issue_credential(
            subject_did="did:key:test_subject_123",
            biometric_embedding=[0.05] * 128,
            claimed_identity="Test Subject",
            tx_hash="0x123abc",
            merkle_root="0xroot789",
            liveness_score=0.95
        )
        vc = bundle["verifiable_credential"]
        
        # Valid verification
        is_valid, _ = ZKCredentialIssuer.verify_credential(vc)
        self.assertTrue(is_valid)

        # Tampered verification
        tampered_vc = json.loads(json.dumps(vc))
        tampered_vc["credentialSubject"]["claimedIdentity"] = "Impersonator"
        is_tampered_valid, _ = ZKCredentialIssuer.verify_credential(tampered_vc)
        self.assertFalse(is_tampered_valid)

    def test_09_solana_merkle_and_ed25519_verification(self):
        """Verify Solana SHA-256 Merkle tree and Ed25519 signature attestation."""
        from solana_verifier import SolanaVerifier
        sol = SolanaVerifier()
        manifest = sol.build_provenance_manifest(
            face_embedding=[0.05] * 128,
            post_url="https://x.com/verified/status/123",
            post_title="Verified post",
            confidence=0.99
        )
        tx_sig = sol.record_on_chain(manifest)
        self.assertIn(len(tx_sig), [87, 88])  # Base58 64-byte signature is 87-88 chars
        res = sol.verify_on_chain(tx_sig, manifest)
        self.assertTrue(res["verified"])
        self.assertEqual(res["blockchain"], "Solana")

    def test_10_solana_tamper_detection(self):
        """Verify that tampering with any Solana payload fails cryptographic verification."""
        from solana_verifier import SolanaVerifier
        sol = SolanaVerifier()
        manifest = sol.build_provenance_manifest(
            face_embedding=[0.05] * 128,
            post_url="https://x.com/verified/status/123",
            post_title="Verified post",
            confidence=0.99
        )
        tx_sig = sol.record_on_chain(manifest)
        
        # Tamper with post URL
        tampered = json.loads(json.dumps(manifest))
        tampered["metadata"]["post_url"] = "https://tampered.fake/link"
        res = sol.verify_on_chain(tx_sig, tampered)
        self.assertFalse(res["verified"])

    def test_11_megaeth_realtime_merkle_and_eigenda(self):
        """Verify MegaETH real-time 10ms block execution and EigenDA blob attestation."""
        from megaeth_verifier import MegaETHVerifier
        mega = MegaETHVerifier()
        manifest = mega.build_provenance_manifest(
            face_embedding=[0.05] * 128,
            post_url="https://x.com/verified/status/456",
            post_title="Verified MegaETH post",
            confidence=0.99
        )
        tx_hash = mega.record_on_chain(manifest)
        self.assertTrue(tx_hash.startswith("0x"))
        res = mega.verify_on_chain(tx_hash, manifest)
        self.assertTrue(res["verified"])
        self.assertEqual(res["blockchain"], "MegaETH")
        self.assertEqual(res["block_time_ms"], 10.0)

    def test_12_megaeth_tamper_detection(self):
        """Verify that tampering with any MegaETH claim fails cryptographic verification."""
        from megaeth_verifier import MegaETHVerifier
        mega = MegaETHVerifier()
        manifest = mega.build_provenance_manifest(
            face_embedding=[0.05] * 128,
            post_url="https://x.com/verified/status/456",
            post_title="Verified MegaETH post",
            confidence=0.99
        )
        tx_hash = mega.record_on_chain(manifest)
        
        # Tamper with post title
        tampered = json.loads(json.dumps(manifest))
        tampered["metadata"]["post_title"] = "Counterfeit title"
        res = mega.verify_on_chain(tx_hash, tampered)
        self.assertFalse(res["verified"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
