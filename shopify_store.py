"""Shopify seam — push an already-approved listing to her real storefront.

Deliberately NOT a node in the LangGraph crew. The approval gate is the
trust-critical step she vouches for; sending an already-approved, already-hers
listing to an external store is a separate action she triggers afterward. Same
single-seam idea as llm.py: one file owns the Shopify Admin API call, so the
rest of the app never knows which store it is.

Config (env, never committed):
  SHOPIFY_SHOP_DOMAIN        e.g. aarambhini-demo.myshopify.com
  SHOPIFY_ADMIN_ACCESS_TOKEN e.g. shpat_...
  SHOPIFY_API_VERSION        optional; defaults to a recent stable version
"""
import base64
import os
from pathlib import Path

from dotenv import load_dotenv

# Load the repo-root .env so this works standalone, same as llm.py.
load_dotenv(Path(__file__).resolve().parent / ".env")

_DEFAULT_API_VERSION = "2025-01"


def _config():
    return (
        os.getenv("SHOPIFY_SHOP_DOMAIN"),
        os.getenv("SHOPIFY_ADMIN_ACCESS_TOKEN"),
        os.getenv("SHOPIFY_API_VERSION", _DEFAULT_API_VERSION),
    )


def is_configured() -> bool:
    """True only if both the store domain and the token are set."""
    domain, token, _ = _config()
    return bool(domain and token)


_currency_cache = None


def shop_currency():
    """The store's currency code (e.g. 'INR', 'USD'), cached. None if unknown.

    Shopify shows a variant's price in the STORE currency — the product API can't
    set it per product. So a price of 294 shows as $294 on a USD store and ₹294 on
    an INR store. This lets the app detect a mismatch instead of shipping it silently.
    To show rupees: Shopify admin → Settings → Store details → Store currency → INR.
    """
    global _currency_cache
    if _currency_cache is not None:
        return _currency_cache or None
    domain, token, api_version = _config()
    if not (domain and token):
        return None
    try:
        import requests

        resp = requests.get(
            f"https://{domain}/admin/api/{api_version}/shop.json",
            headers={"X-Shopify-Access-Token": token},
            timeout=15,
        )
        resp.raise_for_status()
        _currency_cache = (resp.json().get("shop") or {}).get("currency") or ""
    except Exception:  # noqa: BLE001 - a currency read must never block publishing
        _currency_cache = ""
    return _currency_cache or None


def storefront_password():
    """The dev-store's public password, if set, so the UI can show it to a
    self-serve demo viewer. A dev store can't be made fully public (Shopify
    requires a plan), so for a demo this is the honest way to let a judge in.
    Env-driven, not hardcoded, so it never lands in the committed repo — it's a
    throwaway view-only password, but there's no reason to bake it into git.
    """
    return os.getenv("SHOPIFY_STOREFRONT_PASSWORD") or None


def _label_to_bullets(label: str) -> str:
    """Turn 'A: x, B: y, ...' label text into a clean bullet list.

    Splits on the field separators a label uses, but not on commas *inside* a
    value (an address is 'name, street, city' with no 'field:' colon), so each
    'Field: value' pair becomes one line and the address stays whole.
    """
    import re

    parts = re.split(r"\s*;\s*|\s*,(?=[^,]*?:)", label)
    items = [p.strip() for p in parts if p.strip()]
    return "".join(f"<li>{it}</li>" for it in items)


# Friendly, buyer-facing names for the raw attribute keys Likho fills in.
# Anything not listed falls back to a title-cased version of the key, so a new
# attribute still renders sensibly instead of being dropped.
_ATTR_LABELS = {
    "color": "Colour",
    "colour": "Colour",
    "material": "Material",
    "type": "Type",
    "gender": "Gender",
    "size": "Size",
    "age_group": "Age Group",
    "net_quantity": "Net Quantity",
    "compartments": "No. of Compartments",
    "dimensions": "Dimensions",
    "country_of_origin": "Country of Origin",
}


def _attr_rows(attributes: dict) -> str:
    """The full product spec (Colour, Gender, Type, Dimensions, ...) as list
    items. Skips empty values so a half-filled attribute never shows as a blank
    line, and gives each key a human label rather than a snake_case one.
    """
    if not attributes:
        return ""
    items = []
    for key, value in attributes.items():
        if value in (None, "", []):
            continue
        name = _ATTR_LABELS.get(key, key.replace("_", " ").title())
        items.append(f"<li><strong>{name}:</strong> {value}</li>")
    return "".join(items)


def _body_html(marketing: str, label: str, attributes: dict = None) -> str:
    """Buyer-facing copy first, then the full product spec, then the legal/
    compliance details — each as its own section, not run on to the end of the
    marketing paragraph.
    """
    html = ""
    if marketing:
        html += "<p>" + marketing.replace("\n", "<br>") + "</p>"
    attr_rows = _attr_rows(attributes)
    if attr_rows:
        html += (
            '<hr><p><strong>Product details</strong></p>'
            f"<ul>{attr_rows}</ul>"
        )
    if label:
        html += (
            '<hr><p><strong>Compliance details</strong></p>'
            f"<ul>{_label_to_bullets(label)}</ul>"
        )
    return html


def create_product(
    title: str,
    description: str,
    price,
    image_bytes: bytes = None,
    image_filename: str = None,
    tags=None,
    label: str = "",
    attributes: dict = None,
) -> dict:
    """Create a product on the store. Returns {id, storefront_url, admin_url}.

    The photo is sent inline as base64 (`attachment`), so there is no need to
    expose a public image URL — the bytes come straight from GridFS server-side.
    Raises on a missing config or a non-2xx from Shopify.
    """
    domain, token, api_version = _config()
    if not (domain and token):
        raise RuntimeError(
            "Shopify is not configured — set SHOPIFY_SHOP_DOMAIN and "
            "SHOPIFY_ADMIN_ACCESS_TOKEN."
        )

    import requests

    product = {
        "title": (title or "Handmade product").strip(),
        "body_html": _body_html(description, label, attributes),
        "vendor": "Aarambhini",
        "status": "active",
        # A price of None would make an unbuyable product; default to a variant
        # with no price rather than crash, but callers always pass one.
        "variants": [{"price": f"{int(price)}.00"}] if price else [{}],
    }
    if tags:
        product["tags"] = ", ".join(str(t) for t in tags)
    if image_bytes:
        product["images"] = [{
            "attachment": base64.b64encode(image_bytes).decode(),
            "filename": image_filename or "product.jpg",
        }]

    resp = requests.post(
        f"https://{domain}/admin/api/{api_version}/products.json",
        headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
        json={"product": product},
        timeout=30,
    )
    resp.raise_for_status()
    p = resp.json()["product"]
    handle = p.get("handle")
    currency = shop_currency()
    out = {
        "id": p["id"],
        # The public product page. On a fresh dev store this may sit behind a
        # storefront password (Online Store → Preferences) until it's removed.
        "storefront_url": f"https://{domain}/products/{handle}" if handle else None,
        # Always viewable by her, since she's logged into the admin.
        "admin_url": f"https://{domain}/admin/products/{p['id']}",
        "currency": currency,
    }
    # The price is in rupees; if the store isn't INR, Shopify will render the
    # wrong symbol. Surface it rather than shipping it silently.
    if currency and currency != "INR":
        out["currency_warning"] = (
            f"Store currency is {currency}, so ₹{int(price)} shows as a {currency} amount. "
            "Set it to INR in Shopify → Settings → Store details → Store currency."
        )
    return out
