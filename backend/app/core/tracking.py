"""Citizen-facing complaint tracking IDs.

A tracking ID is the short code a citizen keeps after reporting an issue, for
example ``NC-7K4P-9XQ2``. It is separate from the internal UUID primary key so
that it can be read aloud, typed from a screenshot, and quoted over the phone.

Design choices:

* **Unambiguous alphabet** - digits 2-9 and letters A-Z without ``I``, ``L`` and
  ``O`` (31 symbols), so ``0/O`` and ``1/I/L`` can never be confused.
* **8 random symbols** - 31^8 is about 8.5e11 combinations drawn from the OS
  CSPRNG (``secrets``), so IDs cannot be guessed by counting up. This matters
  because the public tracker is looked up by this code alone.
* **Uniqueness is enforced by the database** (unique index); the service also
  checks before inserting and retries on the astronomically rare collision.
"""
from __future__ import annotations

import re
import secrets
from typing import Optional

TRACKING_PREFIX = "NC"
TRACKING_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_BODY_LENGTH = 8
_TRACKING_RE = re.compile(r"^NC-[2-9A-HJKMNP-Z]{4}-[2-9A-HJKMNP-Z]{4}$")


def generate_tracking_id() -> str:
    """Return a new random tracking ID such as ``NC-7K4P-9XQ2``."""
    body = "".join(secrets.choice(TRACKING_ALPHABET) for _ in range(_BODY_LENGTH))
    return f"{TRACKING_PREFIX}-{body[:4]}-{body[4:]}"


def normalize_tracking_id(raw: Optional[str]) -> Optional[str]:
    """Canonicalise user input into ``NC-XXXX-XXXX`` or return ``None``.

    Accepts lower case, surrounding spaces and a missing or misplaced dash, so
    ``nc 7k4p9xq2`` and ``NC-7K4P-9XQ2`` resolve to the same ID.
    """
    if not raw:
        return None
    compact = re.sub(r"[\s\-_]", "", raw).upper()
    if not compact.startswith(TRACKING_PREFIX):
        return None
    body = compact[len(TRACKING_PREFIX):]
    if len(body) != _BODY_LENGTH:
        return None
    candidate = f"{TRACKING_PREFIX}-{body[:4]}-{body[4:]}"
    return candidate if _TRACKING_RE.match(candidate) else None
