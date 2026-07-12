"""
Stage 1: Brand Discovery.
Searches Amazon.in for the brand and infers category / sub-category from the
top results' breadcrumb / department filters.
"""
from __future__ import annotations
from urllib.parse import quote_plus

from playwright.async_api import Page

import config
from schemas import DiscoveryResult
from utils.browser import safe_goto
from utils.logger import log


async def discover_brand(page: Page, brand_name: str) -> DiscoveryResult:
    search_url = f"{config.AMAZON_BASE_URL}/s?k={quote_plus(brand_name)}"
    result = DiscoveryResult(brand_name=brand_name, search_url=search_url)

    ok = await safe_goto(page, search_url)
    if not ok:
        log("discovery_agent", "failed to load Amazon search page", ok=False)
        return result

    try:
        cards = page.locator('div[data-component-type="s-search-result"]')
        count = await cards.count()
        if count == 0:
            log("discovery_agent", f"'{brand_name}' not found on Amazon.in", ok=False)
            return result

        result.found_on_amazon = True

        dept_locator = page.locator(
            "#departments ul li span.a-size-base, "
            "#departments ul li a span"
        )
        dept_count = await dept_locator.count()
        if dept_count > 0:
            top_dept = (await dept_locator.first.inner_text()).strip()
            result.category = top_dept

        if dept_count > 1:
            result.sub_category = (await dept_locator.nth(1).inner_text()).strip()

        log(
            "discovery_agent",
            f"found on Amazon | category: {result.category or 'unknown'}, "
            f"sub_category: {result.sub_category or 'unknown'}",
        )
    except Exception as e:
        log("discovery_agent", f"partial failure during parsing ({e})", ok=False)

    return result