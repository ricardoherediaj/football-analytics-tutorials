"""WhoScored scraping: Playwright fetch + matchCentreData extraction."""

from __future__ import annotations

import json
import re
import sys

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
)


def fetch_match(url: str, headless: bool = True, wait_ms: int = 8000) -> dict:
    """Load a WhoScored match page in headless Chromium, return matchCentreData."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit(
            "Playwright is required to fetch WhoScored. Install with:\n"
            "  uv sync --extra scrape && uv run playwright install chromium"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=UA)
        page.goto(url, timeout=60_000, wait_until="domcontentloaded")
        page.wait_for_timeout(wait_ms)
        html = page.content()
        browser.close()

    data = _extract_match_centredata(html)
    if data is None:
        raise RuntimeError(
            "Could not find matchCentreData on the WhoScored page. The match may "
            "not exist or the page layout changed."
        )
    return data


def _extract_match_centredata(html: str) -> dict | None:
    patterns = [
        re.compile(r"matchCentreData:\s*(\{.*?\})\s*,\s*[\"']matchCentreEventTypeJson", re.S),
        re.compile(r"matchCentreData:\s*(\{.*?\})\s*\},\s*[\"']matchCentrePeriodJson", re.S),
    ]
    for pat in patterns:
        m = pat.search(html)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue

    idx = html.find("matchCentreData:")
    if idx == -1:
        return None
    start = html.find("{", idx)
    depth, i = 0, start
    while i < len(html):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    try:
        return json.loads(html[start : i + 1])
    except json.JSONDecodeError:
        return None
