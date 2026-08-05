"""Published-photo claims are checked again at approval time.

An unapproved draft should not block another seller. But once another seller
does publish first, the waiting draft must not be able to go live later with
the same photo.
"""
import graph_store


class _FakeFingerprints:
    def __init__(self, rows):
        self.rows = rows

    def find(self, *_, **__):
        return self

    def limit(self, *_):
        return iter(self.rows)


class _FakeClient(dict):
    def __getitem__(self, _db_name):
        return {"image_fingerprints": dict.__getitem__(self, "image_fingerprints")}


def _with_claims(rows):
    return _FakeClient(image_fingerprints=_FakeFingerprints(rows))


def test_same_seller_photo_claim_does_not_block():
    old = graph_store._get_client
    graph_store._get_client = lambda: _with_claims([
        {"phash": "ffffffffffffffff", "seller_id": "seller-a"}
    ])
    try:
        claim = graph_store.check_phash_claim("ffffffffffffffff", "seller-a")
    finally:
        graph_store._get_client = old

    assert claim["duplicate"] is True
    assert claim["cross_seller"] is False


def test_cross_seller_photo_claim_blocks():
    old = graph_store._get_client
    graph_store._get_client = lambda: _with_claims([
        {"phash": "ffffffffffffffff", "seller_id": "seller-b"}
    ])
    try:
        claim = graph_store.check_phash_claim("ffffffffffffffff", "seller-a")
    finally:
        graph_store._get_client = old

    assert claim["duplicate"] is True
    assert claim["cross_seller"] is True
    assert claim["duplicate_of_seller"] == "seller-b"


def test_current_listing_claim_is_ignored():
    old = graph_store._get_client
    graph_store._get_client = lambda: _with_claims([
        {"phash": "ffffffffffffffff", "seller_id": "seller-b", "listing_id": "listing-1"}
    ])
    try:
        claim = graph_store.check_phash_claim(
            "ffffffffffffffff", "seller-a", exclude_listing_id="listing-1"
        )
    finally:
        graph_store._get_client = old

    assert claim["duplicate"] is False
    assert claim["cross_seller"] is False
