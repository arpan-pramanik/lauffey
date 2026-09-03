import os
import json
import time
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np

from config import BASE_DIR, BIOMETRIC_ACCURACY_MODE
from face_processor import FaceProcessor

PROFILES_JSON = BASE_DIR / "data" / "profiles.json"
PROFILES_DIR = BASE_DIR / "data" / "profiles"

class LocalDiscoveryEngine:
    """
    Dynamic On-Device Biometric Discovery Engine.
    - Zero hardcoded assumptions: dynamically scans the gallery directory.
    - Supports dynamic registration of novel identities at runtime.
    - Matches queries via high-dimensional normalized cosine distance.
    - Consumes ZERO external API quota.
    """
    def __init__(self, mode: Optional[str] = None, gallery_dir: Optional[Path] = None, metadata_path: Optional[Path] = None):
        self.mode = mode or BIOMETRIC_ACCURACY_MODE
        self.gallery_dir = gallery_dir or PROFILES_DIR
        self.metadata_path = metadata_path or PROFILES_JSON
        self.face_processor = FaceProcessor(mode=self.mode)
        
        if self.mode == "high":
            self.cache_file = BASE_DIR / "data" / "embeddings_cache_512.json"
            self.expected_dim = 512
        else:
            self.cache_file = BASE_DIR / "data" / "embeddings_cache_128.json"
            self.expected_dim = 128

        self.registry: List[Dict[str, Any]] = []
        self._load_and_index()

    def _format_name_from_filename(self, filename: str) -> str:
        stem = Path(filename).stem
        cleaned = stem.replace("_", " ").replace("-", " ").title()
        return cleaned

    def _load_and_index(self):
        """Dynamically scans gallery and synchronizes feature embeddings."""
        self.gallery_dir.mkdir(parents=True, exist_ok=True)
        known_profiles = {}

        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    for p in json.load(f):
                        rel = p.get("image", "")
                        known_profiles[rel] = p
            except Exception:
                known_profiles = {}

        cached_embeddings = {}
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as cf:
                    cached_embeddings = json.load(cf)
            except Exception:
                cached_embeddings = {}

        updated_cache = False
        self.registry = []

        # Find all valid portrait images in gallery
        image_extensions = {".jpg", ".jpeg", ".png", ".webp"}
        gallery_images = [
            f for f in self.gallery_dir.iterdir()
            if f.is_file() and f.suffix.lower() in image_extensions and not f.name.startswith("temp_")
        ]

        for img_path in sorted(gallery_images):
            img_rel = f"data/profiles/{img_path.name}"
            
            # Retrieve or dynamically generate metadata
            if img_rel in known_profiles:
                meta = known_profiles[img_rel]
            else:
                formatted_name = self._format_name_from_filename(img_path.name)
                meta = {
                    "id": img_path.stem.lower(),
                    "name": formatted_name,
                    "image": img_rel,
                    "source": "Web / Local Registry",
                    "title": f"Verified profile record for {formatted_name}",
                    "link": f"https://verified.identity/{img_path.stem.lower()}",
                    "thumbnail": img_rel
                }

            # Extract or load cached embedding
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
                    continue

            norm_emb = np.array(emb, dtype=np.float32)
            norm = np.linalg.norm(norm_emb)
            if norm > 0:
                norm_emb = norm_emb / norm

            self.registry.append({
                "profile": meta,
                "embedding": norm_emb,
                "dim": len(norm_emb)
            })

        if updated_cache:
            with open(self.cache_file, "w", encoding="utf-8") as cf:
                json.dump(cached_embeddings, cf)

    def register_identity(
        self,
        image_path: str,
        name: Optional[str] = None,
        source: str = "Verified Profile",
        link: Optional[str] = None,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dynamically registers ANY new identity into the biometric gallery at runtime.
        """
        src_path = Path(image_path)
        if not src_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        disp_name = name or self._format_name_from_filename(src_path.name)
        dest_filename = f"{src_path.stem}_{int(time.time())}{src_path.suffix}"
        dest_path = self.gallery_dir / dest_filename
        shutil.copy2(src_path, dest_path)

        dest_rel = f"data/profiles/{dest_filename}"
        new_meta = {
            "id": src_path.stem.lower(),
            "name": disp_name,
            "image": dest_rel,
            "source": source,
            "title": title or f"Dynamic identity record for {disp_name}",
            "link": link or f"https://verified.identity/{src_path.stem.lower()}",
            "thumbnail": dest_rel
        }

        # Compute embedding
        proc_res = self.face_processor.process(str(dest_path))
        emb = proc_res["embedding"]

        # Cache update
        cached = {}
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as cf:
                    cached = json.load(cf)
            except Exception:
                cached = {}
        cached[dest_rel] = emb
        with open(self.cache_file, "w", encoding="utf-8") as cf:
            json.dump(cached, cf)

        # Normalize and add to live memory registry
        norm_emb = np.array(emb, dtype=np.float32)
        norm = np.linalg.norm(norm_emb)
        if norm > 0:
            norm_emb = norm_emb / norm

        record = {
            "profile": new_meta,
            "embedding": norm_emb,
            "dim": len(norm_emb)
        }
        self.registry.append(record)
        return new_meta

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
    engine = LocalDiscoveryEngine(mode="fast")
    print(f"Dynamically indexed {len(engine.registry)} profiles in gallery.")
    for idx, reg in enumerate(engine.registry, 1):
        p = reg["profile"]
        print(f"  [{idx}] {p['name']} ({p['source']}) -> {p['image']}")
