"""Compatibility entry point for the Google Trends CDP MCP server."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trend_radar.google_trends.mcp_server import *  # noqa: F403
from trend_radar.google_trends.mcp_server import main


if __name__ == "__main__":
    main()
