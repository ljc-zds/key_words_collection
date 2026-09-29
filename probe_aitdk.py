import asyncio
import argparse
from pathlib import Path

from playwright.async_api import async_playwright

from product_hunt.aitdk.cdp.browser import (
    content_script_ready_delay_ms,
    launch_chrome_installed_extension_context,
    prepare_chrome_extension_profile,
)


AITDK_EXTENSION_ID = 'hhfkpjffbhledfpkhhcoidplcebgdgbk'
CHROME_USER_DATA = Path('/Users/am/Library/Application Support/Google/Chrome')
CHROME = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')


async def main(domain: str) -> None:
    async with async_playwright() as playwright:
        profile = Path('runtime/chrome-probe-user-data')
        prepare_chrome_extension_profile(CHROME_USER_DATA, profile, AITDK_EXTENSION_ID)
        context = await launch_chrome_installed_extension_context(
            playwright, CHROME, profile
        )
        try:
            page = context.pages[0]
            await page.goto(f'https://{domain}', wait_until='domcontentloaded')
            await page.wait_for_timeout(content_script_ready_delay_ms())
            await page.keyboard.press('Alt+D')
            await page.locator('#aitdk-iframe').wait_for(state='attached', timeout=30_000)
            await page.wait_for_timeout(2_000)
            frame = page.frame_locator('#aitdk-iframe')
            await frame.get_by_text('Traffic', exact=True).click()
            text = ''
            for _ in range(15):
                await page.wait_for_timeout(1_000)
                text = await frame.locator('body').inner_text()
                if any(label in text for label in ('Total Visits', 'Monthly Visits', 'Traffic Sources')):
                    break
            print(text[:5000])
        finally:
            await context.close()


parser = argparse.ArgumentParser()
parser.add_argument('domain')
args = parser.parse_args()
asyncio.run(main(args.domain))
