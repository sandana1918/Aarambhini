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

from .models import ComplianceRule, PriceBenchmark

_DATA = os.path.join(os.path.dirname(__file__), "data")


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


async def seed():
    from .db import get_db, ensure_indexes, ping, COMPLIANCE_RULES, PRICE_BENCHMARKS

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

    print(f"Seeded {len(rules)} compliance rules and {len(benches)} price benchmarks into "
          f"'{db.name}'.")


def dry_run():
    rules = load_compliance_rules()
    benches = load_price_benchmarks()
    print(f"[dry-run] {len(rules)} compliance rules validated:")
    for r in rules:
        lic = ",".join(r["required_licenses"]) or "-"
        print(f"  - {r['category']:20s} labels={len(r['required_labels'])} licenses={lic}")
    print(f"[dry-run] {len(benches)} price benchmarks validated.")
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
