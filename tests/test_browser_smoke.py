import os
from pathlib import Path

import pytest


@pytest.mark.integration
def test_browser_smoke_requires_explicit_opt_in() -> None:
    """Prevent live AITDK queries from running as part of the normal test suite."""
    if os.environ.get("AITDK_RUN_BROWSER_SMOKE") != "1":
        pytest.skip("set AITDK_RUN_BROWSER_SMOKE=1 to run a live browser query")

    archive = Path(os.environ["AITDK_EXTENSION_ARCHIVE"])
    edge = Path(os.environ["AITDK_EDGE_EXECUTABLE"])
    assert archive.is_file()
    assert edge.is_file()
