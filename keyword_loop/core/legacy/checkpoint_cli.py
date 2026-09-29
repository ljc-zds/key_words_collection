"""Inspect or update cross-day collection checkpoints."""
import argparse
from pathlib import Path

from ..data.checkpoint import CollectionCheckpoint
from ..data.store import KeywordStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage keyword collection checkpoints.")
    parser.add_argument("action", choices=("show", "set"))
    parser.add_argument("--source", required=True, choices=("stripe", "toolify", "root"))
    parser.add_argument("--database", type=Path, default=Path("output/keyword-loop.sqlite3"))
    parser.add_argument("--period")
    parser.add_argument("--position", type=int)
    parser.add_argument("--product")
    parser.add_argument("--root")
    parser.add_argument("--similarweb-page", type=int)
    args = parser.parse_args()
    store = KeywordStore(args.database)
    if args.action == "show":
        checkpoint = store.collection_checkpoint(args.source)
        print(checkpoint.serialize() if checkpoint else "not-set")
        return
    required = (args.period, args.position, args.product, args.root, args.similarweb_page)
    if any(value is None for value in required):
        parser.error("set requires --period, --position, --product, --root, and --similarweb-page")
    checkpoint = CollectionCheckpoint(args.source, args.period, args.position, args.product, args.root, args.similarweb_page)
    store.save_collection_checkpoint(checkpoint)
    print(checkpoint.serialize())


if __name__ == "__main__":
    main()
