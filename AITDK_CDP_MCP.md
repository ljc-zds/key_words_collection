# AITDK Chrome CDP MCP

`mcp_tool/aitdk_mcp.py` is the local stdio MCP entry point. It reuses the AITDK extension
already installed and logged in within the Chrome instance started with remote
debugging enabled. It does not export extension cookies, request signatures,
headers, or raw response bodies.

## Prerequisites

Start Chrome with a debugging endpoint and ensure the AITDK extension is
installed and logged in in that profile:

```zsh
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --remote-allow-origins='*' \
  --user-data-dir="/Users/am/Documents/代码/key_words_collection/runtime/keyword-loop-profile"
```

## Codex configuration

Add this local server to the Codex MCP configuration:

```toml
[mcp_servers.aitdk-cdp-local]
command = "/Users/am/Documents/代码/key_words_collection/.venv/bin/python"
args = ["/Users/am/Documents/代码/key_words_collection/mcp_tool/aitdk_mcp.py"]

[mcp_servers.aitdk-cdp-local.env]
AITDK_CDP_URL = "http://127.0.0.1:9222"
```

## Tools

- `domain_enrich(domain, cdp_url?)`: returns sanitized domain traffic data:
  overview, traffic sources, top keywords, and any extension-provided Whois
  data.
- `health()`: returns the configured CDP endpoint without consuming AITDK
  query quota.

Each `domain_enrich` call creates a temporary Chrome tab, triggers the normal
AITDK extension flow, and parses only its `/api/v1/bulk` traffic event stream.
