"""Seller registration, login, sessions, and listing ownership.

A seller registers with a phone number and a password, logs in to get a signed
expiring session token, and only she can act on her own listings. That closes
the hole where the approval gate checked a listing's *status* but never *who
was asking* — so any caller could publish someone else's listing or spam
/return to poison Wapsi's learning data.

Two deliberate stdlib choices, both to avoid a dependency on the deploy host:

* **Passwords: `hashlib.scrypt`.** A real memory-hard KDF (~100ms/hash at these
  parameters), not a bare SHA. bcrypt/argon2 would be equally fine but neither
  is installed and both need a compiled wheel.
* **Tokens: `hmac` + SHA-256.** The token never leaves our own API, so a JWT
  library's interoperability buys nothing here.

Known limits, stated plainly rather than discovered later:

* **Passwords are a poor fit for the target seller.** This product's whole
  premise is that she speaks once instead of typing; a password she must
  remember cuts against that. Phone + OTP is the domain-correct answer and
  `SMS_OTP` is where it would go. This is a deliberate trade for a
  self-contained prototype with no SMS provider.
* **Login throttling is per-process and in-memory** (see `_login_attempts`),
  so it does not hold across multiple backend instances. Real deployments want
  this in Mongo or Redis.
* **No password reset.** A seller who forgets hers cannot recover the account
  without a database edit — reset needs a verified channel, which is the same
  SMS/OTP dependency.
"""
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Optional

from fastapi import HTTPException, Request

from .config import settings

log = logging.getLogger(__name__)

_ALGO = hashlib.sha256
_dev_secret: Optional[str] = None


def _secret() -> str:
    """The HMAC signing key.

    In prod a real SESSION_SECRET is mandatory — without it tokens would be
    forgeable by anyone who reads this (open-source) repo. In dev we mint an
    ephemeral one so the app runs with no setup; it changes on every restart,
    which invalidates existing tokens. That is intentional, not a bug.
    """
    global _dev_secret
    if settings.SESSION_SECRET:
        return settings.SESSION_SECRET
    if not settings.is_dev:
        raise RuntimeError(
            "SESSION_SECRET is not set. Set it to a long random string before "
            "running outside dev — session tokens are forgeable without it."
        )
    if _dev_secret is None:
        _dev_secret = secrets.token_urlsafe(32)
        log.warning(
            "SESSION_SECRET not set — using an ephemeral dev secret. "
            "Sessions will not survive a restart."
        )
    return _dev_secret


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload_b64: str) -> str:
    mac = hmac.new(_secret().encode(), payload_b64.encode(), _ALGO).digest()
    return _b64e(mac)


def issue_token(seller_id: str, ttl_hours: Optional[int] = None) -> str:
    """Mint a signed session token for `seller_id`."""
    ttl = ttl_hours if ttl_hours is not None else settings.SESSION_TTL_HOURS
    now = int(time.time())
    payload = {"sid": str(seller_id), "iat": now, "exp": now + ttl * 3600}
    payload_b64 = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    return f"{payload_b64}.{_sign(payload_b64)}"


def verify_token(token: str) -> str:
    """Return the seller_id carried by a valid token, else raise 401."""
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        raise HTTPException(status_code=401, detail="Malformed session token.")

    # compare_digest, not ==, so a wrong signature can't be recovered byte by
    # byte from response timing.
    if not hmac.compare_digest(_sign(payload_b64), signature):
        raise HTTPException(status_code=401, detail="Invalid session token.")

    try:
        payload = json.loads(_b64d(payload_b64))
    except Exception:  # noqa: BLE001 - signature held, so this is our own bug
        raise HTTPException(status_code=401, detail="Unreadable session token.")

    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=401, detail="Session expired — please sign in again.")

    seller_id = payload.get("sid")
    if not seller_id:
        raise HTTPException(status_code=401, detail="Session token carries no seller.")
    return str(seller_id)


# --- passwords -------------------------------------------------------------
#
# scrypt cost. n=2**14 lands around 100ms per hash here: slow enough to make
# offline cracking expensive, fast enough that a login feels instant. The
# parameters are stored *inside* each hash, so raising them later does not
# invalidate existing passwords — verify reads whatever that hash was made with.
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32

MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    """A self-describing scrypt hash: scrypt$n$r$p$salt$key (all base64url)."""
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64e(salt)}${_b64e(key)}"


def verify_password(password: str, stored: Optional[str]) -> bool:
    """Check a password against a stored hash. False on anything malformed."""
    if not stored:
        return False
    try:
        scheme, n, r, p, salt_b64, key_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = _b64d(key_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=_b64d(salt_b64),
            n=int(n), r=int(r), p=int(p), dklen=len(expected),
        )
    except Exception:  # noqa: BLE001 - a corrupt hash must fail closed, not 500
        return False
    return hmac.compare_digest(actual, expected)


# --- login throttling ------------------------------------------------------
#
# Without this a password is only as strong as the attacker's patience. Held in
# memory, so it resets on restart and is per-process — see the module docstring.
_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 15 * 60
_login_attempts: dict[str, list[float]] = {}


def _recent_failures(phone: str) -> list[float]:
    cutoff = time.time() - _LOCKOUT_SECONDS
    return [t for t in _login_attempts.get(phone, []) if t > cutoff]


def check_login_allowed(phone: str) -> None:
    """Raise 429 if this phone has failed too many times recently."""
    failures = _recent_failures(phone)
    if len(failures) >= _MAX_ATTEMPTS:
        wait = int((failures[0] + _LOCKOUT_SECONDS - time.time()) / 60) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Please try again in about {wait} minutes.",
        )


def record_login_failure(phone: str) -> None:
    _login_attempts[phone] = _recent_failures(phone) + [time.time()]


def clear_login_failures(phone: str) -> None:
    _login_attempts.pop(phone, None)


def _bearer(request: Request) -> Optional[str]:
    header = request.headers.get("Authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


async def current_seller(request: Request) -> str:
    """Require a valid session. Returns the caller's seller_id."""
    token = _bearer(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Sign in as a seller first — this action needs a session.",
        )
    return verify_token(token)


async def optional_seller(request: Request) -> Optional[str]:
    """The caller's seller_id if a valid session is present, else None.

    Used by /run, which still accepts anonymous runs. Note the consequence:
    an anonymous run produces a listing nobody owns, and an unowned listing
    can never be approved (see `require_listing_owner`).
    """
    token = _bearer(request)
    if not token:
        return None
    return verify_token(token)


def require_listing_owner(doc: dict, seller_id: str) -> None:
    """Raise unless `seller_id` owns `doc`.

    An unowned listing (seller_id None — every listing the web app created
    before sessions existed, plus the demo seed) is deliberately a dead end
    rather than a free-for-all: letting any signed-in seller adopt it would
    reintroduce the very hole this closes.
    """
    owner = doc.get("seller_id")
    if owner is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "This listing has no owner, so it cannot be acted on. It was "
                "created before seller sessions existed — re-run it while signed in."
            ),
        )
    if str(owner) != str(seller_id):
        # 404, not 403: a 403 would confirm the listing exists to someone who
        # is not its owner.
        raise HTTPException(status_code=404, detail="Listing not found")
