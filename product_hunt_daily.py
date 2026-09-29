"""Compatibility wrapper for the Product Hunt and AITDK workflow."""

from product_hunt.pipeline import *  # noqa: F403
from product_hunt.pipeline import main


if __name__ == "__main__":
    main()
