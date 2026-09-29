# AITDK Playwright Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Launch an isolated browser with the supplied AITDK extension and emit a sanitized data record for one domain.

**Architecture:** A small Python package validates and unpacks the extension, then launches a persistent Chromium-compatible Playwright context with a project-local profile. It opens the extension using its documented Alt+D page shortcut, waits for the injected #aitdk-iframe, and parses only the traffic/Whois events from the normal plugin-generated event stream in memory before emitting a sanitized record.

**Tech Stack:** Python 3.11+, pytest, Playwright for Python, Microsoft Edge or Chromium.

---

## File Structure

- requirements.txt: runtime/test dependencies.
- .gitignore: excludes the unpacked extension, profile, outputs, and logs.
- aitdk_enrichment/archive.py: archive validation and unpacking.
- aitdk_enrichment/models.py: permitted collection record.
- aitdk_enrichment/redaction.py: diagnostic redaction.
- aitdk_enrichment/browser.py: isolated persistent context launcher.
- aitdk_enrichment/collector.py: normalizes plugin traffic event data.
- aitdk_enrichment/cli.py: one-domain smoke-test command.
- tests/test_*.py: deterministic unit tests plus an explicit integration smoke test.

### Task 1: Validate And Unpack The Extension

**Files:**
- Create: requirements.txt
- Create: .gitignore
- Create: aitdk_enrichment/__init__.py
- Create: aitdk_enrichment/archive.py
- Create: tests/test_archive.py

- [ ] **Step 1: Write the failing tests**

~~~python
from pathlib import Path
from zipfile import ZipFile

import pytest

from aitdk_enrichment.archive import ArchiveError, unpack_extension_archive


def test_unpack_extension_archive_returns_manifest_directory(tmp_path: Path) -> None:
    archive = tmp_path / "extension.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("2.7.0_0/manifest.json", '{"manifest_version": 3}')
    destination = tmp_path / "runtime" / "extension"
    assert unpack_extension_archive(archive, destination) == destination
    assert (destination / "manifest.json").is_file()


def test_unpack_extension_archive_rejects_missing_manifest(tmp_path: Path) -> None:
    archive = tmp_path / "invalid.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("extension/readme.txt", "missing manifest")
    with pytest.raises(ArchiveError, match="manifest.json"):
        unpack_extension_archive(archive, tmp_path / "runtime" / "extension")
~~~

- [ ] **Step 2: Run the tests to verify they fail**

Run: python -m pytest tests/test_archive.py -v

Expected: FAIL because aitdk_enrichment.archive does not exist.

- [ ] **Step 3: Write the minimal implementation**

~~~text
# requirements.txt
playwright==1.55.0
pytest==8.4.1

# .gitignore
.venv/
__pycache__/
.pytest_cache/
runtime/
output/
*.log
~~~

~~~python
# aitdk_enrichment/archive.py
from pathlib import Path
from zipfile import ZipFile


class ArchiveError(ValueError):
    pass


def unpack_extension_archive(archive: Path, destination: Path) -> Path:
    with ZipFile(archive) as bundle:
        manifests = [name for name in bundle.namelist() if name.endswith("/manifest.json")]
        if len(manifests) != 1:
            raise ArchiveError("archive must contain exactly one manifest.json")
        root = manifests[0].removesuffix("manifest.json")
        destination.mkdir(parents=True, exist_ok=True)
        for member in bundle.infolist():
            if not member.filename.startswith(root) or member.is_dir():
                continue
            relative = Path(member.filename.removeprefix(root))
            if relative.is_absolute() or ".." in relative.parts:
                raise ArchiveError("archive contains an unsafe path")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read(member))
    if not (destination / "manifest.json").is_file():
        raise ArchiveError("manifest.json was not unpacked")
    return destination
~~~

- [ ] **Step 4: Run the tests to verify they pass**

Run: python -m pytest tests/test_archive.py -v

Expected: PASS with 2 tests.

- [ ] **Step 5: Commit**

~~~bash
git add requirements.txt .gitignore aitdk_enrichment tests/test_archive.py
git commit -m "feat: validate and unpack AITDK extension archive"
~~~

### Task 2: Model And Redaction Boundary

**Files:**
- Create: aitdk_enrichment/models.py
- Create: aitdk_enrichment/redaction.py
- Create: tests/test_models.py
- Create: tests/test_redaction.py

- [ ] **Step 1: Write the failing tests**

~~~python
from aitdk_enrichment.models import CollectionRecord
from aitdk_enrichment.redaction import redact_diagnostic


def test_record_keeps_allowed_traffic_fields_only() -> None:
    record = CollectionRecord.from_plugin_data(
        "deno.com",
        {"overview": {"visits": "318295"}, "topKeywords": [{"name": "deno"}]},
    )
    assert record.domain == "deno.com"
    assert record.overview == {"visits": "318295"}
    assert record.top_keywords == [{"name": "deno"}]


def test_redact_diagnostic_removes_sensitive_query_values() -> None:
    text = "https://example.test/?domain=deno.com&signature=abc&nonce=def"
    redacted = redact_diagnostic(text)
    assert "signature=REDACTED" in redacted
    assert "nonce=REDACTED" in redacted
    assert "abc" not in redacted
~~~

- [ ] **Step 2: Run the tests to verify they fail**

Run: python -m pytest tests/test_models.py tests/test_redaction.py -v

Expected: FAIL because the model and redaction modules do not exist.

- [ ] **Step 3: Write the minimal implementation**

~~~python
# aitdk_enrichment/models.py
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CollectionRecord:
    domain: str
    title: str | None
    description: str | None
    overview: dict[str, Any]
    traffic_sources: dict[str, Any]
    top_keywords: list[dict[str, Any]]
    failure_reason: str | None = None

    @classmethod
    def from_plugin_data(cls, domain: str, data: dict[str, Any]) -> "CollectionRecord":
        return cls(
            domain=domain,
            title=data.get("title"),
            description=data.get("description"),
            overview=data.get("overview", {}),
            traffic_sources=data.get("trafficSources", {}),
            top_keywords=data.get("topKeywords", []),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
~~~

~~~python
# aitdk_enrichment/redaction.py
import re

_SENSITIVE = re.compile(r"(?i)(signature|nonce|secretKey|authorization|cookie)=([^&\s]+)")


def redact_diagnostic(text: str) -> str:
    return _SENSITIVE.sub(lambda match: f"{match.group(1)}=REDACTED", text)
~~~

- [ ] **Step 4: Run the tests to verify they pass**

Run: python -m pytest tests/test_models.py tests/test_redaction.py -v

Expected: PASS with 2 tests.

- [ ] **Step 5: Commit**

~~~bash
git add aitdk_enrichment tests/test_models.py tests/test_redaction.py
git commit -m "feat: add sanitized traffic record"
~~~

### Task 3: Isolated Browser And Smoke Command

**Files:**
- Create: aitdk_enrichment/browser.py
- Create: aitdk_enrichment/collector.py
- Create: aitdk_enrichment/cli.py
- Create: tests/test_browser.py
- Create: tests/test_collector.py
- Create: tests/test_browser_smoke.py

- [ ] **Step 1: Write the failing tests**

~~~python
from pathlib import Path

from aitdk_enrichment.browser import chromium_arguments
from aitdk_enrichment.collector import parse_traffic_event


def test_chromium_arguments_load_only_the_supplied_extension(tmp_path: Path) -> None:
    extension = tmp_path / "extension"
    extension.mkdir()
    arguments = chromium_arguments(extension)
    assert f"--disable-extensions-except={extension}" in arguments
    assert f"--load-extension={extension}" in arguments


def test_parse_traffic_event_returns_sanitized_record() -> None:
    event = {"domain": "deno.com", "data": {"overview": {"visits": "318295"}, "topKeywords": []}}
    assert parse_traffic_event(event).overview["visits"] == "318295"
~~~

- [ ] **Step 2: Run the tests to verify they fail**

Run: python -m pytest tests/test_browser.py tests/test_collector.py -v

Expected: FAIL because browser and collector modules do not exist.

- [ ] **Step 3: Write the minimal implementation**

~~~python
# aitdk_enrichment/browser.py
from pathlib import Path

from playwright.async_api import BrowserContext, Playwright


def chromium_arguments(extension_directory: Path) -> list[str]:
    return [
        f"--disable-extensions-except={extension_directory}",
        f"--load-extension={extension_directory}",
    ]


async def launch_isolated_context(
    playwright: Playwright,
    executable_path: Path,
    profile_directory: Path,
    extension_directory: Path,
) -> BrowserContext:
    profile_directory.mkdir(parents=True, exist_ok=True)
    return await playwright.chromium.launch_persistent_context(
        user_data_dir=str(profile_directory),
        executable_path=str(executable_path),
        headless=False,
        args=chromium_arguments(extension_directory),
    )
~~~

~~~python
# aitdk_enrichment/collector.py
from typing import Any

from .models import CollectionRecord


def parse_traffic_event(event: dict[str, Any]) -> CollectionRecord:
    domain, data = event.get("domain"), event.get("data")
    if not isinstance(domain, str) or not isinstance(data, dict):
        raise ValueError("traffic event requires domain and data")
    return CollectionRecord.from_plugin_data(domain, data)


def parse_event_stream(text: str) -> CollectionRecord | None:
    import json

    event_type = None
    for line in text.splitlines():
        if line.startswith("event:"):
            event_type = line.removeprefix("event:").strip()
        elif event_type == "traffic" and line.startswith("data:"):
            return parse_traffic_event(json.loads(line.removeprefix("data:").strip()))
    return None
~~~

~~~python
# aitdk_enrichment/cli.py
import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

from .archive import unpack_extension_archive
from .browser import launch_isolated_context


async def smoke(domain: str, archive: Path, edge: Path) -> int:
    runtime = Path("runtime")
    extension = unpack_extension_archive(archive, runtime / "extension")
    async with async_playwright() as playwright:
        context = await launch_isolated_context(playwright, edge, runtime / "profile", extension)
        traffic_event = None
        async def read_response(response):
            nonlocal traffic_event
            if response.request.resource_type != "eventsource":
                return
            from .collector import parse_event_stream
            traffic_event = parse_event_stream(await response.text())
        context.on("response", read_response)
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(f"https://{domain}", wait_until="domcontentloaded", timeout=60_000)
        await page.keyboard.press("Alt+D")
        await page.locator("#aitdk-iframe").wait_for(timeout=30_000)
        await page.wait_for_timeout(30_000)
        if traffic_event is None:
            raise RuntimeError("AITDK did not produce a traffic event")
        print(json.dumps(traffic_event.to_dict()))
        await context.close()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("domain")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--edge", type=Path, required=True)
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(smoke(arguments.domain, arguments.archive, arguments.edge)))


if __name__ == "__main__":
    main()
~~~

- [ ] **Step 4: Run unit tests and the opt-in smoke test**

Run: python -m pytest tests/test_browser.py tests/test_collector.py -v

Expected: PASS with 2 tests.

Run: python -m aitdk_enrichment.cli deno.com --archive '/Users/am/Library/Application Support/Microsoft Edge/Profile 1/Extensions/hhfkpjffbhledfpkhhcoidplcebgdgbk/2.7.0_0.zip' --edge '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'

Expected: an isolated browser window opens with the supplied extension, Alt+D opens #aitdk-iframe, and it emits a sanitized traffic/Whois record. The task succeeds only after plugin-generated traffic or Whois data is captured through the normal flow, without DevTools request copying.

- [ ] **Step 5: Commit**

~~~bash
git add aitdk_enrichment tests/test_browser.py tests/test_collector.py tests/test_browser_smoke.py
git commit -m "feat: add isolated AITDK browser smoke command"
~~~

## Plan Self-Review

- Spec coverage: the tasks cover archive isolation, permitted data fields, credential redaction, the normal extension path, and the deno.com verification.
- Placeholder scan: no undefined implementation names, TODO, or TBD markers remain.
- Type consistency: every entry point accepts Path for filesystem inputs; CollectionRecord.from_plugin_data() is defined before use.
- Repository note: this directory is not a Git repository. The listed commits apply only after the project is initialized or moved into its intended repository.
