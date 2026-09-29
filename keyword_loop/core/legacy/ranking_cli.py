import argparse
from dataclasses import dataclass
from pathlib import Path

from ..publishing.feishu import load_ranked_products_from_wiki, publish_wiki
from ..sources.rankings import RankedProduct, fetch_toolify_ranking
from ..clients.similarweb import SimilarwebCollector
from ..data.store import KeywordStore


@dataclass(frozen=True)
class RankingRunResult:
    product_count: int
    candidate_count: int
    failed_products: tuple[str, ...]
    published: bool = False


def product_identity(product: RankedProduct) -> str:
    return " ".join(product.name.lower().split())


def run_ranked_products(*, products: list[RankedProduct], database: Path, collector, review_limit: int) -> RankingRunResult:
    store = KeywordStore(database)
    failed_products: list[str] = []
    for product in products:
        try:
            for item in collector.collect(product.name):
                store.record(item)
                store.record_ranking_keyword(item.keyword, product_identity(product))
        except Exception as error:
            failed_products.append(product.name)
            store.record_failure(f"ranking:{product_identity(product)}", type(error).__name__)
    candidates = store.daily_candidates(minimum_volume=30_000, maximum_kd=60, limit=review_limit)
    return RankingRunResult(len(products), len(candidates), tuple(failed_products))


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Similarweb keyword candidates for products from a Feishu ranking sheet.")
    parser.add_argument("--rankings-feishu-url")
    parser.add_argument("--toolify-url", help="Public Toolify ranking page; bypasses Feishu ranking import")
    parser.add_argument("--ranking-sheet", default="Toolify排名")
    parser.add_argument("--results-feishu-url")
    parser.add_argument("--database", type=Path, default=Path("output/keyword-loop.sqlite3"))
    parser.add_argument("--browser", type=Path, default=Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
    parser.add_argument("--profile", type=Path, default=Path("runtime/keyword-loop-profile"))
    parser.add_argument("--cdp-url", help="Connect to an already-open Chrome, for example http://127.0.0.1:9222")
    parser.add_argument("--per-product-cap", type=int, default=500)
    parser.add_argument("--product-limit", type=int)
    parser.add_argument("--review-limit", type=int, default=10_000)
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    if not arguments.rankings_feishu_url and not arguments.toolify_url:
        parser.error("one of --rankings-feishu-url or --toolify-url is required")
    products = (fetch_toolify_ranking(arguments.toolify_url) if arguments.toolify_url
                else load_ranked_products_from_wiki(arguments.rankings_feishu_url, arguments.ranking_sheet))
    if arguments.product_limit:
        products = products[:arguments.product_limit]
    collector = SimilarwebCollector(
        browser=arguments.browser,
        profile=arguments.profile,
        per_root_cap=arguments.per_product_cap,
        cdp_url=arguments.cdp_url,
    )
    result = run_ranked_products(products=products, database=arguments.database, collector=collector, review_limit=arguments.review_limit)
    if not arguments.dry_run:
        if not arguments.results_feishu_url:
            raise ValueError("results_feishu_url is required unless --dry-run is used")
        candidates = KeywordStore(arguments.database).daily_candidates(minimum_volume=30_000, maximum_kd=60, limit=arguments.review_limit)
        publish_wiki(arguments.results_feishu_url, candidates)
        result = RankingRunResult(result.product_count, result.candidate_count, result.failed_products, True)
    print(f"products={result.product_count} candidates={result.candidate_count} published={result.published} failed_products={len(result.failed_products)}")


if __name__ == "__main__":
    main()
