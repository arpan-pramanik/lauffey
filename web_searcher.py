import os
import json
import hashlib
import time
import requests
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import SERPAPI_KEY, SERPER_API_KEY, SOCIAL_DOMAINS, CACHE_DIR

# Same bucketing local_engine.py uses for on-device gallery matches, applied
# here to real cosine similarity between the query face and each candidate's
# face so web results are ranked by actual face match, not photo similarity.
def _confidence_label(score: float) -> str:
    if score > 0.40:
        return "HIGH (MATCH)"
    if score > 0.25:
        return "MEDIUM"
    return "LOW (NO MATCH)"

def _hamming_distance(hash_a: str, hash_b: str) -> int:
    """Bit distance between two perceptual hashes - near 0 means the same image, not just the same face."""
    try:
        return bin(int(hash_a, 16) ^ int(hash_b, 16)).count("1")
    except (ValueError, TypeError):
        return 64

class WebSearcher:
    """
    Handles reverse visual search via Google Lens, with two interchangeable
    providers: Serper.dev (tried first, cheaper per-query) and SerpAPI
    (automatic fallback if Serper fails or is not configured). Results are
    cached locally by image SHA256 to conserve quota on both providers.
    """
    def __init__(self, serper_key: Optional[str] = None, serpapi_key: Optional[str] = None):
        self.serper_key = serper_key or SERPER_API_KEY
        self.serpapi_key = serpapi_key or SERPAPI_KEY
        if not self.serper_key and not self.serpapi_key:
            print("[!] Warning: neither SERPER_API_KEY nor SERPAPI_KEY is set. Real web search calls will fail unless dry-run is used.")

    def _get_image_file_hash(self, image_path: str) -> str:
        h = hashlib.sha256()
        with open(image_path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    def upload_to_temp_host(self, image_path: str) -> str:
        """
        Uploads local image to a reliable public host so Google Lens can fetch the raw image.
        Uses Uguu (primary) and TmpFiles / Litterbox (fallbacks).
        """
        # Primary: Uguu.se
        try:
            with open(image_path, "rb") as f:
                resp = requests.post(
                    "https://uguu.se/upload.php",
                    files={"files[]": f},
                    timeout=15
                )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and data.get("files"):
                    return data["files"][0]["url"]
        except Exception:
            pass

        # Fallback 1: tmpfiles.org
        try:
            with open(image_path, "rb") as f:
                resp = requests.post(
                    "https://tmpfiles.org/api/v1/upload",
                    files={"file": f},
                    timeout=15
                )
            data = resp.json()
            if data.get("status") == "success":
                url = data["data"]["url"]
                parts = url.split("tmpfiles.org/")
                return f"https://tmpfiles.org/dl/{parts[1]}"
        except Exception:
            pass

        # Fallback 2: Litterbox
        try:
            with open(image_path, "rb") as f:
                resp = requests.post(
                    "https://litterbox.catbox.moe/resources/internals/api.php",
                    data={"reqtype": "fileupload", "time": "1h"},
                    files={"fileToUpload": f},
                    timeout=15
                )
            if resp.status_code == 200 and resp.text.startswith("http"):
                return resp.text.strip()
        except Exception:
            pass

        raise RuntimeError("No image hosting service succeeded in uploading the temporary portrait.")

    def _raw_matches_via_serper(self, public_url: str) -> List[Dict[str, Any]]:
        """Queries Serper.dev's Google Lens endpoint and normalizes results to the common match shape."""
        resp = requests.post(
            "https://google.serper.dev/lens",
            headers={"X-API-KEY": self.serper_key, "Content-Type": "application/json"},
            json={"url": public_url},
            timeout=30
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Serper returned HTTP {resp.status_code}: {resp.text}")
        data = resp.json()
        organic = data.get("organic", [])
        return [
            {
                "link": item.get("link", ""),
                "source": item.get("source", ""),
                "title": item.get("title", ""),
                "thumbnail": item.get("imageUrl", "")
            }
            for item in organic
        ]

    def _raw_matches_via_serpapi(self, public_url: str) -> List[Dict[str, Any]]:
        """Queries SerpAPI's Google Lens engine and returns its native visual_matches list."""
        params = {
            "engine": "google_lens",
            "url": public_url,
            "api_key": self.serpapi_key
        }
        last_err = None
        for attempt in range(2):
            try:
                resp = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
                if resp.status_code == 200:
                    return resp.json().get("visual_matches", [])
                last_err = RuntimeError(f"SerpAPI returned HTTP {resp.status_code}: {resp.text}")
            except Exception as e:
                last_err = e
            time.sleep(1.5)
        raise RuntimeError(f"SerpAPI request failed: {last_err}")

    def _download_thumbnail(self, thumbnail_url: str) -> Optional[bytes]:
        """I/O-only, safe to run concurrently across many candidates at once."""
        if not thumbnail_url:
            return None
        try:
            resp = requests.get(thumbnail_url, timeout=5)
            if resp.status_code == 200 and resp.content:
                return resp.content
        except Exception:
            pass
        return None

    def _verify_face_match(self, image_bytes: bytes, query_embedding: list, face_processor):
        """
        Computes real ArcFace/SFace cosine similarity against the query face
        embedding, plus a perceptual hash of the candidate image - together
        these tell a different photo of the same person (high similarity, a
        different hash) apart from the exact same image reposted (both) and
        an unrelated photo that merely looked similar to Google Lens (neither).
        Runs sequentially, one candidate at a time, reusing a single
        FaceProcessor instance - deepface's TF/Keras backend isn't safe to
        call from multiple threads at once, so only the network downloads
        upstream of this are parallelized.
        """
        tmp_path = CACHE_DIR / f"_candidate_{hashlib.sha256(image_bytes[:64]).hexdigest()[:12]}.jpg"
        try:
            with open(tmp_path, "wb") as f:
                f.write(image_bytes)
            result = face_processor.process(str(tmp_path))
            # "Texture-Histogram (128-d Fallback)" is a color histogram, not
            # a face embedding - it only fires when no real detector found a
            # face at all, but happens to share SFace's 128 dimensions, so a
            # bare dimension check wouldn't catch comparing it against a
            # genuine embedding. A confidence of exactly 0.50 is detect_and_crop's
            # own "nothing detected, used a blind center crop" fallback marker.
            if result.get("engine") == "Texture-Histogram (128-d Fallback)" or result.get("confidence", 1.0) <= 0.50:
                return None, None
            cand_emb = np.array(result["embedding"], dtype=np.float32)
            q_emb = np.array(query_embedding, dtype=np.float32)
            if len(cand_emb) != len(q_emb):
                return None, None
            cand_norm = cand_emb / (np.linalg.norm(cand_emb) or 1)
            q_norm = q_emb / (np.linalg.norm(q_emb) or 1)
            similarity = float(np.dot(cand_norm, q_norm))
            phash = result.get("perceptual_hash", "0x0")
            return similarity, phash
        except Exception:
            return None, None
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def search_reverse_image(
        self,
        image_path: str,
        force: bool = False,
        query_embedding: Optional[list] = None,
        query_phash: Optional[str] = None,
        mode: str = "high"
    ) -> List[Dict[str, Any]]:
        """
        Executes a Google Lens reverse search of the given image, trying Serper.dev
        first (cheaper per-query) and falling back to SerpAPI if Serper fails or
        is not configured. Results are cached locally by image SHA256 so a
        repeat scan of the same photo never spends quota on either provider.

        When query_embedding is provided, each candidate's thumbnail is
        independently re-checked against the query face (see
        _verify_face_match) so a different photo of the same person ranks
        above a merely visually-similar photo of someone else. Thumbnails are
        downloaded concurrently (this is the part that can be slow/flaky
        across many candidates) but verified against the face one at a time.
        """
        img_hash = self._get_image_file_hash(image_path)
        cache_file = CACHE_DIR / f"lens_search_{img_hash[:16]}.json"

        if not force and cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if cached:  # Only reuse non-empty cache
                    print(f"  [*] Reusing locally cached search result: {cache_file.name}")
                    return cached

        if not self.serper_key and not self.serpapi_key:
            raise ValueError("Set SERPER_API_KEY or SERPAPI_KEY to perform reverse web search.")

        print("  [*] Uploading image for facial analysis...")
        public_url = self.upload_to_temp_host(image_path)
        print(f"  [*] Image hosted temporarily at: {public_url}")

        # SerpAPI's google_lens engine has consistently returned far more
        # complete visual match results than Serper.dev's /lens endpoint in
        # side-by-side testing on the same image (60 matches vs 0), so it's
        # tried first. Serper is kept as a fallback in case SerpAPI itself
        # is unavailable or its quota is exhausted.
        providers = []
        if self.serpapi_key:
            providers.append(("SerpAPI", self._raw_matches_via_serpapi))
        if self.serper_key:
            providers.append(("Serper.dev", self._raw_matches_via_serper))

        raw_matches = None
        last_err = None
        for name, search_fn in providers:
            print(f"  [*] Querying {name} Google Lens...")
            try:
                result = search_fn(public_url)
            except Exception as e:
                last_err = e
                print(f"  [!] {name} search failed: {e}")
                continue
            if result:
                raw_matches = result
                break
            print(f"  [!] {name} returned no visual matches, trying next provider...")
            last_err = last_err or RuntimeError(f"{name} returned no visual matches")

        if raw_matches is None:
            raise RuntimeError(f"All configured search providers failed or returned nothing: {last_err}")

        # Normalize every raw match Lens/Serper returned - social platform or
        # not. The task asks for matching content on "the web/social media",
        # not social platforms exclusively, and a news article or blog post
        # showing the same person is still a genuine find.
        all_candidates = []
        for match in raw_matches:
            link = match.get("link", "")
            source = match.get("source", "").lower()
            is_social = any(domain in link.lower() or domain in source for domain in SOCIAL_DOMAINS)
            all_candidates.append({
                "title": match.get("title", "") or ("Social Post" if is_social else "Web Match"),
                "link": link,
                "source": match.get("source", "Social Media" if is_social else "Web"),
                "thumbnail": match.get("thumbnail", ""),
                "confidence": "high" if is_social else "web-match",
                "is_social": is_social
            })

        # Google Lens matches by photo similarity, which reliably finds
        # reposts of the exact same image but won't on its own tell a
        # genuinely different photo of the same person apart from a photo
        # that just looks visually similar. Independently re-check every
        # candidate's thumbnail against the query face with our own
        # ArcFace/SFace embeddings, so a person's face is recognized across
        # however many different photos of them Lens happened to surface for
        # this one query - not just re-checking the single top hit. Capped
        # to bound how many extra downloads/detections one search costs.
        VERIFY_CAP = 20
        if query_embedding and all_candidates:
            pool = all_candidates[:VERIFY_CAP]
            print(f"  [*] Downloading {len(pool)} candidate thumbnail(s)...")

            # Downloads are the slow, flaky part (many different third-party
            # hosts, some slow to respond) - fetch them all concurrently so
            # one slow host doesn't multiply into the others' wait time.
            downloads = {}
            with ThreadPoolExecutor(max_workers=8) as pool_executor:
                futures = {pool_executor.submit(self._download_thumbnail, c.get("thumbnail", "")): i for i, c in enumerate(pool)}
                for future in as_completed(futures):
                    downloads[futures[future]] = future.result()

            downloaded = sum(1 for b in downloads.values() if b)
            print(f"  [*] Verifying {downloaded} downloaded candidate(s) against the query face...")
            from face_processor import get_cached_processor

            # Candidate verification always runs in fast mode (YuNet+SFace),
            # independent of whatever accuracy mode the user's own photo
            # used. Checking up to 20 candidates doesn't need SOTA precision,
            # and running deepface's much heavier RetinaFace/ArcFace pass
            # that many times in a row was slow enough to blow past request
            # timeouts in production. Re-embeds the query in fast mode too
            # so both sides of every comparison are the same 128-d space.
            verifier = get_cached_processor("fast")
            if mode == "fast":
                fast_query_embedding = query_embedding
            else:
                fast_query_embedding = verifier.process(image_path)["embedding"]

            for i, candidate in enumerate(pool):
                image_bytes = downloads.get(i)
                if not image_bytes:
                    continue
                similarity, cand_phash = self._verify_face_match(image_bytes, fast_query_embedding, verifier)
                if similarity is not None:
                    candidate["similarity_score"] = round(similarity, 4)
                    candidate["confidence"] = _confidence_label(similarity)
                    if query_phash and cand_phash:
                        candidate["is_exact_image"] = _hamming_distance(query_phash, cand_phash) <= 10

        # Keep every candidate Lens/Serper returned, verified or not - a
        # result that couldn't be face-checked (no thumbnail, download
        # failed) or that scored low is still a real find worth showing,
        # just ranked below anything confirmed as a stronger face match.
        social_posts = all_candidates
        social_posts.sort(key=lambda m: m.get("similarity_score", -1.0), reverse=True)
        for c in social_posts:
            c.pop("is_social", None)

        # Save to cache to safeguard user API quota
        if social_posts:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(social_posts, f, indent=2)

        return social_posts

    def mock_search(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Provides a synthetic matching social media post for zero-cost local testing.
        """
        img_hash = self._get_image_file_hash(image_path)[:8]
        return [
            {
                "title": f"Profile avatar update - verified user identity #{img_hash}",
                "link": f"https://x.com/identity_user/status/179234819{img_hash}",
                "source": "X (formerly Twitter)",
                "thumbnail": "https://pbs.twimg.com/profile_images/sample.jpg",
                "confidence": "synthetic-test"
            }
        ]

if __name__ == "__main__":
    searcher = WebSearcher()
    print("WebSearcher initialized with caching enabled.")
