"""10年保有できる優良企業ランキング（日本株）メイン実行スクリプト。"""

from __future__ import annotations

import argparse
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from src.fetch_data import fetch_stock_data
from src.fetch_jpx import fetch_jpx_topix500
from src.generate_pages import generate_auxiliary_pages
from src.generate_reports import generate_reports
from src.generate_site import generate_site
from src.scoring import score_all_stocks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="10年保有できる優良企業ランキング（日本株）静的サイト生成ツール")
    parser.add_argument("--limit", type=int, default=None, help="取得対象銘柄数の上限（テスト用）")
    parser.add_argument("--no-cache", action="store_true", help="ローカルキャッシュを無視して再取得")
    parser.add_argument("--workers", type=int, default=3, help="並列取得ワーカー数（デフォルト: 3）")
    args = parser.parse_args()

    t0 = time.time()
    base_dir = Path(__file__).resolve().parent
    cache_dir = base_dir / "cache"
    dist_dir = base_dir / "dist"
    use_cache = not args.no_cache

    logger.info("=== 10年保有できる優良企業ランキング（日本株）生成開始 ===")
    constituents = fetch_jpx_topix500(cache_dir=cache_dir, use_cache=use_cache, limit=args.limit)
    logger.info("母集団取得完了: %d 銘柄", len(constituents))

    stocks: list[dict] = []
    done_cnt = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futs = [
            pool.submit(fetch_stock_data, c, cache_dir, use_cache=use_cache, sleep_sec=0.2)
            for c in constituents
        ]
        for fut in as_completed(futs):
            done_cnt += 1
            res = fut.result()
            if res is not None and res.get("price", {}).get("current") is not None:
                stocks.append(res)
            if done_cnt % 50 == 0 or done_cnt == len(constituents):
                logger.info("進捗: %d / %d 銘柄処理済み（有効: %d 銘柄）", done_cnt, len(constituents), len(stocks))

    if not stocks:
        logger.error("有効銘柄が0件のため終了します。")
        return

    items, group_stats = score_all_stocks(stocks)
    logger.info("採点・軍分け完了（12業種グループ中 %d グループ）", len(group_stats))

    index_path = generate_site(items, group_stats, dist_dir=dist_dir)
    report_cnt = generate_reports(items, dist_dir=dist_dir)
    generate_auxiliary_pages(dist_dir=dist_dir)

    logger.info("=== 完了（%.1f秒）: %s / 個別レポート %d 件 / 補助ページ4件 ===", time.time() - t0, index_path, report_cnt)


if __name__ == "__main__":
    main()
