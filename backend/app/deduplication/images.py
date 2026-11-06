"""Local image perceptual hashing helpers; no image is sent to a remote service."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlsplit
from typing import Optional

import imagehash
from PIL import Image, UnidentifiedImageError



def compute_phash(path: str | Path) -> Optional[str]:
    """Return a 64-bit pHash as hexadecimal, or None if the file is unreadable."""
    try:
        with Image.open(path) as image:
            return str(imagehash.phash(image.convert("RGB"), hash_size=8))
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
        return None


def phash_similarity(first: str, second: str) -> float:
    """Return normalized pHash similarity in [0, 1]; malformed hashes raise."""
    first_hash = imagehash.hex_to_hash(first)
    second_hash = imagehash.hex_to_hash(second)
    if first_hash.hash.shape != second_hash.hash.shape:
        raise ValueError("pHash values must have matching dimensions")
    distance = int((first_hash - second_hash))
    return 1.0 - distance / first_hash.hash.size


def resolve_uploaded_file(file_url: str, upload_dir: str | Path | None = None) -> Optional[Path]:
    """Resolve an app-local `/uploads/...` URL without permitting path traversal."""
    parsed = urlsplit(file_url)
    if parsed.scheme or parsed.netloc:
        return None
    parts = [unquote(part) for part in parsed.path.replace("\\", "/").split("/") if part]
    if not parts or parts[0] != "uploads" or any(part in {".", ".."} for part in parts):
        return None
    if upload_dir is None:
        from app.core.config import get_upload_directory

        upload_dir = get_upload_directory()
    root = Path(upload_dir).resolve()
    candidate = root.joinpath(*parts[1:]).resolve()
    if root not in candidate.parents:
        return None
    return candidate


def compute_phash_for_url(file_url: str, upload_dir: str | Path | None = None) -> Optional[str]:
    """Compute pHash only for files in local upload storage; remote URLs are skipped."""
    path = resolve_uploaded_file(file_url, upload_dir)
    return compute_phash(path) if path is not None else None
