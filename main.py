"""
uv run main.py "<brand name>"

Orchestrates the full pipeline:
  1. discovery_agent   -> is the brand on Amazon.in? what category?
  2. url_extractor     -> up to N real product URLs, ranked by rating count
  3. marketplace_agent -> per-product ratings, sellers, ad presence
  4. listing_quality   -> local Ollama audit of the top-rated product
  5. weakness_agent    -> 4-6 bullet weakness synthesis
  then writes output.xlsx (append) and <brand>.md

Every stage is wrapped so a failure degrades gracefully (empty/default data)
rather than crashing the whole run.
"""

from __future__ import annotations
import asyncio
import sys

import config
from schemas import (
    DiscoveryResult,
    MarketplaceSummary,
    ListingQualityResult,
    WeaknessReport,
    BrandIntelligence,
)
from utils.logger import banner, footer, log
from utils.browser import browser_context, new_page

from agents.discovery_agent import discover_brand
from agents.url_extractor import extract_product_urls
from agents.marketplace_agent import collect_marketplace_data
from agents.listing_quality_agent import audit_listing
from agents.weakness_agent import generate_weakness_report

from outputs.excel_writer import write_row
from outputs.markdown_writer import write_markdown

async def run_pipeline(brand_name: str) -> BrandIntelligence:
    banner(brand_name)

    discovery = DiscoveryResult(brand_name=brand_name)
    marketplace = MarketplaceSummary()
    listing_quality = ListingQualityResult()
    weakness = WeaknessReport()

    async with browser_context() as context:
        page = await new_page(context)

        # Stage 1: Discovery
        try:
            discovery = await discover_brand(page, brand_name)
        except Exception as e:
            log("discovery_agent", f"stage failed entirely ({e})", ok=False)

        if discovery.found_on_amazon:
            
        # Stage 2: URL extraction (reuses the search page already loaded)
            try:
                candidates = await extract_product_urls(page, brand_name)
            except Exception as e:
                log("url_extractor", f"stage failed entirely ({e})", ok=False)
                candidates = []

        # Stage 3: Marketplace data collection
            if candidates:
                try:
                    marketplace = await collect_marketplace_data(page, candidates)
                except Exception as e:
                    log("marketplace_agent", f"stage failed entirely ({e})", ok=False)
            else:
                log("marketplace_agent", "skipped, no product URLs to visit", ok=False)
        else:
            log("url_extractor", "skipped, brand not found on Amazon", ok=False)
            log("marketplace_agent", "skipped, brand not found on Amazon", ok=False)

        # Stage 4: Listing quality audit (LLM, no browser needed past this point)
    top_product = None
    if marketplace.products:
        top_product = max(marketplace.products, key=lambda p: p.rating_count, default=None)

    if top_product and top_product.breadcrumb:
        crumbs = top_product.breadcrumb
        if not discovery.category and len(crumbs) >= 1:
            discovery.category = crumbs[0]
        if not discovery.sub_category and len(crumbs) >= 2:
            discovery.sub_category = crumbs[-1]
        log(
            "discovery_agent",
            f"category refined from product breadcrumb: {discovery.category} → {discovery.sub_category}",
        )

    try:
        listing_quality = await audit_listing(top_product)
    except Exception as e:
        log("listing_quality", f"stage failed entirely ({e})", ok=False)

        # Stage 5: Weakness synthesis
    try:
        weakness = await generate_weakness_report(brand_name, discovery, marketplace, listing_quality)
    except Exception as e:
        log("weakness_agent", f"stage failed entirely ({e})", ok=False)

    result = BrandIntelligence(
        brand_name=brand_name,
        discovery=discovery,
        marketplace=marketplace,
        listing_quality=listing_quality,
        weakness=weakness,
        portals_live=["Amazon.in"] if discovery.found_on_amazon else [],
    )

        # Outputs
    write_row(result, config.EXCEL_OUTPUT_PATH)
    write_markdown(result, config.MARKDOWN_OUTPUT_DIR)

    footer(brand_name, success=True)
    return result


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: uv run main.py "<brand name>"')
        sys.exit(1)

    brand_name = sys.argv[1].strip()
    if not brand_name:
        print("Error: brand name cannot be empty")
        sys.exit(1)

    asyncio.run(run_pipeline(brand_name))


if __name__ == "__main__":
    main()