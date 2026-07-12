"""
Stage 3: Marketplace Data Collection.

For each product URL, visit the page and extract rating count, seller name,
star rating, images, bullets and description (the latter three are reused by
the listing-quality agent so we don't re-scrape the top product twice).
"""

from __future__ import annotations
import re

from playwright.async_api import Page

from schemas import ProductRecord, MarketplaceSummary
from utils.browser import safe_goto
from utils.logger import log


async def collect_marketplace_data(
    page: Page, product_candidates: list[dict]
) -> MarketplaceSummary:
    products: list[ProductRecord] = []

    for cand in product_candidates:
        url = cand["url"]
        record = ProductRecord(url=url, is_sponsored=cand.get("is_sponsored", False))

        ok = await safe_goto(page, url)
        if not ok:
            log("marketplace_agent", f"could not load {url}", ok=False)
            products.append(record)  
            continue

        record.url = page.url

        try:
            record.title = await _text_or_default(page, "#productTitle")

            rating_text = await _text_or_default(
                page, "#acrCustomerReviewText"
            )
            record.rating_count = _parse_int(rating_text)
            if record.rating_count == 0 and cand.get("rating_count"):
                record.rating_count = cand["rating_count"]

            star_text = await _attr_or_default(page, "#acrPopover", "title")
            record.star_rating = _parse_float(star_text)

            record.seller_name = await _text_or_default(
                page, "#sellerProfileTriggerId, #merchant-info a, #merchant-info"
            )

            thumbs = page.locator("#altImages img")
            thumb_count = await thumbs.count()
            for i in range(min(thumb_count, 10)):
                src = await thumbs.nth(i).get_attribute("src")
                if src:
                    record.image_urls.append(src)

            bullets = page.locator("#feature-bullets li span.a-list-item")
            b_count = await bullets.count()
            for i in range(b_count):
                text = (await bullets.nth(i).inner_text()).strip()
                if text:
                    record.bullet_points.append(text)

            record.description = await _text_or_default(
                page, "#productDescription, #aplus"
            )

            crumb_links = page.locator(
                "#wayfinding-breadcrumbs_feature_div ul li a, "
                "#wayfinding-breadcrumbs_feature_div ul li span.a-list-item"
            )
            crumb_count = await crumb_links.count()
            for i in range(crumb_count):
                text = (await crumb_links.nth(i).inner_text()).strip()
                if text and text.lower() not in ("›", ">", ""):
                    record.breadcrumb.append(text)

        except Exception as e:
            log("marketplace_agent", f"partial extraction failure on {url} ({e})", ok=False)

        products.append(record)

    sellers = sorted({p.seller_name for p in products if p.seller_name})
    running_ads = any(p.is_sponsored for p in products)
    over_100 = [p.url for p in products if p.rating_count > 100]

    log(
        "marketplace_agent",
        f"{len(sellers)} sellers, running_ads: {running_ads}",
    )

    return MarketplaceSummary(
        products=products,
        sellers=sellers,
        running_ads=running_ads,
        products_over_100_ratings=over_100,
    )


async def _text_or_default(page: Page, selector: str, default: str = "") -> str:
    try:
        loc = page.locator(selector).first
        if await loc.count() == 0:
            return default
        return (await loc.inner_text()).strip()
    except Exception:
        return default


async def _attr_or_default(page: Page, selector: str, attr: str, default: str = "") -> str:
    try:
        loc = page.locator(selector).first
        if await loc.count() == 0:
            return default
        val = await loc.get_attribute(attr)
        return val or default
    except Exception:
        return default


def _parse_int(text: str) -> int:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else 0


def _parse_float(text: str) -> float:
    match = re.search(r"[\d.]+", text or "")
    return float(match.group()) if match else 0.0