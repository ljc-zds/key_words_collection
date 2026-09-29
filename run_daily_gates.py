"""Compatibility wrapper for the renamed validation and publication command."""

from keyword_loop.workflows.validation_publish import run_validation_publish
from keyword_loop.workflows.validation_publish.cli import main


if __name__ == "__main__":
    main()
