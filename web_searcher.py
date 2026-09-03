import os
import json
import hashlib
import time
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
from config import SERPAPI_KEY, SOCIAL_DOMAINS, CACHE_DIR

class WebSearcher:
    """
    Handles reverse visual search via Google Lens (SerpAPI) with smart caching
    to prevent burning precious free API quota.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or SERPAPI_KEY
        if not self.api_key:
            print("[!] Warning: SERPAPI_KEY is not set. Real web search calls will fail unless dry-run is used.")

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

    def search_reverse_image(self, image_path: str, force: bool = False) -> List[Dict[str, Any]]:
        """
        Executes Google Lens reverse search via SerpAPI.
        Results are cached locally by image SHA256 to conserve API credits.
        """
        img_hash = self._get_image_file_hash(image_path)
        cache_file = CACHE_DIR / f"lens_search_{img_hash[:16]}.json"

        if not force and cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if cached:  # Only reuse non-empty cache
                    print(f"  [*] Reusing locally cached search result: {cache_file.name}")
                    return cached

        if not self.api_key:
            raise ValueError("SERPAPI_KEY is required to perform reverse web search.")

        print("  [*] Uploading cropped face to temporary host...")
        public_url = self.upload_to_temp_host(image_path)
        print(f"  [*] Image hosted temporarily at: {public_url}")

        print("  [*] Querying SerpAPI Google Lens...")
        params = {
            "engine": "google_lens",
            "url": public_url,
            "api_key": self.api_key
        }

        last_err = None
        for attempt in range(2):
            try:
                resp = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    break
                else:
                    raise RuntimeError(f"SerpAPI returned HTTP {resp.status_code}: {resp.text}")
            except Exception as e:
                last_err = e
                time.sleep(1.5)
        else:
            raise RuntimeError(f"SerpAPI request failed: {last_err}")

        raw_matches = data.get("visual_matches", [])

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
