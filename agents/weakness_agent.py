"""
Stage 5: Weakness Report Synthesis.
Uses the free local Ollama text model to produce 4-6 evidence-backed bullet
points from all collected structured data. Falls back to a rule-based
summary if Ollama isn't running or the call fails.
"""

from __future__ import annotations
import json

import httpx

import config
from schemas import DiscoveryResult, MarketplaceSummary, ListingQualityResult, WeaknessReport
from utils.logger import log

SYSTEM_PROMPT = """You are an e-commerce brand analyst. Given structured data about a \
brand's Amazon.in presence, write 4 to 6 bullet points identifying concrete weaknesses. \
Each bullet must cite a specific number or fact from the data (e.g. seller count, rating \
count, score, ad status) and be actionable. Do not invent data not present in the input.

Respond ONLY with valid JSON, no commentary: {"bullets": ["...", "...", ...]}"""


async def generate_weakness_report(
    brand_name: str,
    discovery: DiscoveryResult,
    marketplace: MarketplaceSummary,
    listing_quality: ListingQualityResult,
) -> WeaknessReport:
    try:
        payload_data = {
            "brand_name": brand_name,
            "found_on_amazon": discovery.found_on_amazon,
            "category": discovery.category,
            "sub_category": discovery.sub_category,
            "num_products_found": len(marketplace.products),
            "sellers": marketplace.sellers,
            "running_ads": marketplace.running_ads,
            "products_over_100_ratings": len(marketplace.products_over_100_ratings),
            "listing_quality_score": listing_quality.score,
            "listing_quality_summary": listing_quality.summary,
            "listing_dimensions": [
                {"dimension": d.dimension, "verdict": d.verdict.value, "notes": d.notes}
                for d in listing_quality.dimensions
            ],
        }

        request = {
            "model": config.OLLAMA_TEXT_MODEL,
            "system": SYSTEM_PROMPT,
            "prompt": json.dumps(payload_data, indent=2),
            "stream": False,
            "format": "json",
        }

        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(f"{config.OLLAMA_HOST}/api/generate", json=request)
            resp.raise_for_status()
            raw_text = resp.json().get("response", "")

        parsed = json.loads(raw_text.strip().strip("`"))
        bullets = parsed.get("bullets", [])[:6]

        if not bullets:
            raise ValueError("empty bullets from LLM")

        log("weakness_agent", f"{len(bullets)} weakness bullets generated")
        return WeaknessReport(bullets=bullets)

    except httpx.ConnectError:
        log("weakness_agent", "Ollama not running — using rule-based fallback", ok=False)
        return _fallback(discovery, marketplace, listing_quality)
    except Exception as e:
        log("weakness_agent", f"LLM synthesis failed ({type(e).__name__}: {e}), using rule-based fallback", ok=False)
        return _fallback(discovery, marketplace, listing_quality)

def _fallback(
    discovery: DiscoveryResult,
    marketplace: MarketplaceSummary,
    listing_quality: ListingQualityResult,
) -> WeaknessReport:
    bullets = []
    if not discovery.found_on_amazon:
        bullets.append("Brand not found on Amazon.in — no presence detected on the search results page.")
    if not marketplace.running_ads:
        bullets.append("No sponsored ads detected on Amazon — brand is not investing in paid visibility.")
    if len(marketplace.sellers) > 1:
        bullets.append(
            f"{len(marketplace.sellers)} distinct sellers found — brand may not have exclusive Buy Box control."
        )
    if listing_quality.score and listing_quality.score < 6:
        bullets.append(f"Top listing quality score is only {listing_quality.score}/10 — below acceptable threshold.")
    if len(marketplace.products_over_100_ratings) == 0:
        bullets.append("No products with more than 100 ratings — low social proof across the catalog.")
    if not bullets:
        bullets.append("Insufficient data collected to identify specific weaknesses; manual review recommended.")
    return WeaknessReport(bullets=bullets)