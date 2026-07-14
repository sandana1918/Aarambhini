"""Read-only access to the seeded compliance rules + price benchmarks."""
from fastapi import APIRouter, HTTPException

from ..db import get_db, COMPLIANCE_RULES, PRICE_BENCHMARKS

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("")
async def list_rules():
    db = get_db()
    cur = db[COMPLIANCE_RULES].find({}, {"_id": 0})
    return await cur.to_list(length=100)


@router.get("/{category}")
async def get_rule(category: str):
    db = get_db()
    rule = await db[COMPLIANCE_RULES].find_one({"category": category}, {"_id": 0})
    if not rule:
        raise HTTPException(status_code=404, detail=f"No rule for category '{category}'")
    bench = await db[PRICE_BENCHMARKS].find_one({"category": category}, {"_id": 0})
    return {"rule": rule, "benchmark": bench}
