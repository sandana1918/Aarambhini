"""Full, realistic demo seed — a believable multi-category marketplace.

Resets the transactional collections (listings, image_fingerprints, audit_log,
GridFS product images, LangGraph checkpoints) and fills them with:

  * 7 SHG women sellers across states / languages,
  * 9 published listings across categories (incl. the licence-bearing ones:
    food/FSSAI, cosmetics, ayurvedic/AYUSH, toys/BIS) + 1 awaiting approval,
  * a distinct placeholder photo (GridFS) + pHash fingerprint per listing,
  * an approve_publish audit entry per published listing.

Prices come from the real Daam agent and packing plans from the real Packaging
agent, so the numbers are consistent with the live pipeline. Compliance is built
from data/compliance_rules.json. Idempotent — reruns reset and refill.

Run:
    python -m backend.seed_demo          # reference seed + demo marketplace
    python -m backend.seed_demo --keep   # keep existing test data, just add demo
"""
import io
import os
import csv
import sys
import json
import uuid
import asyncio
from datetime import datetime, timezone, timedelta

_DATA = os.path.join(os.path.dirname(__file__), "..", "data")


def _load_rules():
    with open(os.path.join(_DATA, "compliance_rules.json"), encoding="utf-8") as f:
        return json.load(f)


def _load_benchmarks():
    rows = {}
    with open(os.path.join(_DATA, "price_benchmarks.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["category"]] = r
    return rows


# ----------------------------------------------------------------- sellers
SELLERS = [
    {"phone": "9990000001", "name": "Sunita Devi", "preferred_language": "hi",
     "shg_name": "Aarambh Mahila SHG", "district": "Muzaffarpur", "state": "Bihar",
     "pincode": "842001", "licenses": {}},
    {"phone": "9990000002", "name": "Lakshmi Ammal", "preferred_language": "ta",
     "shg_name": "Kalvi Women's Collective", "district": "Madurai", "state": "Tamil Nadu",
     "pincode": "625001", "licenses": {"fssai": "12419026000123"}},
    {"phone": "9990000003", "name": "Ratna Barik", "preferred_language": "or",
     "shg_name": "Konark Handicraft SHG", "district": "Puri", "state": "Odisha",
     "pincode": "752012", "licenses": {}},
    {"phone": "9990000004", "name": "Meena Kumari", "preferred_language": "hi",
     "shg_name": "Marudhara Kala Samooh", "district": "Jaipur", "state": "Rajasthan",
     "pincode": "302001", "licenses": {}},
    {"phone": "9990000005", "name": "Anjali Nair", "preferred_language": "ml",
     "shg_name": "Kudumbashree Green Unit", "district": "Kollam", "state": "Kerala",
     "pincode": "691001", "licenses": {"ayush": "KL/AY/2023/00456"}},
    {"phone": "9990000006", "name": "Farah Sheikh", "preferred_language": "mr",
     "shg_name": "Roshni Bachat Gat", "district": "Kolhapur", "state": "Maharashtra",
     "pincode": "416001", "licenses": {}},
    {"phone": "9990000007", "name": "Kavya Reddy", "preferred_language": "kn",
     "shg_name": "Channapatna Killona Sangha", "district": "Ramanagara", "state": "Karnataka",
     "pincode": "562159", "licenses": {"bis": "CM/L-7300012345"}},
]


# --------------------------------------------------------------- products
# Rich per-product content; price/packaging come from the real agents, compliance
# from the rules base. img_rgb gives each a distinct placeholder photo + pHash.
PRODUCTS = [
    {
        "seller": "9990000001", "category": "handloom_textiles", "status": "published",
        "product_name": "Handwoven Jute Tote Bag", "material": "Jute",
        "cost": 200, "quantity": 40, "colour": "Natural Beige", "lang": "hi",
        "title": "Handwoven Jute Tote Bag — Eco-Friendly Everyday Shopping Bag",
        "description": "A sturdy handwoven jute tote made for daily errands and grocery runs. "
                       "Natural jute fibre, roomy interior and reinforced handles. Being handmade, "
                       "the weave and shade may vary slightly from the photo.",
        "maker_story": "Woven by hand by the women of Aarambh Mahila SHG in Muzaffarpur, Bihar.",
        "keywords": ["jute bag", "tote bag", "eco friendly bag", "handmade bag", "shopping bag", "natural jute"],
        "attrs": {"gender": "Women", "size": "Free Size", "fabric": "Jute", "pattern": "Woven Design", "occasion": "Daily"},
        "returns": {"top_return_reason": "colour/texture looks different from the screen", "risk_level": "medium",
                    "mitigations": ["add a natural-light photo", "state exact dimensions", "note handmade shade variation"]},
        "img_rgb": (196, 164, 120),
    },
    {
        "seller": "9990000002", "category": "food_packaged", "status": "published",
        "product_name": "Homemade Mango Pickle (Aam ka Achaar)", "material": None,
        "cost": 120, "quantity": 60, "colour": None, "lang": "ta",
        "title": "Homemade Mango Pickle — Traditional Aam ka Achaar, 250g",
        "description": "Sun-cured raw mango pickle made in small batches with cold-pressed sesame oil "
                       "and hand-ground spices. No artificial preservatives or colours. Best enjoyed "
                       "within the printed best-before date.",
        "maker_story": "Made to a family recipe by Lakshmi and the Kalvi Women's Collective, Madurai.",
        "keywords": ["mango pickle", "aam ka achaar", "homemade pickle", "traditional pickle", "no preservatives"],
        "attrs": {"net_weight": "250 g", "veg_nonveg": "Vegetarian", "food_type": "Pickle", "flavour": "Raw Mango",
                  "shelf_life": "9 months", "organic": "No"},
        "returns": {"top_return_reason": "leakage in transit or taste expectation", "risk_level": "high",
                    "mitigations": ["leak-proof jar + tamper seal", "print ingredients and best-before", "prefer regional delivery"]},
        "img_rgb": (206, 142, 58),
    },
    {
        "seller": "9990000004", "category": "imitation_jewellery", "status": "published",
        "product_name": "Oxidised Silver Jhumka Earrings", "material": "Oxidised Metal",
        "cost": 90, "quantity": 50, "colour": "Antique Silver", "lang": "hi",
        "title": "Oxidised Silver Jhumka Earrings — Handcrafted Ethnic Jhumkas",
        "description": "Lightweight oxidised-finish jhumkas with fine bead detailing, easy on the ears "
                       "for all-day festive wear. Nickel-free hooks. Adjustable drop length.",
        "maker_story": "Handcrafted by Meena and the Marudhara Kala Samooh artisans of Jaipur, Rajasthan.",
        "keywords": ["oxidised jhumka", "silver earrings", "ethnic earrings", "handmade jewellery", "festive earrings"],
        "attrs": {"gender": "Women", "base_metal": "Oxidised Metal", "plating": "Oxidised", "stone_type": "No Stone",
                  "type": "Earrings", "sizing": "Fixed"},
        "returns": {"top_return_reason": "smaller/larger than expected", "risk_level": "medium",
                    "mitigations": ["state exact drop length and weight", "add a photo against a hand for scale"]},
        "img_rgb": (120, 124, 130),
    },
    {
        "seller": "9990000003", "category": "handicrafts_decor", "status": "published",
        "product_name": "Terracotta Konark Wheel Wall Hanging", "material": "Terracotta",
        "cost": 260, "quantity": 20, "colour": "Earthen Brown", "lang": "or",
        "title": "Terracotta Konark Wheel Wall Hanging — Handmade Home Décor",
        "description": "A hand-moulded terracotta wall piece inspired by the Konark Sun Temple wheel, "
                       "kiln-fired and hand-finished. Each piece is unique; small natural variations are "
                       "part of the craft.",
        "maker_story": "Shaped by Ratna and the Konark Handicraft SHG near Raghurajpur, Puri, Odisha.",
        "keywords": ["terracotta decor", "wall hanging", "konark wheel", "handmade decor", "clay craft", "GI craft"],
        "attrs": {"material": "Terracotta", "product_type": "Wall Hanging", "dimensions": "25 x 25 x 3 cm", "finish": "Natural"},
        "returns": {"top_return_reason": "breakage in transit", "risk_level": "high",
                    "mitigations": ["bubble-wrap all sides", "double-wall box", "add a FRAGILE label"]},
        "img_rgb": (150, 96, 62),
    },
    {
        "seller": "9990000005", "category": "cosmetics_handmade", "status": "published",
        "product_name": "Handmade Neem & Tulsi Soap", "material": None,
        "cost": 70, "quantity": 80, "colour": "Herbal Green", "lang": "ml",
        "title": "Handmade Neem & Tulsi Soap — Cold-Process, 100g",
        "description": "A gentle cold-process soap with neem and tulsi, cured for four weeks. Free of "
                       "SLS and artificial colours. Suitable for daily use on most skin types.",
        "maker_story": "Made in small batches by the Kudumbashree Green Unit, Kollam, Kerala.",
        "keywords": ["neem soap", "handmade soap", "tulsi soap", "cold process soap", "natural soap", "sls free"],
        "attrs": {"net_weight": "100 g", "form": "Bar", "skin_type": "All Skin Types",
                  "key_ingredients": "Neem, Tulsi, Coconut Oil", "fragrance": "Herbal", "shelf_life": "12 months"},
        "returns": {"top_return_reason": "fragrance/skin-feel expectation", "risk_level": "low",
                    "mitigations": ["list full ingredients", "state it is unscented/lightly scented"]},
        "img_rgb": (120, 156, 96),
    },
    {
        "seller": "9990000006", "category": "home_furnishing", "status": "published",
        "product_name": "Cotton Block-Print Cushion Covers (Set of 2)", "material": "Cotton",
        "cost": 220, "quantity": 30, "colour": "Indigo Blue", "lang": "mr",
        "title": "Cotton Block-Print Cushion Covers — Set of 2, 16x16 inch",
        "description": "Hand block-printed 100% cotton cushion covers with a concealed zip. Colour-fast "
                       "natural dyes. Cushion inserts not included. Slight print irregularities reflect "
                       "the handmade block process.",
        "maker_story": "Block-printed by Farah and the Roshni Bachat Gat, Kolhapur, Maharashtra.",
        "keywords": ["cushion covers", "block print", "cotton cushion cover", "home decor", "handmade furnishing"],
        "attrs": {"material": "Cotton", "size": "Standard", "dimensions": "16 x 16 inch", "product_type": "Cushion Cover",
                  "pattern": "Printed", "pieces": 2},
        "returns": {"top_return_reason": "size/colour mismatch", "risk_level": "medium",
                    "mitigations": ["state exact inches and that inserts are excluded", "add a true-colour photo"]},
        "img_rgb": (58, 74, 140),
    },
    {
        "seller": "9990000006", "category": "candles_fragrance", "status": "published",
        "product_name": "Soy Wax Scented Jar Candle — Sandalwood", "material": "Soy Wax",
        "cost": 130, "quantity": 45, "colour": "Ivory", "lang": "mr",
        "title": "Soy Wax Scented Jar Candle — Sandalwood, 120g",
        "description": "A hand-poured soy wax candle in a reusable glass jar, with a cotton wick and "
                       "sandalwood fragrance. Approx. 20 hours burn time. Never leave a burning candle "
                       "unattended.",
        "maker_story": "Hand-poured by the Roshni Bachat Gat, Kolhapur, Maharashtra.",
        "keywords": ["soy candle", "scented candle", "jar candle", "sandalwood candle", "handmade candle"],
        "attrs": {"type": "Jar", "wax_type": "Soy Wax", "fragrance": "Sandalwood", "net_weight": "120 g", "burn_time": "~20 hours"},
        "returns": {"top_return_reason": "fragrance strength / melted in transit", "risk_level": "medium",
                    "mitigations": ["melt-safe packing", "state fragrance is subtle", "fragile handling label"]},
        "img_rgb": (224, 214, 190),
    },
    {
        "seller": "9990000005", "category": "ayurvedic_herbal", "status": "published",
        "product_name": "Amla & Bhringraj Hair Oil", "material": None,
        "cost": 150, "quantity": 40, "colour": None, "lang": "ml",
        "title": "Amla & Bhringraj Hair Oil — Herbal, 200ml",
        "description": "A traditional herbal hair oil infused with amla and bhringraj in a coconut oil "
                       "base, slow-cooked in small batches. For regular scalp massage. Patch-test before "
                       "first use.",
        "maker_story": "Prepared by the Kudumbashree Green Unit, Kollam, Kerala.",
        "keywords": ["amla hair oil", "bhringraj oil", "herbal hair oil", "ayurvedic hair oil", "natural hair care"],
        "attrs": {"net_weight": "200 ml", "form": "Oil", "key_ingredients": "Amla, Bhringraj, Coconut Oil",
                  "concern": "Hair Care", "shelf_life": "18 months"},
        "returns": {"top_return_reason": "scent/consistency expectation", "risk_level": "low",
                    "mitigations": ["list ingredients and directions", "state it is a herbal, not medicinal, product"]},
        "img_rgb": (86, 112, 64),
    },
    {
        "seller": "9990000007", "category": "toys_games", "status": "published",
        "product_name": "Channapatna Wooden Stacking Rings", "material": "Wood",
        "cost": 240, "quantity": 25, "colour": "Multicolour", "lang": "kn",
        "title": "Channapatna Wooden Stacking Rings — Safe Handmade Toy",
        "description": "A classic stacking-rings toy turned from ivory-wood and finished with food-grade "
                       "vegetable dyes, in the traditional Channapatna craft. Smooth, rounded edges. "
                       "Suitable for ages 1.5+.",
        "maker_story": "Turned and lacquered by Kavya and the Channapatna Killona Sangha, Karnataka.",
        "keywords": ["channapatna toy", "wooden toy", "stacking rings", "handmade toy", "safe wooden toy", "GI toy"],
        "attrs": {"material": "Wood", "age_group": "1.5-3 Years", "product_type": "Stacking Toy", "dimensions": "12 x 12 x 14 cm"},
        "returns": {"top_return_reason": "smaller than expected / colour", "risk_level": "low",
                    "mitigations": ["state exact dimensions and age grade", "note vegetable-dye colour"]},
        "img_rgb": (198, 96, 74),
    },
    {
        # One listing left awaiting the seller's approval, to show the pending state.
        "seller": "9990000001", "category": "handloom_textiles", "status": "ready_for_approval",
        "product_name": "Handwoven Cotton Table Runner", "material": "Cotton",
        "cost": 180, "quantity": 22, "colour": "Mustard & White", "lang": "hi",
        "title": "Handwoven Cotton Table Runner — Handloom, 14x72 inch",
        "description": "A handloom cotton table runner with a woven border, for everyday and festive "
                       "tables. Colour-fast. Gentle hand wash. Slight variation is natural to handloom.",
        "maker_story": "Woven by the Aarambh Mahila SHG, Muzaffarpur, Bihar.",
        "keywords": ["table runner", "handloom cotton", "woven runner", "home decor", "handmade runner"],
        "attrs": {"gender": "Unisex", "size": "Free Size", "fabric": "Cotton", "pattern": "Woven Design", "occasion": "Festive"},
        "returns": {"top_return_reason": "size/colour mismatch", "risk_level": "medium",
                    "mitigations": ["state exact inches", "add a true-colour photo"]},
        "img_rgb": (214, 176, 72),
    },
]


def _placeholder_image(rgb, label):
    """A distinct, recognisable placeholder photo per product (real bytes → GridFS)."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (600, 600), rgb)
    d = ImageDraw.Draw(img)
    d.rectangle([30, 30, 570, 570], outline=(255, 255, 255), width=4)
    # A little texture so each hash is distinct even at similar base colours.
    for i, ch in enumerate(label[:22]):
        d.text((44 + (i % 11) * 48, 500 + (i // 11) * 30), ch, fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return img, buf.getvalue()


def _compliance_for(rules, category, seller):
    cat = rules["categories"].get(category, {})
    required_labels = cat.get("required_labels", [])
    required_licenses = cat.get("required_licenses", [])
    thr = rules["gst"]["goods_threshold_inr"]
    gst_note = (f"Seller turnover assumed below the ₹{thr:,} GST threshold, so registration "
                "is likely not required. Confirm actual annual turnover.")
    packer = seller["name"]
    addr = f"{seller['district']}, {seller['state']} {seller['pincode']}"
    label_text = cat.get("label_template", "").replace("<packer_name>", packer) \
        .replace("<address>", addr).replace("<name>", packer) \
        .replace("<fbo_name>", packer)
    return {
        "compliance_ok": True,
        "required_labels": required_labels,
        "required_licenses": required_licenses,
        "gst_note": gst_note,
        "required_label_text": label_text,
        "label_overhead_inr": 5 if required_labels else 0,
        "category_notes": cat.get("notes", ""),
        "optional_marks": cat.get("optional_marks", []),
    }


def _activity_log(p, price, compliance, packaging, returns):
    """A plausible completed run, including the compliance loop when a label applies."""
    log = [
        {"agent": "Suno", "output": {"product_name": p["product_name"], "category": p["category"],
                                     "detected_language": p["lang"], "photo_ok": True}},
        {"agent": "Likho", "output": {"title": p["title"]}},
        {"agent": "Mukhiya (review)", "output": {"quality_ok": True}},
        {"agent": "Daam", "output": {"selling_price_inr": price["selling_price_inr"]}},
        {"agent": "Niyam", "output": {"compliance_ok": not compliance["required_labels"],
                                      "required_labels": compliance["required_labels"]}},
    ]
    if compliance["required_labels"]:
        log += [
            {"agent": "Likho (re-run #1)", "output": {"appended_disclaimers": [compliance["required_label_text"]]}},
            {"agent": "Daam (re-price #1)", "output": {"selling_price_inr": price["selling_price_inr"]}},
            {"agent": "Niyam (recheck #1)", "output": {"compliance_ok": True}},
        ]
    log += [
        {"agent": "Packaging", "output": {"primary_pack": packaging["primary_pack"]}},
        {"agent": "Wapsi", "output": {"risk_level": returns["risk_level"]}},
        {"agent": "Mukhiya (return review)", "output": {"return_action": "none"}},
    ]
    if p["status"] == "published":
        log.append({"agent": "Seller decision", "output": {"approved": True}})
    return log


async def seed_demo(keep_existing=False):
    from .db import get_db, ensure_indexes, ping, LISTINGS, AUDIT_LOG, IMAGE_FINGERPRINTS, SELLERS as SELLERS_COL
    from .seed import seed as seed_reference
    import graph_store
    from agents import daam as daam_agent
    from agents import packaging as packaging_agent

    # Reference data + demo sellers first (idempotent).
    await seed_reference()

    db = get_db()
    await ensure_indexes()

    if not keep_existing:
        for c in [LISTINGS, AUDIT_LOG, IMAGE_FINGERPRINTS, "return_events",
                  "checkpoints", "checkpoint_writes",
                  "product_images.files", "product_images.chunks"]:
            await db[c].delete_many({})
        print("Reset transactional collections (listings, fingerprints, audit, checkpoints, images).")

    rules = _load_rules()
    now = datetime.now(timezone.utc)

    # Upsert the full 7-seller roster (superset of seed.py's 3), idempotent by phone.
    for s in SELLERS:
        seller_doc = {
            "phone": s["phone"], "name": s["name"], "preferred_language": s["preferred_language"],
            "shg_name": s["shg_name"],
            "address": {"line": "", "district": s["district"], "state": s["state"], "pincode": s["pincode"]},
            "packer_label": {"name": s["name"], "address": f"{s['district']}, {s['state']} {s['pincode']}"},
            "licenses": {"fssai": s["licenses"].get("fssai"), "bis": s["licenses"].get("bis"),
                         "ayush": s["licenses"].get("ayush"), "gstin": None},
        }
        await db[SELLERS_COL].update_one(
            {"phone": s["phone"]},
            {"$set": seller_doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

    sellers_by_phone = {}
    async for s in db[SELLERS_COL].find({}):
        sellers_by_phone[s["phone"]] = s

    n_pub = 0
    cat_listing = {}  # category -> a listing id, to attach return events to
    for i, p in enumerate(PRODUCTS):
        seller_doc = sellers_by_phone.get(p["seller"])
        seller = next(s for s in SELLERS if s["phone"] == p["seller"])

        # Real deterministic agents for price + packaging.
        compliance = _compliance_for(rules, p["category"], seller)
        price = daam_agent.run(p["cost"], p["category"], desired_margin_pct=20,
                               extra_overhead_inr=compliance["label_overhead_inr"])
        packaging = packaging_agent.run(p["category"], p.get("material"))

        # Distinct placeholder photo → GridFS + pHash fingerprint.
        img, img_bytes = _placeholder_image(p["img_rgb"], p["product_name"])
        image_ref = graph_store.save_image(img_bytes, f"{p['category']}_{i}.png")
        ph = graph_store.phash(img)
        await db[IMAGE_FINGERPRINTS].insert_one({
            "phash": ph, "seller_id": seller_doc["_id"], "image_ref": image_ref,
            "created_at": now - timedelta(days=len(PRODUCTS) - i),
        })

        attrs = {"color": p.get("colour"), "country_of_origin": "India", **p["attrs"]}
        returns = {**p["returns"], "needs_seller_confirmation": False, "confirmation_prompt": None}
        checklist = []
        if compliance["required_label_text"]:
            checklist.append(f"Print & attach the label: {compliance['required_label_text']}")
        for lic in compliance["required_licenses"]:
            checklist.append(f"Keep ready: {lic.replace('_', ' ')}")
        checklist.append(f"Pack it: {packaging['primary_pack']} → {packaging['outer_pack']}")
        checklist.append(f"Approve to publish at ₹{price['selling_price_inr']}")

        created = now - timedelta(days=len(PRODUCTS) - i, hours=3)
        doc = {
            "seller_id": seller_doc["_id"],
            "thread_id": str(uuid.uuid4()),
            "image_ref": image_ref,
            "status": p["status"],
            "suno": {
                "product_name": p["product_name"], "quantity": p["quantity"],
                "cost_price_inr": p["cost"], "material": p.get("material"),
                "category": p["category"], "attributes": {"size": p["attrs"].get("size"), "colour": p.get("colour")},
                "photo_ok": True, "photo_issue": None,
                "photo_authenticity": "original", "authenticity_note": None,
                "detected_language": p["lang"],
            },
            "product_attributes": attrs,
            "missing_attributes": [],
            "authenticity": {"verdict": "ok", "flags": [], "phash": ph,
                             "photo_authenticity": "original", "note": None},
            "clarification": None,
            "listing": {
                "title": p["title"], "description": p["description"], "category": p["category"],
                "keywords": p["keywords"], "maker_story": p["maker_story"],
                "appended_disclaimers": [compliance["required_label_text"]] if compliance["required_label_text"] else [],
            },
            "price": price,
            "compliance": compliance,
            "returns": returns,
            "packaging_plan": packaging,
            "action_checklist": checklist,
            "approvals": [
                {"type": "go_live", "summary": "Publish this listing?"},
                {"type": "price", "summary": f"Set price ₹{price['selling_price_inr']}?"},
            ],
            "seller_notes": None,
            "activity_log": _activity_log(p, price, compliance, packaging, returns),
            "reason": None,
            "version": 1,
            "created_at": created,
            "updated_at": created,
            "_seed": True,
        }
        res = await db[LISTINGS].insert_one(doc)
        cat_listing[p["category"]] = res.inserted_id

        if p["status"] == "published":
            n_pub += 1
            await db[AUDIT_LOG].insert_one({
                "actor": seller_doc["_id"], "action": "approve_publish",
                "listing_id": res.inserted_id, "payload": {"notes": None},
                "ts": created + timedelta(minutes=4),
            })

    # Historical returns so Wapsi has real data to learn from immediately. Realistic
    # per-category reason distributions (decor breaks; furnishing = size; food damaged).
    return_history = {
        "handloom_textiles": {"colour_mismatch": 6, "size_mismatch": 3, "damaged": 1},
        "food_packaged": {"damaged": 9, "not_as_described": 4, "late_or_lost": 2},
        "imitation_jewellery": {"not_as_described": 4, "size_mismatch": 3, "damaged": 2},
        "handicrafts_decor": {"damaged": 11, "not_as_described": 2},
        "cosmetics_handmade": {"not_as_described": 2, "quality_issue": 1},
        "home_furnishing": {"size_mismatch": 7, "colour_mismatch": 4, "damaged": 1},
        "candles_fragrance": {"damaged": 5, "not_as_described": 3},
        "ayurvedic_herbal": {"not_as_described": 2},
        "toys_games": {"size_mismatch": 1, "damaged": 1},
    }
    events, day = [], 0
    for category, reasons in return_history.items():
        listing_id = cat_listing.get(category)
        for reason, count in reasons.items():
            for _ in range(count):
                day += 1
                events.append({
                    "listing_id": listing_id,
                    "seller_id": None,
                    "category": category,
                    "reason": reason,
                    "notes": None,
                    "attributes": {},
                    "created_at": now - timedelta(days=(day % 60)),
                })
    if events:
        await db["return_events"].insert_many(events)

    print(f"Seeded {len(PRODUCTS)} listings ({n_pub} published), "
          f"{len(PRODUCTS)} image fingerprints, {n_pub} audit entries, "
          f"{len(events)} return events.")
    print("Collections now filled:")
    for c in ["sellers", "listings", "compliance_rules", "price_benchmarks",
              "image_fingerprints", "audit_log", "product_images.files"]:
        print(f"  {c:22s}: {await db[c].count_documents({})}")


if __name__ == "__main__":
    asyncio.run(seed_demo(keep_existing="--keep" in sys.argv))
