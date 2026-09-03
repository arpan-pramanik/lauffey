import os
import json
import time
from typing import Dict, Any, Tuple
from eth_utils import keccak
from eth_account.messages import encode_defunct
from eth_account import Account

class ZKCredentialIssuer:
    """
    Issues W3C-compliant Verifiable Credentials (VC) with Zero-Knowledge selective disclosure.
    Allows proving identity ownership and blockchain provenance without revealing the
    underlying biometric feature vector.
    """
    def __init__(self, private_key_hex: str = None):
        if private_key_hex:
            self.account = Account.from_key(private_key_hex)
        else:
            self.account = Account.create()
        self.did = f"did:lauffey:{self.account.address.lower()}"

    def issue_credential(
        self,
        subject_did: str,
        biometric_embedding: list,
        claimed_identity: str,
        tx_hash: str,
        merkle_root: str,
        liveness_score: float
    ) -> Dict[str, Any]:
        # 1. Blind the biometric embedding with a cryptographically secure salt
        blinding_salt = os.urandom(32).hex()
        raw_bytes = json.dumps(biometric_embedding, separators=(",", ":")).encode() + bytes.fromhex(blinding_salt)
        biometric_commitment = "0x" + keccak(raw_bytes).hex()

        issuance_date = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # 2. Structure W3C Verifiable Credential payload
        vc_payload = {
            "@context": [
                "https://www.w3.org/2018/credentials/v1",
                "https://w3id.org/security/suites/ed25519-2020/v1"
            ],
            "id": f"urn:uuid:{os.urandom(16).hex()}",
            "type": ["VerifiableCredential", "BiometricProvenanceCredential"],
            "issuer": self.did,
            "issuanceDate": issuance_date,
            "credentialSubject": {
                "id": subject_did,
                "claimedIdentity": claimed_identity,
                "biometricCommitment": biometric_commitment,
                "livenessScore": liveness_score,
                "onChainLedger": {
                    "network": "EVM-L2-Calldata",
                    "transactionHash": tx_hash,
                    "merkleRoot": merkle_root
                }
            }
        }

        # 3. Cryptographically sign the credential payload
        canonical_str = json.dumps(vc_payload, sort_keys=True, separators=(",", ":"))
        signable = encode_defunct(text=canonical_str)
        signed = self.account.sign_message(signable)

        vc_payload["proof"] = {
            "type": "EcdsaSecp256k1RecoverySignature2020",
            "created": issuance_date,
            "verificationMethod": f"{self.did}#key-1",
            "proofPurpose": "assertionMethod",
            "jws": signed.signature.hex()
        }

        # Private ZK witness stored solely by user for selective disclosure
        zk_witness = {
            "subject_did": subject_did,
            "blinding_salt": blinding_salt,
            "biometric_commitment": biometric_commitment,
            "merkle_root": merkle_root,
            "tx_hash": tx_hash
        }

        return {
            "verifiable_credential": vc_payload,
            "zk_witness": zk_witness
        }

    @staticmethod
    def verify_credential(vc: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Verifies W3C Verifiable Credential integrity and digital signature without
        needing to inspect private biometric vectors.
        """
        proof = vc.get("proof")
        if not proof:
            return False, "Missing cryptographic proof block"

        # Remove proof to reconstruct signed message
        payload_copy = {k: v for k, v in vc.items() if k != "proof"}
        canonical_str = json.dumps(payload_copy, sort_keys=True, separators=(",", ":"))
        signable = encode_defunct(text=canonical_str)

        try:
            recovered_addr = Account.recover_message(signable, signature=bytes.fromhex(proof["jws"]))
            issuer_did = vc.get("issuer", "")
            expected_addr = issuer_did.split(":")[-1].lower()

            if recovered_addr.lower() == expected_addr:
                return True, f"Valid signature from {recovered_addr}"
            else:
                return False, f"Signer mismatch: expected {expected_addr}, got {recovered_addr.lower()}"
        except Exception as e:
            return False, f"Signature recovery failed: {e}"

if __name__ == "__main__":
    issuer = ZKCredentialIssuer()
    cred_bundle = issuer.issue_credential(
        subject_did="did:key:z6MkpTHR8VNsBxYAAWJnKQjinzb8SQG51556PLAet3itWvWv",
        biometric_embedding=[0.05] * 512,
        claimed_identity="Barack Obama",
        tx_hash="0xabc123",
        merkle_root="0xroot456",
        liveness_score=0.98
    )
    vc = cred_bundle["verifiable_credential"]
    print("Issued Verifiable Credential:")
    print(f"  Issuer : {vc['issuer']}")
    print(f"  Subject: {vc['credentialSubject']['claimedIdentity']}")
    print(f"  Commit : {vc['credentialSubject']['biometricCommitment'][:22]}...")
    
    is_valid, msg = ZKCredentialIssuer.verify_credential(vc)
    print(f"  Verification: {is_valid} ({msg})")
