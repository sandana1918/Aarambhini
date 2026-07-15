"""Seed compliance_rules + price_benchmarks into MongoDB Atlas.

Run:
    python -m backend.seed            # seeds Atlas (needs MONGODB_URI)
    python -m backend.seed --dry-run  # validates the data, no DB needed

Idempotent: upserts by category, so re-running refreshes rather than duplicates.
"""
import os
import csv
import sys
import json
import asyncio
from datetime import datetime, timezone

from .models import ComplianceRule, PriceBenchmark, SellerCreate

_DATA = os.path.join(os.path.dirname(__file__), "data")

# A few realistic SHG sellers so the seller_id flow is demonstrable out of the box.
# Kept small and clearly synthetic — phone numbers use the reserved 999xxxxxxx range.
_DEMO_SELLERS = [
    {
        "phone": "9990000001",
        "name": "Sunita Devi",
        "preferred_language": "hi",
        "shg_name": "Aarambh Mahila SHG",
        "address": {"line": "Ward 4, Near Panchayat Bhawan", "district": "Muzaffarpur",
                    "state": "Bihar", "pincode": "842001"},
        "packer_label": {"name": "Sunita Devi", "address": "Ward 4, Muzaffarpur, Bihar 842001"},
        "licenses": {"fssai": None, "bis": None, "gstin": None},
    },
    {
        "phone": "9990000002",
        "name": "Lakshmi Ammal",
        "preferred_language": "ta",
        "shg_name": "Kalvi Women's Collective",
        "address": {"line": "12 Bharathi Street", "district": "Madurai",
                    "state": "Tamil Nadu", "pincode": "625001"},
        "packer_label": {"name": "Lakshmi Ammal", "address": "12 Bharathi Street, Madurai, TN 625001"},
        "licenses": {"fssai": "12345678901234", "bis": None, "gstin": None},
    },
    {
        "phone": "9990000003",
        "name": "Ratna Barik",
        "preferred_language": "or",
        "shg_name": "Konark Handicraft SHG",
        "address": {"line": "Village Raghurajpur", "district": "Puri",
                    "state": "Odisha", "pincode": "752012"},
        "packer_label": {"name": "Ratna Barik", "address": "Raghurajpur, Puri, Odisha 752012"},
        "licenses": {"fssai": None, "bis": None, "gstin": None},
    },
]


def load_compliance_rules() -> list[dict]:
    with open(os.path.join(_DATA, "compliance_rules.json"), encoding="utf-8") as f:
        raw = json.load(f)
    docs = []
    for category, val in raw["categories"].items():
        rule = ComplianceRule(category=category, jurisdiction=raw["_meta"]["jurisdiction"], **val)
        docs.append(rule.model_dump())
    return docs


def load_price_benchmarks() -> list[dict]:
    docs = []
    with open(os.path.join(_DATA, "price_benchmarks.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            bench = PriceBenchmark(
                category=row["category"],
                region=row["region"],
                typical_low_inr=int(row["typical_low_inr"]),
                typical_high_inr=int(row["typical_high_inr"]),
                platform_fee_pct=float(row["platform_fee_pct"]),
                shipping_flat_inr=int(row["shipping_flat_inr"]),
                fragile=row["fragile"].strip().lower() == "true",
                perishable=row["perishable"].strip().lower() == "true",
                packaging_overhead_inr=int(row["packaging_overhead_inr"]),
                notes=row.get("notes", ""),
            )
            docs.append(bench.model_dump())
    return docs


def load_demo_sellers() -> list[dict]:
    """Validate the demo sellers through the same Pydantic model the API uses."""
    return [SellerCreate(**s).model_dump() for s in _DEMO_SELLERS]


async def seed():
    from .db import get_db, ensure_indexes, ping, COMPLIANCE_RULES, PRICE_BENCHMARKS, SELLERS

    await ping()
    await ensure_indexes()
    db = get_db()

    rules = load_compliance_rules()
    for r in rules:
        await db[COMPLIANCE_RULES].update_one({"category": r["category"]}, {"$set": r}, upsert=True)

    benches = load_price_benchmarks()
    for b in benches:
        await db[PRICE_BENCHMARKS].update_one(
            {"category": b["category"], "region": b["region"]}, {"$set": b}, upsert=True
        )

    # Demo sellers — upsert by phone so re-running refreshes rather than duplicates,
    # and set created_at only on first insert.
    sellers = load_demo_sellers()
    now = datetime.now(timezone.utc)
    for s in sellers:
        await db[SELLERS].update_one(
            {"phone": s["phone"]},
            {"$set": s, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

    print(f"Seeded {len(rules)} compliance rules, {len(benches)} price benchmarks, and "
          f"{len(sellers)} demo sellers into '{db.name}'.")


def dry_run():
    rules = load_compliance_rules()
    benches = load_price_benchmarks()
    sellers = load_demo_sellers()
    print(f"[dry-run] {len(rules)} compliance rules validated:")
    for r in rules:
        lic = ",".join(r["required_licenses"]) or "-"
        print(f"  - {r['category']:20s} labels={len(r['required_labels'])} licenses={lic}")
    print(f"[dry-run] {len(benches)} price benchmarks validated.")
    print(f"[dry-run] {len(sellers)} demo sellers validated:")
    for s in sellers:
        print(f"  - {s['name']:16s} {s['preferred_language']}  {s['shg_name']}")
    # Cross-check: every benchmark category has a rule and vice-versa.
    rc = {r["category"] for r in rules}
    bc = {b["category"] for b in benches}
    missing = rc ^ bc
    print("[dry-run] category parity:", "OK" if not missing else f"MISMATCH {missing}")


if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        dry_run()
    else:
        asyncio.run(seed())
