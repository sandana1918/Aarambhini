"""backend/auth.py — password hashing, session tokens, login throttle.

The account-enumeration bug caught this session lived here: verify_password
short-circuited on a missing hash, so an unregistered phone answered ~130ms
faster than a wrong password for a real one — the timing told an attacker
which sellers have accounts even though the error message was identical.
That fix (a dummy hash always run through the same scrypt cost) is exercised
by the caller in backend/routers/sessions.py, not in this pure module, so it
isn't re-tested here — what belongs at this layer is that verify_password
itself never raises and never accepts a malformed or empty hash.
"""
import time

import pytest

from backend import auth


def test_hash_is_salted_same_password_twice_differs():
    a = auth.hash_password("correct horse battery staple")
    b = auth.hash_password("correct horse battery staple")
    assert a != b


def test_hash_round_trips():
    h = auth.hash_password("correct horse battery staple")
    assert auth.verify_password("correct horse battery staple", h) is True
    assert auth.verify_password("wrong password entirely", h) is False


def test_verify_password_never_raises_on_garbage_input():
    assert auth.verify_password("anything", None) is False
    assert auth.verify_password("anything", "") is False
    assert auth.verify_password("anything", "not-a-real-hash") is False
    assert auth.verify_password("anything", "scrypt$bad$bad$bad$bad$bad") is False


def test_hash_format_carries_its_own_cost_parameters():
    # So raising _SCRYPT_N later never invalidates an existing password —
    # verify reads whatever cost that hash was actually made with.
    h = auth.hash_password("x")
    scheme, n, r, p, salt, key = h.split("$")
    assert scheme == "scrypt"
    int(n), int(r), int(p)  # must parse as integers


# --------------------------------------------------------------- session tokens
def test_token_round_trips_to_the_right_seller():
    tok = auth.issue_token("seller-123")
    assert auth.verify_token(tok) == "seller-123"


def test_forged_signature_is_rejected():
    tok = auth.issue_token("seller-123")
    other = auth.issue_token("seller-456")
    forged = other.split(".")[0] + "." + tok.split(".")[1]
    with pytest.raises(Exception):
        auth.verify_token(forged)


def test_expired_token_is_rejected():
    tok = auth.issue_token("seller-123", ttl_hours=0)
    time.sleep(1.1)
    with pytest.raises(Exception):
        auth.verify_token(tok)


@pytest.mark.parametrize("garbage", ["", "nonsense", "a.b", "..", "not-base64.at-all"])
def test_malformed_tokens_are_rejected_not_500d(garbage):
    with pytest.raises(Exception):
        auth.verify_token(garbage)


# ------------------------------------------------------------------ login throttle
def test_throttle_locks_out_after_five_failures():
    phone = "9000000001-throttle-test"
    for _ in range(5):
        auth.check_login_allowed(phone)  # must not raise yet
        auth.record_login_failure(phone)
    with pytest.raises(Exception):
        auth.check_login_allowed(phone)


def test_a_success_clears_the_failure_count():
    phone = "9000000002-throttle-test"
    for _ in range(5):
        auth.check_login_allowed(phone)
        auth.record_login_failure(phone)
    auth.clear_login_failures(phone)
    auth.check_login_allowed(phone)  # must not raise
