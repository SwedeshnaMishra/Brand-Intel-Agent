"""
Structured schemas shared across every agent in the pipeline.
Nothing downstream should ever consume free-form dicts -- always one of these.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Verdict(str, Enum):
    GOOD = "GOOD"
    MODERATE = "MODERATE"
    BAD = "BAD"


class DiscoveryResult(BaseModel):
    brand_name: str
    found_on_amazon: bool = False
    category: str = ""
    sub_category: str = ""
    search_url: str = ""


class ProductRecord(BaseModel):
    """One scraped Amazon product page."""
    url: str
    title: str = ""
    rating_count: int = 0
    star_rating: float = 0.0
    seller_name: str = ""
    is_sponsored: bool = False
    image_urls: list[str] = Field(default_factory=list)
    bullet_points: list[str] = Field(default_factory=list)
    description: str = ""
    breadcrumb: list[str] = Field(default_factory=list)



class MarketplaceSummary(BaseModel):
    products: list[ProductRecord] = Field(default_factory=list)
    sellers: list[str] = Field(default_factory=list)   # deduplicated
    running_ads: bool = False
    products_over_100_ratings: list[str] = Field(default_factory=list)  # URLs


class DimensionAssessment(BaseModel):
    dimension: str
    verdict: Verdict
    notes: str = ""


class ListingQualityResult(BaseModel):
    product_url: str = ""
    score: int = Field(default=0, ge=0, le=10)
    summary: str = ""
    dimensions: list[DimensionAssessment] = Field(default_factory=list)


class WeaknessReport(BaseModel):
    bullets: list[str] = Field(default_factory=list)


class BrandIntelligence(BaseModel):
    """Final aggregate object -- this is what gets written to Excel + Markdown."""
    brand_name: str
    discovery: DiscoveryResult
    marketplace: MarketplaceSummary
    listing_quality: ListingQualityResult
    weakness: WeaknessReport
    portals_live: list[str] = Field(default_factory=lambda: ["Amazon.in"])