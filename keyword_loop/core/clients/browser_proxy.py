"""Small OpenCLI browser-proxy client used by keyword providers.

The client keeps one named browser lease for the lifetime of the provider and
only returns JSON network bodies. It deliberately has no DOM/screenshot API.
"""
from __future__ import annotations

import json
import subprocess
import time
import selectors
import uuid
from dataclasses import dataclass


class BrowserProxyError(RuntimeError):
    pass


def parse_json_output(output: str) -> dict:
    start = output.find("{")
    if start < 0:
        raise BrowserProxyError("OpenCLI returned no JSON")
    try:
        return json.JSONDecoder().raw_decode(output[start:])[0]
    except json.JSONDecodeError as exc:
        raise BrowserProxyError("OpenCLI returned invalid JSON") from exc


@dataclass
class OpenCliBrowser:
    prefix: str = "keyword-pipeline"
    executable: str = "opencli"

    def __post_init__(self) -> None:
        self.session = f"{self.prefix}-{uuid.uuid4().hex[:8]}"
        self.closed = False

    def run(self, *args: str) -> dict:
        result = subprocess.run([self.executable, "browser", self.session, *args], capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise BrowserProxyError(result.stderr.strip() or result.stdout.strip() or "OpenCLI command failed")
        return parse_json_output(result.stdout) if "{" in result.stdout else {}

    def close(self) -> None:
        if not self.closed:
            # OpenCLI may wait for a disconnected tab during close; cleanup is
            # best-effort and must never turn a successful fetch into a failure.
            try:
                subprocess.run([self.executable, "browser", self.session, "close"], capture_output=True, text=True, timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                pass
            self.closed = True

    def capture_after_open(self, url: str, *, path_fragment: str, timeout: int = 90) -> list[dict]:
        """Wait for the target XHR in the same lease, then read its cached body."""
        self.run("open", url)
        entries: list[dict] = []
        for _ in range(4):
            payload = self.run("network", "--raw", "--since", "10m")
            entries = [e for e in payload.get("entries", []) if path_fragment in e.get("url", "") and e.get("status") == 200]
            if entries:
                return entries
            self.run("wait", "time", "5")
        raise BrowserProxyError(f"No browser network response for {path_fragment}")

    def __enter__(self) -> "OpenCliBrowser":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
