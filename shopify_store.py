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


def _to_html(text: str) -> str:
    """The description carries the compliance label appended as plain text.
    Keep it readable; Shopify's body_html accepts basic HTML.
    """
    if not text:
        return ""
    return "<p>" + text.replace("\n", "<br>") + "</p>"


def create_product(
    title: str,
    description: str,
    price,
    image_bytes: bytes = None,
    image_filename: str = None,
    tags=None,
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
        "body_html": _to_html(description),
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
    return {
        "id": p["id"],
        # The public product page. On a fresh dev store this may sit behind a
        # storefront password (Online Store → Preferences) until it's removed.
        "storefront_url": f"https://{domain}/products/{handle}" if handle else None,
        # Always viewable by her, since she's logged into the admin.
        "admin_url": f"https://{domain}/admin/products/{p['id']}",
    }
