import asyncio
import json
import re
from playwright.async_api import async_playwright
from datetime import datetime, timezone

from backend.config import SCANNER_1_URL, SCANNER_2_URL, SCANNER_1_NAME, SCANNER_2_NAME


async def scrape_chartink_screener(url: str, timeout: int = 30000) -> list[dict]:
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=timeout)
            await page.wait_for_timeout(3000)

            rows = await page.query_selector_all("table tbody tr")
            if not rows:
                rows = await page.query_selector_all("div.scanner-table-row")

            for row in rows:
                cells = await row.query_selector_all("td")
                if len(cells) < 2:
                    continue
                symbol_el = cells[0]
                price_el = cells[1]
                symbol = (await symbol_el.inner_text()).strip()
                price_text = (await price_el.inner_text()).strip()
                price = None
                try:
                    price = float(re.sub(r"[^\d.]", "", price_text))
                except ValueError:
                    pass
                if symbol:
                    results.append({"symbol": symbol, "price": price})
        except Exception as e:
            print(f"Error scraping {url}: {e}")
        finally:
            await browser.close()
    return results


def scrape_screener_sync(url: str, timeout: int = 30000) -> list[dict]:
    return asyncio.run(scrape_chartink_screener(url, timeout))


def scrape_both_scanners(timeout: int = 30000) -> dict:
    scanner_1_results = scrape_screener_sync(SCANNER_1_URL, timeout)
    scanner_2_results = scrape_screener_sync(SCANNER_2_URL, timeout)

    return {
        "scanner_1": {
            "name": SCANNER_1_NAME,
            "url": SCANNER_1_URL,
            "results": scanner_1_results,
            "count": len(scanner_1_results),
        },
        "scanner_2": {
            "name": SCANNER_2_NAME,
            "url": SCANNER_2_URL,
            "results": scanner_2_results,
            "count": len(scanner_2_results),
        },
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
