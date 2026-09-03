import os
import sys
import unittest
import numpy as np
from eth_utils import keccak

from blockchain_verifier import MerkleTree, BlockchainVerifier
from face_processor import FaceProcessor
from web_searcher import WebSearcher
from local_engine import LocalDiscoveryEngine

class TestLauffeyPipeline(unittest.TestCase):
    def setUp(self):
        self.verifier = BlockchainVerifier()

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
        """Verify that the local biometric discovery engine accurately identifies test identities."""
        engine = LocalDiscoveryEngine()
        self.assertGreater(len(engine.registry), 0)

        # Query with unseen photo of Obama
        obama_query = "test_images/obama_query.jpg"
        if os.path.exists(obama_query):
            matches = engine.search_by_image(obama_query)
            self.assertGreater(len(matches), 0)
            top = matches[0]
            self.assertIn("Obama", top["title"])
            self.assertGreater(top["similarity_score"], 0.50)
            self.assertEqual(top["confidence"], "HIGH")

if __name__ == "__main__":
    unittest.main(verbosity=2)
