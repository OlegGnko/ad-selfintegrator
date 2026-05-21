import json
import os
from playwright.sync_api import sync_playwright

RESTAURANTS = [
    {"name": "Trattoria Murano", "url": "https://www.facebook.com/trattoriamurano"},
    {"name": "Kuchnia Easy Diet", "url": "https://www.facebook.com/KuchniaEasyDiet/"},
    {"name": "Restauracja Kompromis", "url": "https://www.facebook.com/Restauracja.Kompromis"},
    {"name": "Sushi Muranów", "url": "https://www.facebook.com/sushimuranow"},
]


def _load_cookies() -> list:
    raw = os.environ.get("FB_COOKIES")
    if not raw:
        raise RuntimeError("FB_COOKIES environment variable is not set")
    cookies = json.loads(raw)
    result = []
    for c in cookies:
        cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ".facebook.com"),
            "path": c.get("path", "/"),
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", True),
        }
        # Cookie-Editor uses "expirationDate", Playwright uses "expires"
        exp = c.get("expirationDate") or c.get("expires")
        if exp:
            cookie["expires"] = int(exp)
        same_site = c.get("sameSite", "None")
        if same_site in ("no_restriction", "unspecified", ""):
            same_site = "None"
        cookie["sameSite"] = same_site
        result.append(cookie)
    return result


def _extract_page_text(page) -> str:
    """Return all visible text nodes from the page, deduplicated."""
    texts = page.evaluate("""
        () => {
            const seen = new Set();
            const result = [];
            const walker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_TEXT,
                null
            );
            let node;
            while ((node = walker.nextNode())) {
                const t = node.textContent.trim();
                if (t.length > 30 && !seen.has(t)) {
                    seen.add(t);
                    result.push(t);
                }
            }
            return result.join("\\n");
        }
    """)
    return texts[:10000]


def scrape_all() -> dict[str, str]:
    cookies = _load_cookies()
    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="pl-PL",
        )
        context.add_cookies(cookies)
        page = context.new_page()

        for r in RESTAURANTS:
            name = r["name"]
            try:
                print(f"  → {name}")
                page.goto(r["url"], wait_until="domcontentloaded", timeout=60_000)
                page.wait_for_timeout(4000)
                page.evaluate("window.scrollTo(0, 600)")
                page.wait_for_timeout(2000)
                results[name] = _extract_page_text(page)
            except Exception as exc:
                print(f"    ERROR: {exc}")
                results[name] = f"__error__: {exc}"

        browser.close()

    return results
