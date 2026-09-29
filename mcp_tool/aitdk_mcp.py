"""Compatibility wrapper for the relocated AITDK CDP MCP server."""

from product_hunt.aitdk.protocol.mcp_server import *  # noqa: F403
from product_hunt.aitdk.protocol.mcp_server import main


if __name__ == "__main__":
    main()
