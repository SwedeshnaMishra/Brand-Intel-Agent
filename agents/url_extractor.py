"""
Stage 2: Product URL Extraction.

Pulls up to MAX_PRODUCTS *real* product URLs from the Amazon search results
page (never constructed/guessed), sorted by rating count (popularity).
Also records, per-card, whether the "Sponsored" tag was present -- this feeds
the marketplace agent's ad-presence check without a second page load.

NOTE: sponsored cards link through an /sspa/click redirect rather than a
direct /dp/ URL. We still collect that href here -- it's a real Amazon link,
not guessed -- and let marketplace_agent capture the final resolved URL after
Playwright follows the redirect, which is the true canonical product URL.
"""
from __future__ import annotations
import re
from urllib.parse import urljoin

from playwright.async_api import Page

import config
from utils.logger import log

FAST_TIMEOUT_MS = 2500
MAX_CARDS_TO_SCAN = 20

async def extract_product_urls(page: Page, brand_name: str) -> list[dict]:
    """Returns a list of {url, rating_count, is_sponsored} dicts, real & deduped."""
    candidates: list[dict] = []

    try:
        cards = page.locator('div[data-component-type="s-search-result"]')
        count = min(await cards.count(), MAX_CARDS_TO_SCAN)

        for i in range(count):
            card = cards.nth(i)
            try:
                link = card.locator("a:has(h2)").first
                href = await link.get_attribute("href", timeout=FAST_TIMEOUT_MS)
                if not href:
                    continue
                url = urljoin(config.AMAZON_BASE_URL, href)

                rating_text = ""
                rating_locator = card.locator(
                    "span.s-underline-text, span[aria-label$='ratings']"
                )
                if await rating_locator.count() > 0:
                    try:
                        rating_text = await rating_locator.first.inner_text(
                            timeout=FAST_TIMEOUT_MS
                        )
                    except Exception:
                        rating_text = ""
                rating_count = _parse_rating_count(rating_text)

                h2 = card.locator("h2").first
                h2_aria = ""
                if await h2.count() > 0:
                    h2_aria = (await h2.get_attribute("aria-label", timeout=FAST_TIMEOUT_MS)) or ""
                sponsored = "sponsored" in h2_aria.lower() or (
                    await card.locator("span:has-text('Sponsored')").count() > 0
                )

                candidates.append(
                    {"url": url, "rating_count": rating_count, "is_sponsored": sponsored}
                )
            except Exception:
                continue  

    except Exception as e:
        log("url_extractor", f"failed to parse search results ({e})", ok=False)
        return []

    dedup: dict[str, dict] = {}
    for c in candidates:
        existing = dedup.get(c["url"])
        if not existing or c["rating_count"] > existing["rating_count"]:
            dedup[c["url"]] = c

    ranked = sorted(dedup.values(), key=lambda x: x["rating_count"], reverse=True)
    top = ranked[: config.MAX_PRODUCTS]

    log("url_extractor", f"{len(top)} amazon product URLs found")
    return top


def _parse_rating_count(text: str) -> int:
    """'(3K)' -> 3000, '(12,453)' -> 12453, '12,453 ratings' -> 12453."""
    if not text:
        return 0
    text = text.strip().strip("()")
    match = re.match(r"([\d,.]+)\s*([KkMm]?)", text)
    if not match:
        return 0
    number_str, suffix = match.groups()
    number_str = number_str.replace(",", "")
    try:
        number = float(number_str)
    except ValueError:
        return 0
    if suffix.upper() == "K":
        number *= 1_000
    elif suffix.upper() == "M":
        number *= 1_000_000
    return int(number)