import os
import json
import hashlib
import time
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
from config import SERPAPI_KEY, SERPER_API_KEY, SOCIAL_DOMAINS, CACHE_DIR

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

    def search_reverse_image(self, image_path: str, force: bool = False) -> List[Dict[str, Any]]:
        """
        Executes a Google Lens reverse search of the given image, trying Serper.dev
        first (cheaper per-query) and falling back to SerpAPI if Serper fails or
        is not configured. Results are cached locally by image SHA256 so a
        repeat scan of the same photo never spends quota on either provider.
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

        print("  [*] Uploading face crop to temporary host...")
        public_url = self.upload_to_temp_host(image_path)
        print(f"  [*] Image hosted temporarily at: {public_url}")

        providers = []
        if self.serper_key:
            providers.append(("Serper.dev", self._raw_matches_via_serper))
        if self.serpapi_key:
            providers.append(("SerpAPI", self._raw_matches_via_serpapi))

        raw_matches = None
        last_err = None
        for name, search_fn in providers:
            print(f"  [*] Querying {name} Google Lens...")
            try:
                raw_matches = search_fn(public_url)
                break
            except Exception as e:
                last_err = e
                print(f"  [!] {name} search failed: {e}")
        if raw_matches is None:
            raise RuntimeError(f"All configured search providers failed: {last_err}")

        # Filter social media posts
        social_posts = []
        for match in raw_matches:
            link = match.get("link", "")
            source = match.get("source", "").lower()
            title = match.get("title", "")

            is_social = any(domain in link.lower() or domain in source for domain in SOCIAL_DOMAINS)
            if is_social:
                social_posts.append({
                    "title": title or "Social Post",
                    "link": link,
                    "source": match.get("source", "Social Media"),
                    "thumbnail": match.get("thumbnail", ""),
                    "confidence": "high"
                })

        # Fallback to top visual matches if specific social domains are not direct visual matches
        if not social_posts and raw_matches:
            for match in raw_matches[:5]:
                social_posts.append({
                    "title": match.get("title", "Web Match"),
                    "link": match.get("link", ""),
                    "source": match.get("source", "Web"),
                    "thumbnail": match.get("thumbnail", ""),
                    "confidence": "web-match"
                })

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
