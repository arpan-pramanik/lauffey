import json
import os
from pathlib import Path
from typing import Any, Dict

LEDGER_DIR = Path(__file__).resolve().parent / "data"
LEDGER_DIR.mkdir(exist_ok=True)


def _ledger_path(chain_name: str) -> Path:
    return LEDGER_DIR / f"ledger_{chain_name}.json"


def load_ledger(chain_name: str) -> Dict[str, Any]:
    """Loads a chain's persisted ledger from disk so records survive across processes."""
    path = _ledger_path(chain_name)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def append_record(chain_name: str, tx_key: str, record: Dict[str, Any]) -> None:
    """Persists a single ledger record, keyed by tx hash/signature, with an atomic write."""
    path = _ledger_path(chain_name)
    ledger = load_ledger(chain_name)
    ledger[tx_key] = record
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)
    os.replace(tmp_path, path)


def load_key_material(key_name: str) -> str | None:
    """Loads a persisted validator private key hex string, if one exists."""
    path = LEDGER_DIR / f"{key_name}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("private_key")
    except (json.JSONDecodeError, OSError):
        return None


def save_key_material(key_name: str, private_key: str) -> None:
    path = LEDGER_DIR / f"{key_name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"private_key": private_key}, f)
