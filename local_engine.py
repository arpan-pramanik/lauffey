import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np

from config import BASE_DIR, BIOMETRIC_ACCURACY_MODE
from face_processor import FaceProcessor

PROFILES_JSON = BASE_DIR / "data" / "profiles.json"

class LocalDiscoveryEngine:
    """
    Highest-Accuracy on-device biometric search engine.
    Supports:
    - 'high' mode: SOTA RetinaFace + ArcFace 512-d embeddings
    - 'fast' mode: OpenCV YuNet + SFace 128-d embeddings
    Matches queries via normalized cosine similarity with zero API quota consumption.
    """
    def __init__(self, mode: Optional[str] = None, profiles_path: Optional[Path] = None):
        self.mode = mode or BIOMETRIC_ACCURACY_MODE
        self.profiles_path = profiles_path or PROFILES_JSON
        self.face_processor = FaceProcessor(mode=self.mode)
        
        if self.mode == "high":
            self.cache_file = BASE_DIR / "data" / "embeddings_cache_512.json"
            self.expected_dim = 512
        else:
            self.cache_file = BASE_DIR / "data" / "embeddings_cache_128.json"
            self.expected_dim = 128

        self.registry = []
        self._load_and_index()

    def _load_and_index(self):
        if not self.profiles_path.exists():
            return

        with open(self.profiles_path, "r", encoding="utf-8") as f:
            profiles = json.load(f)

        cached_embeddings = {}
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as cf:
                    cached_embeddings = json.load(cf)
            except Exception:
                cached_embeddings = {}

        updated_cache = False
        self.registry = []

        for p in profiles:
            img_rel = p.get("image", "")
            img_path = BASE_DIR / img_rel
            if not img_path.exists():
                continue

            if img_rel in cached_embeddings and len(cached_embeddings[img_rel]) == self.expected_dim:
                emb = cached_embeddings[img_rel]
            else:
                try:
                    proc_res = self.face_processor.process(str(img_path))
                    emb = proc_res["embedding"]
                    if len(emb) == self.expected_dim:
                        cached_embeddings[img_rel] = emb
                        updated_cache = True
                except Exception as e:
                    print(f"[!] Error indexing {img_rel}: {e}")
                    continue

            norm_emb = np.array(emb, dtype=np.float32)
            norm = np.linalg.norm(norm_emb)
            if norm > 0:
                norm_emb = norm_emb / norm

            self.registry.append({
                "profile": p,
                "embedding": norm_emb,
                "dim": len(norm_emb)
            })

        if updated_cache:
            with open(self.cache_file, "w", encoding="utf-8") as cf:
                json.dump(cached_embeddings, cf)

    def search_by_embedding(self, query_embedding: list) -> List[Dict[str, Any]]:
        """
        Executes vector similarity search against registered identities.
        """
        if not self.registry:
            return []

        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        scored = []
        for item in self.registry:
            db_vec = item["embedding"]
            if len(q_vec) != len(db_vec):
                continue
            cos_sim = float(np.dot(q_vec, db_vec))
            scored.append((cos_sim, item["profile"]))

        # Sort descending by similarity
        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, prof in scored:
            confidence_label = "HIGH (MATCH)" if score > 0.40 else ("MEDIUM" if score > 0.25 else "LOW (NO MATCH)")
            engine_label = f"ArcFace-512 ({self.mode})" if self.expected_dim == 512 else f"SFace-128 ({self.mode})"
            results.append({
                "title": f"[{prof['name']}] {prof['title']}",
                "link": prof["link"],
                "source": prof["source"],
                "thumbnail": prof.get("thumbnail", ""),
                "similarity_score": round(score, 4),
                "confidence": confidence_label,
                "vector_dim": len(q_vec),
                "engine": engine_label
            })

        return results

    def search_by_image(self, image_path: str) -> List[Dict[str, Any]]:
        proc = self.face_processor.process(image_path)
        return self.search_by_embedding(proc["embedding"])

if __name__ == "__main__":
    engine = LocalDiscoveryEngine(mode="high")
    print(f"Indexed {len(engine.registry)} profiles in ArcFace-512 database.")
    query_img = str(BASE_DIR / "test_images" / "obama_query.jpg")
    matches = engine.search_by_image(query_img)
    print("\nArcFace 512-d Query Matches:")
    for idx, m in enumerate(matches, 1):
        print(f"  [{idx}] {m['source']}: {m['title']}")
        print(f"      Similarity: {m['similarity_score']} ({m['confidence']}) -> {m['link']}")
