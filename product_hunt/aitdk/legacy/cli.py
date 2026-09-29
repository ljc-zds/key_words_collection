import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import Response, async_playwright

from ..data.archive import unpack_extension_archive
from ..cdp.browser import content_script_ready_delay_ms, launch_isolated_context, traffic_result_timeout_ms
from ..cdp.cdp import collect_via_cdp
from ..cdp.collector import parse_event_stream


async def smoke(domain: str, archive: Path, edge: Path) -> int:
    """Run one normal extension query and print only its sanitized result."""
    runtime = Path("runtime")
    extension = unpack_extension_archive(archive, runtime / "extension")
    result: asyncio.Future[object] = asyncio.get_running_loop().create_future()

    async def inspect_response(response: Response) -> None:
        if "/api/v1/bulk" not in response.url:
            return
        try:
            record = parse_event_stream(await response.text())
        except Exception as error:  # Do not include response data in diagnostics.
            if not result.done():
                result.set_exception(RuntimeError(f"AITDK response could not be parsed: {type(error).__name__}"))
            return
        if record is not None and not result.done():
            result.set_result(record)

    def on_response(response: Response) -> None:
        asyncio.create_task(inspect_response(response))

    async with async_playwright() as playwright:
        context = await launch_isolated_context(playwright, edge, runtime / "profile", extension)
        context.on("response", on_response)
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(f"https://{domain}", wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(content_script_ready_delay_ms())
            await page.keyboard.press("Alt+D")
            await page.locator("#aitdk-iframe").wait_for(timeout=30_000)
            record = await asyncio.wait_for(result, timeout=traffic_result_timeout_ms())
            print(json.dumps(record.to_dict(), ensure_ascii=False))
        finally:
            await context.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one AITDK extension enrichment query.")
    parser.add_argument("domain")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--edge", type=Path)
    parser.add_argument("--cdp-url", help="Use an installed, logged-in AITDK extension in an existing Chrome session.")
    return parser


def main() -> None:
    parser = build_parser()
    arguments = parser.parse_args()
    if arguments.cdp_url:
        record = asyncio.run(collect_via_cdp(arguments.domain, arguments.cdp_url))
        print(json.dumps(record.to_dict(), ensure_ascii=False))
        return
    if not arguments.archive or not arguments.edge:
        parser.error("--archive and --edge are required unless --cdp-url is provided")
    raise SystemExit(asyncio.run(smoke(arguments.domain, arguments.archive, arguments.edge)))


if __name__ == "__main__":
    main()
