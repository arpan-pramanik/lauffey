import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

def load_env():
    """Load key-value pairs from .env into os.environ without third-party dependencies."""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val

load_env()

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "").strip()

# Target social media domains to detect in reverse search
SOCIAL_DOMAINS = [
    "instagram.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "facebook.com",
    "reddit.com",
    "tiktok.com",
    "youtube.com",
    "pinterest.com",
    "threads.net",
    "github.com",
    "medium.com"
]

# Face processing configurations
DETECTOR_BACKEND = os.environ.get("DETECTOR_BACKEND", "opencv")
RECOGNITION_MODEL = os.environ.get("RECOGNITION_MODEL", "Facenet512")
CROP_MARGIN = 0.20  # 20% margin around the face for optimal Lens matching

# Blockchain configuration
BLOCKCHAIN_RPC = os.environ.get("BLOCKCHAIN_RPC", "tester")  # 'tester' or HTTP RPC URL
