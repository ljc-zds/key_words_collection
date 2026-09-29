"""Compatibility wrapper for the renamed Similarweb/Semrush discovery command."""

from keyword_loop.workflows.discovery import (
    DiscoveryTotals,
    collect_and_gate_source,
    remaining_terms,
    semrush_target_reached,
    validate_semrush,
)
from keyword_loop.workflows.discovery.cli import main


if __name__ == "__main__":
    main()
