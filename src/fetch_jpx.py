"""JPX「東証上場銘柄一覧」からTOPIX 500相当（Core30/Large70/Mid400）と東証33業種→12業種グループを取得するモジュール。"""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)

JPX_LIST_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xlsx"

# 東証33業種 → 参考サイト準拠の独自12業種グループ
SECTOR33_TO_GROUP: dict[str, str] = {
    "電気・ガス業": "資源・エネルギー",
    "鉱業": "資源・エネルギー",
    "石油・石炭製品": "資源・エネルギー",
    "金属製品": "素材",
    "繊維製品": "素材",
    "化学": "素材",
    "ガラス・土石製品": "素材",
    "鉄鋼": "素材",
    "非鉄金属": "素材",
    "パルプ・紙": "素材",
    "ゴム製品": "素材",
    "電気機器": "機械・電機",
    "精密機器": "機械・電機",
    "機械": "機械・電機",
    "輸送用機器": "自動車・輸送機",
    "卸売業": "商社・卸",
    "情報・通信業": "情報通信・サービス",
    "サービス業": "情報通信・サービス",
    "その他製品": "情報通信・サービス",
    "小売業": "生活必需・小売",
    "食料品": "生活必需・小売",
    "水産・農林業": "生活必需・小売",
    "医薬品": "医薬・ヘルスケア",
    "建設業": "建設・不動産",
    "不動産業": "建設・不動産",
    "陸運業": "インフラ・運輸",
    "空運業": "インフラ・運輸",
    "海運業": "インフラ・運輸",
    "倉庫・運輸関連業": "インフラ・運輸",
    "銀行業": "銀行・保険・証券",
    "保険業": "銀行・保険・証券",
    "証券、商品先物取引業": "銀行・保険・証券",
    "証券・商品先物取引業": "銀行・保険・証券",
    "その他金融業": "リース・信販・その他金融",
}

GROUP_ORDER: list[str] = [
    "資源・エネルギー",
    "素材",
    "機械・電機",
    "自動車・輸送機",
    "商社・卸",
    "情報通信・サービス",
    "生活必需・小売",
    "医薬・ヘルスケア",
    "建設・不動産",
    "インフラ・運輸",
    "銀行・保険・証券",
    "リース・信販・その他金融",
]

TOPIX500_SCALES = {"TOPIX Core30", "TOPIX Large70", "TOPIX Mid400"}

# オフライン・テスト用フォールバック（日本の代表大型株）
FALLBACK_CONSTITUENTS: list[dict[str, str]] = [
    {"code": "7203", "yf_symbol": "7203.T", "name": "トヨタ自動車", "sector33": "輸送用機器", "sector_group": "自動車・輸送機", "scale": "TOPIX Core30"},
    {"code": "6758", "yf_symbol": "6758.T", "name": "ソニーグループ", "sector33": "電気機器", "sector_group": "機械・電機", "scale": "TOPIX Core30"},
    {"code": "6861", "yf_symbol": "6861.T", "name": "キーエンス", "sector33": "電気機器", "sector_group": "機械・電機", "scale": "TOPIX Core30"},
    {"code": "8035", "yf_symbol": "8035.T", "name": "東京エレクトロン", "sector33": "電気機器", "sector_group": "機械・電機", "scale": "TOPIX Core30"},
    {"code": "6501", "yf_symbol": "6501.T", "name": "日立製作所", "sector33": "電気機器", "sector_group": "機械・電機", "scale": "TOPIX Core30"},
    {"code": "4063", "yf_symbol": "4063.T", "name": "信越化学工業", "sector33": "化学", "sector_group": "素材", "scale": "TOPIX Core30"},
    {"code": "8058", "yf_symbol": "8058.T", "name": "三菱商事", "sector33": "卸売業", "sector_group": "商社・卸", "scale": "TOPIX Core30"},
    {"code": "8001", "yf_symbol": "8001.T", "name": "伊藤忠商事", "sector33": "卸売業", "sector_group": "商社・卸", "scale": "TOPIX Core30"},
    {"code": "8031", "yf_symbol": "8031.T", "name": "三井物産", "sector33": "卸売業", "sector_group": "商社・卸", "scale": "TOPIX Core30"},
    {"code": "9432", "yf_symbol": "9432.T", "name": "日本電信電話", "sector33": "情報・通信業", "sector_group": "情報通信・サービス", "scale": "TOPIX Core30"},
    {"code": "9433", "yf_symbol": "9433.T", "name": "KDDI", "sector33": "情報・通信業", "sector_group": "情報通信・サービス", "scale": "TOPIX Core30"},
    {"code": "6098", "yf_symbol": "6098.T", "name": "リクルートホールディングス", "sector33": "サービス業", "sector_group": "情報通信・サービス", "scale": "TOPIX Core30"},
    {"code": "7974", "yf_symbol": "7974.T", "name": "任天堂", "sector33": "その他製品", "sector_group": "情報通信・サービス", "scale": "TOPIX Core30"},
    {"code": "9983", "yf_symbol": "9983.T", "name": "ファーストリテイリング", "sector33": "小売業", "sector_group": "生活必需・小売", "scale": "TOPIX Core30"},
    {"code": "4519", "yf_symbol": "4519.T", "name": "中外製薬", "sector33": "医薬品", "sector_group": "医薬・ヘルスケア", "scale": "TOPIX Large70"},
    {"code": "4568", "yf_symbol": "4568.T", "name": "第一三共", "sector33": "医薬品", "sector_group": "医薬・ヘルスケア", "scale": "TOPIX Core30"},
    {"code": "1925", "yf_symbol": "1925.T", "name": "大和ハウス工業", "sector33": "建設業", "sector_group": "建設・不動産", "scale": "TOPIX Large70"},
    {"code": "8801", "yf_symbol": "8801.T", "name": "三井不動産", "sector33": "不動産業", "sector_group": "建設・不動産", "scale": "TOPIX Core30"},
    {"code": "9020", "yf_symbol": "9020.T", "name": "東日本旅客鉄道", "sector33": "陸運業", "sector_group": "インフラ・運輸", "scale": "TOPIX Core30"},
    {"code": "1605", "yf_symbol": "1605.T", "name": "INPEX", "sector33": "鉱業", "sector_group": "資源・エネルギー", "scale": "TOPIX Large70"},
    {"code": "8306", "yf_symbol": "8306.T", "name": "三菱UFJフィナンシャル・グループ", "sector33": "銀行業", "sector_group": "銀行・保険・証券", "scale": "TOPIX Core30"},
    {"code": "8316", "yf_symbol": "8316.T", "name": "三井住友フィナンシャルグループ", "sector33": "銀行業", "sector_group": "銀行・保険・証券", "scale": "TOPIX Core30"},
    {"code": "8766", "yf_symbol": "8766.T", "name": "東京海上ホールディングス", "sector33": "保険業", "sector_group": "銀行・保険・証券", "scale": "TOPIX Core30"},
    {"code": "8591", "yf_symbol": "8591.T", "name": "オリックス", "sector33": "その他金融業", "sector_group": "リース・信販・その他金融", "scale": "TOPIX Large70"},
]


def fetch_jpx_topix500(
    cache_dir: Path | None = None,
    use_cache: bool = True,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """JPX東証上場銘柄一覧からTOPIX 500構成銘柄（Core30+Large70+Mid400）を取得する。"""
    cache_file = cache_dir / "jpx_topix500.json" if cache_dir else None
    if use_cache and cache_file and cache_file.exists():
        logger.info("キャッシュからJPX銘柄一覧を読み込みます: %s", cache_file)
        items = json.loads(cache_file.read_text(encoding="utf-8"))
        return items[:limit] if limit else items

    items: list[dict[str, Any]] = []
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(JPX_LIST_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        df = pd.read_excel(io.BytesIO(resp.content))

        for _, row in df.iterrows():
            market = str(row.get("市場・商品区分", "")).strip()
            if "内国株式" not in market:
                continue
            scale = str(row.get("規模区分", "")).strip()
            if scale not in TOPIX500_SCALES:
                continue
            raw_code = str(row.get("コード", "")).strip()
            if raw_code.endswith(".0"):
                raw_code = raw_code[:-2]
            if not raw_code or raw_code == "nan":
                continue
            sec33 = str(row.get("33業種区分", "")).strip()
            group = SECTOR33_TO_GROUP.get(sec33, "情報通信・サービス")
            name = str(row.get("銘柄名", raw_code)).strip()
            items.append(
                {
                    "code": raw_code,
                    "yf_symbol": f"{raw_code}.T",
                    "name": name,
                    "sector33": sec33,
                    "sector_group": group,
                    "scale": scale,
                }
            )
        logger.info("JPX公式一覧から TOPIX 500 構成銘柄 %d 件を取得しました。", len(items))
        if cache_file and items:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("JPX一覧の取得に失敗したためフォールバックを使用します: %s", exc)
        items = list(FALLBACK_CONSTITUENTS)

    return items[:limit] if limit else items
