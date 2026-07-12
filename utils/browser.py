"""
Thin wrapper around Playwright for Amazon.in scraping.

NOTE: Amazon actively fingerprints and rate-limits scrapers. This wrapper does
the basic hygiene (realistic UA, viewport, slight delays) but for sustained /
production use you should route through a residential proxy or a scraping API
(set SCRAPER_PROXY_URL in .env) rather than relying on this alone.
"""
from __future__ import annotations
import asyncio
import random
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, BrowserContext, Page

import config

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


@asynccontextmanager
async def browser_context():
    async with async_playwright() as p:
        launch_kwargs = {"headless": config.HEADLESS}
        if config.SCRAPER_PROXY_URL:
            launch_kwargs["proxy"] = {"server": config.SCRAPER_PROXY_URL}

        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 900},
            locale="en-IN",
        )
        try:
            yield context
        finally:
            await context.close()
            await browser.close()


async def new_page(context: BrowserContext) -> Page:
    page = await context.new_page()
    page.set_default_timeout(20000)
    return page


async def human_delay(a: float = 0.6, b: float = 1.8) -> None:
    await asyncio.sleep(random.uniform(a, b))


async def safe_goto(page: Page, url: str, retries: int = 2) -> bool:
    """Returns True on success, False if all retries exhausted -- never raises."""
    for attempt in range(retries + 1):
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await human_delay()
            return True
        except Exception:
            if attempt == retries:
                return False
            await asyncio.sleep(1.5 * (attempt + 1))
    return False