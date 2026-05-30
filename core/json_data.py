"""Utility for loading JSON mock data files from the workspace `data/` folder.

Provides simple caching and robust error handling so services can read
mock data without a database.
"""
from pathlib import Path
import json
from django.conf import settings

from core.exceptions import ServiceError


_CACHE = {}


def _data_dir() -> Path:
    return Path(settings.BASE_DIR) / "data"


def load_json(name: str):
    """Load and return the JSON object for `name` (e.g. 'customers.json').

    Caches results for the lifetime of the process. Raises ServiceError
    if the file cannot be read or parsed.
    """
    if name in _CACHE:
        return _CACHE[name]

    path = _data_dir() / name
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:
        raise ServiceError(f"Data file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ServiceError(f"Data file malformed: {path}") from exc
    except Exception as exc:
        raise ServiceError(f"Unable to read data file: {path}") from exc

    _CACHE[name] = data
    return data


def save_json(name: str, data):
    """Save JSON data to the data/ folder atomically and update cache.

    Raises ServiceError on failure (file permissions, malformed path, etc).
    """
    path = _data_dir() / name
    try:
        # write to a temporary file first then replace
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        tmp.replace(path)
    except Exception as exc:
        raise ServiceError(f"Unable to write data file: {path} ({exc})") from exc

    # update cache to ensure readers see the new content
    _CACHE[name] = data
    return True
