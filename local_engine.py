import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np

from config import BASE_DIR
from face_processor import FaceProcessor

PROFILES_JSON = BASE_DIR / "data" / "profiles.json"
CACHE_FILE = BASE_DIR / "data" / "embeddings_cache.json"

class LocalDiscoveryEngine:
    """
    High-speed, 100% on-device biometric search engine.
    Matches input face feature embeddings against a local gallery of profiles
    using cosine similarity. Consumes ZERO API credits.
    """
    def __init__(self, profiles_path: Optional[Path] = None):
        self.profiles_path = profiles_path or PROFILES_JSON
        self.face_processor = FaceProcessor()
        self.registry = []
        self._load_and_index()

    def _load_and_index(self):
        if not self.profiles_path.exists():
            print(f"[!] Warning: Local profiles database not found at {self.profiles_path}")
            return

        with open(self.profiles_path, "r", encoding="utf-8") as f:
            profiles = json.load(f)

        cached_embeddings = {}
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as cf:
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

            # Check if embedding already computed in cache
            if img_rel in cached_embeddings:
                emb = cached_embeddings[img_rel]
            else:
                try:
                    proc_res = self.face_processor.process(str(img_path))
                    emb = proc_res["embedding"]
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
                "embedding": norm_emb
            })

        if updated_cache:
            with open(CACHE_FILE, "w", encoding="utf-8") as cf:
                json.dump(cached_embeddings, cf)

    def search_by_embedding(self, query_embedding: list, min_similarity: float = 0.20) -> List[Dict[str, Any]]:
        """
        Executes sub-millisecond vector similarity search against registered identities.
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
            cos_sim = float(np.dot(q_vec, db_vec))
            scored.append((cos_sim, item["profile"]))

        # Sort by similarity descending
        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, prof in scored:
            confidence_label = "HIGH" if score > 0.40 else ("MEDIUM" if score > 0.25 else "LOW")
            results.append({
                "title": f"[{prof['name']}] {prof['title']}",
                "link": prof["link"],
                "source": prof["source"],
                "thumbnail": prof.get("thumbnail", ""),
                "similarity_score": round(score, 4),
                "confidence": confidence_label,
                "engine": "On-Device Biometric Matcher"
            })

        return results

    def search_by_image(self, image_path: str) -> List[Dict[str, Any]]:
        """Convenience method to process an image and search on-device."""
        proc = self.face_processor.process(image_path)
        return self.search_by_embedding(proc["embedding"])

if __name__ == "__main__":
    engine = LocalDiscoveryEngine()
    print(f"Indexed {len(engine.registry)} profiles on-device.")
    # Test query with Obama query image
    query_img = str(BASE_DIR / "test_images" / "obama_query.jpg")
    print(f"\nTesting on-device search with: {query_img}")
    t0 = time.perf_counter()
    matches = engine.search_by_image(query_img)
    t_el = (time.perf_counter() - t0) * 1000
    print(f"Search completed in: {t_el:.2f}ms")
    for idx, m in enumerate(matches, 1):
        print(f"  [{idx}] {m['source']}: {m['title']}")
        print(f"      Similarity: {m['similarity_score']} ({m['confidence']}) -> {m['link']}")
