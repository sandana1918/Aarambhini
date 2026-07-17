"""Pydantic schemas — the API's typed contracts (match the HLD collections)."""
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field


class Address(BaseModel):
    line: str = ""
    district: str = ""
    state: str = ""
    pincode: str = ""


class PackerLabel(BaseModel):
    name: str = ""
    address: str = ""


class SellerLicenses(BaseModel):
    fssai: Optional[str] = None
    bis: Optional[str] = None
    gstin: Optional[str] = None


class SellerCreate(BaseModel):
    phone: str = Field(..., min_length=8, max_length=15)
    name: str
    preferred_language: str = "hi"
    shg_name: Optional[str] = None
    address: Address = Address()
    packer_label: PackerLabel = PackerLabel()
    licenses: SellerLicenses = SellerLicenses()


class SellerRegister(SellerCreate):
    """Registration = seller details + the password she'll log in with."""
    password: str = Field(..., min_length=8, max_length=128)


class SellerOut(SellerCreate):
    id: str
    created_at: datetime


class SessionStart(BaseModel):
    """Log in: phone + password → a session token."""
    phone: str = Field(..., min_length=8, max_length=15)
    password: str = Field(..., min_length=1, max_length=128)


class SessionOut(BaseModel):
    token: str
    seller_id: str
    name: str
    expires_in_hours: int


class ListingRunRequest(BaseModel):
    seller_id: Optional[str] = None
    voice_text: str
    desired_margin_pct: int = 20
    # image handled as a separate multipart upload in a real flow; text-first here.


class ApprovalEdits(BaseModel):
    price: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    attributes: Optional[dict] = None


class ApprovalDecision(BaseModel):
    approved: bool
    notes: Optional[str] = None
    edits: Optional[ApprovalEdits] = None


class ClarificationAnswers(BaseModel):
    """Seller's answers to blocking-gap questions raised right after Suno."""
    cost_price_inr: Optional[int] = None
    # The category key she picked when it couldn't be determined from her words.
    # Validated against the real rule keys in the graph, not here — data/ is the
    # single source of truth for which categories exist.
    category: Optional[str] = None


class ReturnReport(BaseModel):
    """A real buyer return, logged so Wapsi learns from it.

    reason should be one of: size_mismatch, colour_mismatch, damaged,
    quality_issue, not_as_described, late_or_lost, other.
    """
    reason: str
    notes: Optional[str] = None


class AttributeAnswer(BaseModel):
    """Her spoken (or typed) answer to one missing product detail."""
    key: str
    spoken_text: str


class TranslateRequest(BaseModel):
    """Texts to render in her language. `to` defaults to her preferred_language."""
    texts: list[str] = []
    to: Optional[str] = None


class SpeakRequest(BaseModel):
    """Text to read aloud. `lang` defaults to her preferred_language."""
    text: str
    lang: Optional[str] = None


class ComplianceRule(BaseModel):
    category: str
    label: str = ""
    jurisdiction: str = "IN"
    regime: list[str] = []
    aliases: list[str] = []
    required_labels: list[str] = []
    required_licenses: list[str] = []
    optional_marks: list[str] = []
    label_template: str = ""
    label_overhead_inr: int = 0
    source_url: str = ""
    effective_date: Optional[str] = None
    needs_legal_review: bool = True
    notes: str = ""
    version: int = 1


class PriceBenchmark(BaseModel):
    category: str
    region: str = "IN"
    typical_low_inr: int
    typical_high_inr: int
    platform_fee_pct: float = 0
    shipping_flat_inr: int = 0
    fragile: bool = False
    perishable: bool = False
    packaging_overhead_inr: int = 0
    notes: str = ""
