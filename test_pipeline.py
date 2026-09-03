import os
import sys
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

if __name__ == "__main__":
    unittest.main(verbosity=2)
