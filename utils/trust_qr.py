"""Builds a provenance / trust QR for a published listing.

Encodes a compact human-readable provenance record the buyer can scan — proof
the listing passed the agent crew's checks. No external service; fully local.
"""
import os
import json
import datetime

import qrcode

_OUT_DIR = os.path.join(os.path.dirname(__file__), "..")


def build_trust_qr(listing, price, compliance, out_path=None):
    """Return (out_path, payload_dict)."""
    payload = {
        "verified_by": "Aarambhini agent crew",
        "product": listing.get("title", ""),
        "category": listing.get("category", ""),
        "price_inr": price.get("selling_price_inr"),
        "labels_applied": compliance.get("required_labels", []),
        "compliance_ok": compliance.get("compliance_ok", False),
        "issued_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }

    text = "AARAMBHINI TRUST\n" + "\n".join(f"{k}: {v}" for k, v in payload.items())

    if out_path is None:
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(_OUT_DIR, f"trust_qr_{stamp}.png")

    img = qrcode.make(text)
    img.save(out_path)
    return out_path, payload


if __name__ == "__main__":
    p, data = build_trust_qr(
        {"title": "Handwoven Jute Bag", "category": "handloom_textiles"},
        {"selling_price_inr": 288},
        {"compliance_ok": True, "required_labels": ["fabric_content", "care_instructions"]},
    )
    print("QR saved:", p)
    print(json.dumps(data, indent=2))
