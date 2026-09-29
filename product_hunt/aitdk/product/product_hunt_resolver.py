"""Resolve official product websites from Product Hunt detail pages."""

from playwright.async_api import async_playwright


def select_website_url(anchors: list[dict[str, str]]) -> str | None:
    for anchor in anchors:
        if anchor.get("text", "").strip().lower() == "visit website":
            return anchor.get("href")
    return None


async def resolve_product_urls(product_urls: list[str], edge_path: str) -> list[str | None]:
    """Open launch pages normally and retain their first external website link."""
    resolved: list[str | None] = []
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            "runtime/product-hunt-resolver", executable_path=edge_path, headless=False
        )
        page = context.pages[0] if context.pages else await context.new_page()
        for product_url in product_urls:
            await page.goto(product_url, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(2_000)
            anchors = await page.locator("a").evaluate_all(
                "elements => elements.map(a => ({text: a.innerText, href: a.href}))"
            )
            resolved.append(select_website_url(anchors))
        await context.close()
    return resolved
