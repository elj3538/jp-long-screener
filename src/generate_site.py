"""採点済み日本株データから ranking.json と静的HTML（index.html）を生成するモジュール。"""

from __future__ import annotations

import html
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .fetch_jpx import GROUP_ORDER

JST = timezone(timedelta(hours=9))


def _fmt_num(val: float | None, digits: int = 1, suffix: str = "") -> str:
    if val is None:
        return "―"
    return f"{val:.{digits}f}{suffix}"


def _fmt_yen(val: float | None) -> str:
    if val is None:
        return "―"
    return f"¥{val:,.0f}"


def _fmt_pct(val: float | None, digits: int = 1) -> str:
    if val is None:
        return "―"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.{digits}f}%"


def _score_cls(val: float | None, high: float = 80.0, mid: float = 65.0) -> str:
    if val is None:
        return ""
    if val >= high:
        return "sc-good"
    if val >= mid:
        return "sc-warn"
    return "sc-weak"


def _ret_cls(val: float | None) -> str:
    if val is None:
        return ""
    if val > 0:
        return "pos"
    if val < 0:
        return "neg"
    return ""


def _tier_badge(tier: int) -> str:
    if tier in (1, 2, 3):
        return f'<span class="tier t{tier}">{tier}軍</span>'
    return '<span class="tier t0">―</span>'


def _build_row_html(item: dict[str, Any], rank_num: int | None = None, expand_returns: bool = False) -> str:
    m = item["metrics"]
    r = item.get("returns", {})
    tier = item["tier"]
    code = html.escape(item["code"])
    name = html.escape(item["name"])
    sec33 = html.escape(item["sector33"])
    grp = html.escape(item["sector_group"])

    badges = []
    if item["model"] == "financial":
        badges.append('<span class="badge-model" title="銀行・保険・証券専用スコアで採点">金融</span>')
    elif item["model"] == "lease":
        badges.append('<span class="badge-model" title="リース・信販専用スコアで採点">リース</span>')
    if item.get("rapid_decel"):
        badges.append('<span class="badge-warn" title="直近四半期で急減速">⚠急減速</span>')
    badge_html = " ".join(badges)

    attrs = {
        "data-code": code,
        "data-name": name,
        "data-sec33": sec33,
        "data-grp": grp,
        "data-tier": str(tier),
        "data-model": item["model"],
        "data-secgrade": item.get("sector_grade", "B"),
        "data-cov": item.get("coverage", "中"),
        "data-decel": "1" if item.get("rapid_decel") else "0",
        "data-f": "" if item["funda_score"] is None else str(item["funda_score"]),
        "data-perf": "" if item["perf_score"] is None else str(item["perf_score"]),
        "data-fin": "" if item["fin_score"] is None else str(item["fin_score"]),
        "data-cf": "" if item["cf_score"] is None else str(item["cf_score"]),
        "data-b": "" if item["buy_score"] is None else str(item["buy_score"]),
        "data-close": "" if item["close"] is None else str(item["close"]),
        "data-mcap": "" if item["market_cap_oku"] is None else str(item["market_cap_oku"]),
        "data-dy": "" if m["dividend_yield"] is None else str(m["dividend_yield"]),
        "data-roe": "" if m["roe"] is None else str(m["roe"]),
        "data-roa": "" if m["roa"] is None else str(m["roa"]),
        "data-eqr": "" if m["equity_ratio"] is None else str(m["equity_ratio"]),
        "data-fcfy": "" if m["fcf_yield"] is None else str(m["fcf_yield"]),
        "data-ocfpos": "1" if m["ocf_positive"] else "0",
        "data-fcfpos": "1" if m["fcf_positive"] else "0",
    }
    attr_str = " ".join(f'{k}="{html.escape(v)}"' for k, v in attrs.items())
    rank_td = f'<td class="num">{rank_num}</td>' if rank_num is not None else ""

    if expand_returns:
        ret_tds = "".join(f'<td class="num {_ret_cls(r.get(k))}">{_fmt_pct(r.get(k), 1)}</td>' for k in ("D", "W", "M", "3M", "6M", "9M", "Y"))
    else:
        ret_tds = (
            f'<td class="num ret-summary {_ret_cls(r.get("Y"))}">{_fmt_pct(r.get("Y"), 1)}</td>'
            + "".join(f'<td class="num ret-col {_ret_cls(r.get(k))}">{_fmt_pct(r.get(k), 1)}</td>' for k in ("D", "W", "M", "3M", "6M", "9M", "Y"))
        )

    return f"""<tr class="stock-row" {attr_str}>
  <td class="chk-cell"><input type="checkbox" class="wl-chk" data-code="{code}" aria-label="{code} ウォッチリスト"></td>
  <td class="chk-cell"><input type="checkbox" class="pf-chk" data-code="{code}" aria-label="{code} ポートフォリオ"></td>
  {rank_td}
  <td class="tier-cell">{_tier_badge(tier)}</td>
  <td class="sym-cell"><a href="reports/{code}.html" class="sym-link">{code}</a></td>
  <td class="name-cell"><a href="reports/{code}.html" class="name-link">{name}</a> {badge_html}</td>
  <td class="sec-cell">{sec33}</td>
  <td class="num">{_fmt_yen(item["close"])}</td>
  {ret_tds}
  <td class="num score-cell {_score_cls(item["funda_score"], 85, 70)}">{_fmt_num(item["funda_score"], 1)}</td>
  <td class="num">{_fmt_num(item["perf_score"], 1)}</td>
  <td class="num">{_fmt_num(item["fin_score"], 1)}</td>
  <td class="num">{_fmt_num(item["cf_score"], 1)}</td>
  <td class="num score-cell {_score_cls(item["buy_score"], 85, 65)}">{_fmt_num(item["buy_score"], 1)}</td>
  <td class="num">{_fmt_num(m["dividend_yield"], 2, "%")}</td>
  <td class="num">{_fmt_num(m["roe"], 1, "%")}</td>
  <td class="num">{_fmt_num(m["roa"], 1, "%")}</td>
  <td class="cov-cell"><span class="cov cov-{item["coverage"]}">{item["coverage"]}</span></td>
</tr>"""


def generate_site(items: list[dict[str, Any]], group_stats: dict[str, dict[str, Any]], dist_dir: Path) -> Path:
    dist_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    latest_dates = [it["latest_date"] for it in items if it.get("latest_date")]
    latest_price_date = max(latest_dates) if latest_dates else "-"

    payload = {
        "generated_at": generated_at,
        "latest_price_date": latest_price_date,
        "count": len(items),
        "group_stats": group_stats,
        "items": [
            {
                "code": it["code"],
                "name": it["name"],
                "sector33": it["sector33"],
                "sector_group": it["sector_group"],
                "sector_grade": it.get("sector_grade", "B"),
                "tier": it["tier"],
                "model": it["model"],
                "close": it["close"],
                "market_cap_oku": it["market_cap_oku"],
                "funda_score": it["funda_score"],
                "perf_score": it["perf_score"],
                "fin_score": it["fin_score"],
                "cf_score": it["cf_score"],
                "buy_score": it["buy_score"],
                "coverage": it["coverage"],
                "dividend_yield": it["metrics"]["dividend_yield"],
                "dividend_rate": it["metrics"]["dividend_rate"],
                "roe": it["metrics"]["roe"],
                "roa": it["metrics"]["roa"],
            }
            for it in items
        ],
    }
    (dist_dir / "ranking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    t1 = sum(1 for x in items if x["tier"] == 1)
    t2 = sum(1 for x in items if x["tier"] == 2)
    t3 = sum(1 for x in items if x["tier"] == 3)
    top50_rows = "\n".join(_build_row_html(it, rank_num=i + 1, expand_returns=True) for i, it in enumerate(items[:50]))

    by_group: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        by_group.setdefault(it["sector_group"], []).append(it)
    ordered_groups = [g for g in GROUP_ORDER if g in by_group] + [g for g in by_group if g not in GROUP_ORDER]

    group_sections = []
    for grp in ordered_groups:
        g_items = sorted(by_group[grp], key=lambda x: (x["funda_score"] if x["funda_score"] is not None else -1.0), reverse=True)
        st = group_stats.get(grp, {"count": len(g_items), "median": 0.0, "grade": "B"})
        rows_html = "\n".join(_build_row_html(it, expand_returns=False) for it in g_items)
        g_esc = html.escape(grp)
        group_sections.append(f"""
<section class="sector-block" data-grp="{g_esc}">
  <div class="sector-head">
    <h2>{g_esc}</h2>
    <div class="sector-meta">
      <span class="sec-grade sg-{st['grade']}">業種級 {st['grade']}</span>
      <span>中央値 {st['median']:.1f}</span>
      <span class="sec-count">{len(g_items)} 銘柄</span>
    </div>
  </div>
  <div class="table-wrap">
  <table class="rank-table sector-table">
    <thead>
      <tr>
        <th class="chk-col">☆</th>
        <th class="chk-col">💼</th>
        <th class="sortable" data-sort="tier">軍</th>
        <th class="sortable" data-sort="code">コード</th>
        <th class="sortable" data-sort="name">銘柄</th>
        <th class="sortable" data-sort="sec33">業種</th>
        <th class="num sortable" data-sort="close">終値</th>
        <th class="num"><button type="button" class="ret-toggle-btn">騰落率(展開)</button></th>
        <th class="num ret-col">D</th><th class="num ret-col">W</th><th class="num ret-col">M</th><th class="num ret-col">3M</th><th class="num ret-col">6M</th><th class="num ret-col">9M</th><th class="num ret-col">Y</th>
        <th class="num sortable" data-sort="f">ファンダ ▼</th>
        <th class="num sortable" data-sort="perf">業績</th>
        <th class="num sortable" data-sort="fin">財務</th>
        <th class="num sortable" data-sort="cf">CF</th>
        <th class="num sortable" data-sort="b">買い時</th>
        <th class="num sortable" data-sort="dy">利回り</th>
        <th class="num sortable" data-sort="roe">ROE</th>
        <th class="num sortable" data-sort="roa">ROA</th>
        <th class="sortable" data-sort="cov">カバレッジ</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
  </div>
</section>""")

    grp_options = "".join(f'<option value="{html.escape(g)}">{html.escape(g)}</option>' for g in ordered_groups)

    html_doc = f"""<!DOCTYPE html>
<html lang="ja" data-theme="genko" data-mode="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>10年保有できる優良企業ランキング（日本株）</title>
<style>
:root {{
  --bg: #f8fafc; --surface: #ffffff; --surface2: #f1f5f9; --text: #0f172a; --muted: #475569;
  --border: #e2e8f0; --accent: #1d4ed8; --accent-soft: #dbeafe; --good: #15803d; --good-bg: #dcfce7;
  --warn: #b45309; --warn-bg: #fef3c7; --weak: #b91c1c; --weak-bg: #fee2e2;
}}
[data-theme="blueplus"] {{ --accent: #0284c7; --accent-soft: #e0f2fe; }}
[data-theme="teal"] {{ --accent: #0f766e; --accent-soft: #ccfbf1; }}
[data-theme="slate"] {{ --accent: #334155; --accent-soft: #e2e8f0; }}
[data-theme="sand"] {{ --accent: #b45309; --accent-soft: #fef3c7; }}
[data-theme="violet"] {{ --accent: #6d28d9; --accent-soft: #ede9fe; }}
[data-theme="rose"] {{ --accent: #be123c; --accent-soft: #ffe4e6; }}
[data-mode="dark"] {{
  --bg: #0b1120; --surface: #111827; --surface2: #1e293b; --text: #f1f5f9; --muted: #94a3b8;
  --border: #334155; --accent-soft: #1e3a5f; --good: #4ade80; --good-bg: #14532d;
  --warn: #fbbf24; --warn-bg: #451a03; --weak: #f87171; --weak-bg: #450a0a;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif; background: var(--bg); color: var(--text); font-size: 14px; line-height: 1.5; padding-bottom: 70px; }}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
#theme-bar {{ display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 6px 16px; background: var(--surface2); border-bottom: 1px solid var(--border); font-size: 12px; }}
.theme-btn {{ border: 1px solid var(--border); background: var(--surface); color: var(--text); border-radius: 999px; padding: 2px 10px; cursor: pointer; font-size: 12px; }}
.theme-btn.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 16px; }}
.header-inner {{ max-width: 1440px; margin: 0 auto; }}
.header-top {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; }}
h1 {{ margin: 0; font-size: 22px; }}
.nav-links {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.nav-btn {{ display: inline-flex; align-items: center; gap: 4px; padding: 6px 12px; border-radius: 8px; border: 1px solid var(--border); background: var(--surface2); color: var(--text); font-size: 13px; font-weight: 600; }}
.nav-btn:hover {{ background: var(--accent-soft); text-decoration: none; }}
.meta-bar {{ margin-top: 8px; color: var(--muted); font-size: 12px; display: flex; flex-wrap: wrap; gap: 14px; }}
main {{ max-width: 1440px; margin: 0 auto; padding: 16px; }}
.tier-bar {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }}
.tier-filter {{ border: 1px solid var(--border); background: var(--surface); color: var(--text); padding: 7px 14px; border-radius: 10px; cursor: pointer; font-weight: 700; font-size: 13px; }}
.tier-filter.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
.toolbar {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; background: var(--surface); padding: 10px 12px; border: 1px solid var(--border); border-radius: 10px; }}
.toolbar input[type="search"] {{ flex: 1; min-width: 220px; padding: 7px 10px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg); color: var(--text); }}
.btn {{ border: 1px solid var(--border); background: var(--surface2); color: var(--text); padding: 7px 12px; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600; }}
.btn:hover {{ background: var(--accent-soft); }}
.btn-primary {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
.hit-count {{ font-weight: 700; color: var(--accent); margin-left: auto; }}
details.panel {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; margin-bottom: 12px; padding: 10px 14px; }}
details.panel > summary {{ cursor: pointer; font-weight: 700; font-size: 14px; list-style: none; display: flex; align-items: center; gap: 8px; }}
details.panel > summary::before {{ content: "▶"; font-size: 11px; transition: transform .15s; }}
details.panel[open] > summary::before {{ transform: rotate(90deg); }}
.filter-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; margin-top: 10px; }}
.f-item {{ display: flex; flex-direction: column; gap: 4px; font-size: 12px; }}
.f-item label {{ font-weight: 600; color: var(--muted); }}
.f-item input, .f-item select {{ padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text); }}
.f-checks {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; font-size: 13px; }}
.sector-block {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; margin-bottom: 16px; overflow: hidden; }}
.sector-head {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; padding: 10px 14px; background: var(--surface2); border-bottom: 1px solid var(--border); }}
.sector-head h2 {{ margin: 0; font-size: 16px; }}
.sector-meta {{ display: flex; gap: 10px; align-items: center; font-size: 12px; color: var(--muted); font-weight: 600; }}
.sec-grade {{ padding: 2px 8px; border-radius: 6px; font-weight: 700; }}
.sg-A {{ background: var(--good-bg); color: var(--good); }}
.sg-B {{ background: var(--accent-soft); color: var(--accent); }}
.sg-C {{ background: var(--warn-bg); color: var(--warn); }}
.table-wrap {{ overflow-x: auto; }}
table.rank-table {{ width: 100%; border-collapse: collapse; font-size: 13px; white-space: nowrap; }}
table.rank-table th, table.rank-table td {{ padding: 7px 8px; border-bottom: 1px solid var(--border); text-align: left; }}
table.rank-table th {{ background: var(--surface2); font-size: 12px; color: var(--muted); position: sticky; top: 0; z-index: 1; }}
table.rank-table th.sortable {{ cursor: pointer; }}
table.rank-table tbody tr:hover {{ background: var(--surface2); }}
.num {{ text-align: right !important; font-variant-numeric: tabular-nums; }}
.chk-col, .chk-cell {{ width: 32px; text-align: center !important; }}
.sym-link {{ font-weight: 700; }}
.name-link {{ color: var(--text); }}
.tier {{ display: inline-block; padding: 2px 7px; border-radius: 6px; font-weight: 700; font-size: 12px; }}
.t1 {{ background: var(--good-bg); color: var(--good); }}
.t2 {{ background: var(--accent-soft); color: var(--accent); }}
.t3, .t0 {{ background: var(--surface2); color: var(--muted); }}
.score-cell {{ font-weight: 700; }}
.sc-good {{ color: var(--good); }}
.sc-warn {{ color: var(--warn); }}
.sc-weak {{ color: var(--weak); }}
.pos {{ color: var(--good); }}
.neg {{ color: var(--weak); }}
.badge-model {{ background: var(--surface2); color: var(--muted); font-size: 11px; padding: 1px 5px; border-radius: 4px; border: 1px solid var(--border); }}
.badge-warn {{ background: var(--warn-bg); color: var(--warn); font-size: 11px; padding: 1px 5px; border-radius: 4px; font-weight: 700; }}
.cov {{ font-size: 11px; padding: 1px 6px; border-radius: 4px; font-weight: 700; }}
.cov-高 {{ background: var(--good-bg); color: var(--good); }}
.cov-中 {{ background: var(--accent-soft); color: var(--accent); }}
.cov-低 {{ background: var(--warn-bg); color: var(--warn); }}
.ret-col {{ display: none; }}
.returns-expanded .ret-col {{ display: table-cell; }}
.returns-expanded .ret-summary {{ display: none; }}
.ret-toggle-btn {{ border: 1px solid var(--border); background: var(--surface); color: var(--accent); border-radius: 5px; padding: 2px 6px; font-size: 11px; cursor: pointer; }}
#wlbar {{ position: fixed; bottom: 0; left: 0; right: 0; background: var(--surface); border-top: 2px solid var(--accent); padding: 10px 16px; display: none; align-items: center; gap: 12px; justify-content: center; z-index: 50; box-shadow: 0 -4px 12px rgba(0,0,0,.1); }}
#wlbar.show {{ display: flex; }}
</style>
</head>
<body>
<div id="hub-portal-bar" style="background:#0f172a;color:#e2e8f0;padding:7px 14px;display:flex;flex-wrap:wrap;align-items:center;gap:6px;font-size:12px;border-bottom:1px solid #1e293b;"><a href="https://elj3538.github.io/" style="color:#cbd5e1;background:transparent;padding:4px 10px;border-radius:6px;text-decoration:none;font-weight:600;white-space:nowrap;">🏠 ポータル</a><a href="https://elj3538.github.io/us-long-screener/" style="color:#cbd5e1;background:transparent;padding:4px 10px;border-radius:6px;text-decoration:none;font-weight:600;white-space:nowrap;">🇺🇸 米国10年保有</a><a href="https://elj3538.github.io/us-dividend-screener/" style="color:#cbd5e1;background:transparent;padding:4px 10px;border-radius:6px;text-decoration:none;font-weight:600;white-space:nowrap;">🇺🇸 米国配当株</a><a href="https://elj3538.github.io/jp-long-screener/" style="color:#ffffff;background:#2563eb;padding:4px 10px;border-radius:6px;text-decoration:none;font-weight:600;white-space:nowrap;">🇯🇵 日本10年保有</a><a href="https://elj3538.github.io/jp-dividend-screener/" style="color:#cbd5e1;background:transparent;padding:4px 10px;border-radius:6px;text-decoration:none;font-weight:600;white-space:nowrap;">🇯🇵 日本配当株</a></div>
<div id="theme-bar">
  <span>テーマ:</span>
  <button class="theme-btn" data-set-theme="genko">標準</button>
  <button class="theme-btn" data-set-theme="blueplus">ブルー</button>
  <button class="theme-btn" data-set-theme="teal">ティール</button>
  <button class="theme-btn" data-set-theme="slate">スレート</button>
  <button class="theme-btn" data-set-theme="sand">サンド</button>
  <button class="theme-btn" data-set-theme="violet">バイオレット</button>
  <button class="theme-btn" data-set-theme="rose">ローズ</button>
  <button class="theme-btn" id="mode-toggle" style="margin-left:auto;">🌙 ダーク切替</button>
</div>

<header>
  <div class="header-inner">
    <div class="header-top">
      <h1>10年保有できる優良企業ランキング（日本株）</h1>
      <nav class="nav-links">
        <a class="nav-btn" href="guide.html">📖 使い方・見方</a>
        <a class="nav-btn" href="watchlist.html">☆ ウォッチリスト</a>
        <a class="nav-btn" href="portfolio.html">💼 ポートフォリオ</a>
        <a class="nav-btn" href="terms.html">📜 利用規約・免責</a>
      </nav>
    </div>
    <div class="meta-bar">
      <span>更新: {generated_at}</span>
      <span>株価基準日: {latest_price_date}</span>
      <span>対象: TOPIX 500 相当（J-REIT除外・配当非採点・12業種グループ）</span>
    </div>
  </div>
</header>

<main>
  <div class="tier-bar">
    <button class="tier-filter active" data-tier="all">{len(items)} 全銘柄</button>
    <button class="tier-filter" data-tier="1">{t1} 1軍</button>
    <button class="tier-filter" data-tier="2">{t2} 2軍</button>
    <button class="tier-filter" data-tier="3">{t3} 3軍</button>
  </div>

  <div class="toolbar">
    <input type="search" id="search-input" placeholder="コード・銘柄名・業種で検索 (例: 7203, トヨタ, 電気機器)">
    <button class="btn" id="clear-btn">クリア</button>
    <button class="btn" id="csv-btn">📥 CSV出力</button>
    <button class="btn" id="tsv-btn">📋 コピー</button>
    <span class="hit-count" id="hit-count">{len(items)} 件表示</span>
  </div>

  <details class="panel" id="screener-panel">
    <summary>🔍 詳しい条件で絞り込む（詳細スクリーナー）</summary>
    <div class="filter-grid">
      <div class="f-item"><label>ファンダ点 以上</label><input type="number" id="f-f-min" placeholder="例: 80" step="1"></div>
      <div class="f-item"><label>買い時スコア 以上</label><input type="number" id="f-b-min" placeholder="例: 75" step="1"></div>
      <div class="f-item"><label>自己資本比率(%) 以上</label><input type="number" id="f-eqr-min" placeholder="例: 40" step="5"></div>
      <div class="f-item"><label>FCF利回り(%) 以上</label><input type="number" id="f-fcfy-min" placeholder="例: 5" step="0.5"></div>
      <div class="f-item"><label>予想配当利回り(%) 以上</label><input type="number" id="f-dy-min" placeholder="例: 3.0" step="0.1"></div>
      <div class="f-item"><label>ROE(%) 以上</label><input type="number" id="f-roe-min" placeholder="例: 10" step="1"></div>
      <div class="f-item"><label>ROA(%) 以上</label><input type="number" id="f-roa-min" placeholder="例: 5" step="1"></div>
      <div class="f-item"><label>時価総額(億円) 以上</label><input type="number" id="f-mcap-min" placeholder="例: 5000" step="500"></div>
      <div class="f-item"><label>終値(円) 以下</label><input type="number" id="f-close-max" placeholder="例: 5000" step="100"></div>
      <div class="f-item"><label>業種グループ</label><select id="f-grp"><option value="">すべて</option>{grp_options}</select></div>
      <div class="f-item"><label>業種級</label><select id="f-secgrade"><option value="">すべて</option><option value="A">A</option><option value="B">B</option><option value="C">C</option></select></div>
      <div class="f-item"><label>カバレッジ</label><select id="f-cov"><option value="">すべて</option><option value="高">高</option><option value="中">中</option><option value="低">低</option></select></div>
      <div class="f-item"><label>業種区分</label><select id="f-model"><option value="">すべて</option><option value="general">一般企業のみ</option><option value="special">金融・リースのみ</option></select></div>
    </div>
    <div class="f-checks">
      <label><input type="checkbox" id="f-no-decel"> 直近四半期の急減速なしのみ</label>
      <label><input type="checkbox" id="f-ocf-pos"> 営業CFプラスのみ</label>
      <label><input type="checkbox" id="f-fcf-pos"> フリーCFプラスのみ</label>
      <button class="btn" id="reset-filters" style="margin-left:auto;">条件をリセット</button>
    </div>
  </details>

  <details class="panel">
    <summary>💾 バックアップ（JSON保存/復元）</summary>
    <div style="margin-top:10px; display:flex; gap:10px;">
      <button class="btn" id="backup-export">バックアップを保存</button>
      <label class="btn" style="cursor:pointer;">ファイルから復元 <input type="file" id="backup-import" accept=".json" style="display:none;"></label>
    </div>
  </details>

  <details class="panel">
    <summary>🏆 全体 ファンダ点 上位50（業種横断）</summary>
    <div class="table-wrap" style="margin-top:10px;">
      <table class="rank-table">
        <thead>
          <tr>
            <th class="chk-col">☆</th><th class="chk-col">💼</th><th class="num">#</th><th>軍</th><th>コード</th><th>銘柄</th><th>業種</th><th class="num">終値</th>
            <th class="num">D</th><th class="num">W</th><th class="num">M</th><th class="num">3M</th><th class="num">6M</th><th class="num">9M</th><th class="num">Y</th>
            <th class="num">ファンダ</th><th class="num">業績</th><th class="num">財務</th><th class="num">CF</th><th class="num">買い時</th><th class="num">利回り</th><th class="num">ROE</th><th class="num">ROA</th><th>カバレッジ</th>
          </tr>
        </thead>
        <tbody>{top50_rows}</tbody>
      </table>
    </div>
  </details>

  <div id="sectors-container">{"".join(group_sections)}</div>
</main>

<div id="wlbar">
  <span id="wlbar-count">0 銘柄選択中</span>
  <a class="btn btn-primary" href="watchlist.html">☆ ウォッチリスト</a>
  <a class="btn" href="portfolio.html">💼 ポートフォリオ</a>
</div>

<script>
(function() {{
  const LS_THEME = "pp_theme_jp_long", LS_MODE = "pp_mode_jp_long", LS_WL = "pp_watchlist_jp_long", LS_PF = "pp_portfolio_jp_long";
  function applyTheme(t) {{ document.documentElement.setAttribute("data-theme", t); localStorage.setItem(LS_THEME, t); document.querySelectorAll("[data-set-theme]").forEach(b => b.classList.toggle("active", b.dataset.setTheme === t)); }}
  function applyMode(m) {{ document.documentElement.setAttribute("data-mode", m); localStorage.setItem(LS_MODE, m); }}
  applyTheme(localStorage.getItem(LS_THEME) || "genko");
  applyMode(localStorage.getItem(LS_MODE) || "light");
  document.querySelectorAll("[data-set-theme]").forEach(b => b.addEventListener("click", () => applyTheme(b.dataset.setTheme)));
  document.getElementById("mode-toggle").addEventListener("click", () => applyMode(document.documentElement.getAttribute("data-mode") === "dark" ? "light" : "dark"));

  let wlSet = new Set(JSON.parse(localStorage.getItem(LS_WL) || "[]"));
  let pfObj = JSON.parse(localStorage.getItem(LS_PF) || "{{}}");
  function syncChecks() {{
    document.querySelectorAll(".wl-chk").forEach(cb => cb.checked = wlSet.has(cb.dataset.code));
    document.querySelectorAll(".pf-chk").forEach(cb => cb.checked = Boolean(pfObj[cb.dataset.code]));
    document.getElementById("wlbar-count").textContent = `☆ ${{wlSet.size}}件 / 💼 ${{Object.keys(pfObj).length}}件 登録中`;
    document.getElementById("wlbar").classList.toggle("show", wlSet.size + Object.keys(pfObj).length > 0);
  }}
  document.addEventListener("change", (e) => {{
    if (e.target.classList.contains("wl-chk")) {{
      const c = e.target.dataset.code;
      if (e.target.checked) wlSet.add(c); else wlSet.delete(c);
      localStorage.setItem(LS_WL, JSON.stringify([...wlSet])); syncChecks();
    }} else if (e.target.classList.contains("pf-chk")) {{
      const c = e.target.dataset.code;
      if (e.target.checked) {{ if (!pfObj[c]) pfObj[c] = {{ shares: 100 }}; }} else {{ delete pfObj[c]; }}
      localStorage.setItem(LS_PF, JSON.stringify(pfObj)); syncChecks();
    }}
  }});
  syncChecks();

  document.getElementById("backup-export").addEventListener("click", () => {{
    const blob = new Blob([JSON.stringify({{ watchlist: [...wlSet], portfolio: pfObj }}, null, 2)], {{ type: "application/json" }});
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "jp_long_backup.json"; a.click();
  }});
  document.getElementById("backup-import").addEventListener("change", (e) => {{
    const file = e.target.files[0]; if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {{
      try {{
        const data = JSON.parse(reader.result);
        if (Array.isArray(data.watchlist)) wlSet = new Set(data.watchlist);
        if (data.portfolio && typeof data.portfolio === "object") pfObj = data.portfolio;
        localStorage.setItem(LS_WL, JSON.stringify([...wlSet])); localStorage.setItem(LS_PF, JSON.stringify(pfObj));
        syncChecks(); alert("復元しました！");
      }} catch (err) {{ alert("読み込みエラー: " + err); }}
    }};
    reader.readAsText(file);
  }});

  document.querySelectorAll(".ret-toggle-btn").forEach(btn => {{
    btn.addEventListener("click", () => {{
      const tbl = btn.closest("table");
      tbl.classList.toggle("returns-expanded");
      btn.textContent = tbl.classList.contains("returns-expanded") ? "騰落率(閉じる)" : "騰落率(展開)";
    }});
  }});

  let currentTier = "all";
  const nv = (id) => {{ const v = document.getElementById(id).value; return v === "" ? null : parseFloat(v); }};
  function applyFilters() {{
    const q = document.getElementById("search-input").value.trim().toLowerCase();
    const fMin = nv("f-f-min"), bMin = nv("f-b-min"), eqMin = nv("f-eqr-min"), fcfyMin = nv("f-fcfy-min");
    const dyMin = nv("f-dy-min"), roeMin = nv("f-roe-min"), roaMin = nv("f-roa-min"), mcMin = nv("f-mcap-min"), clMax = nv("f-close-max");
    const fGrp = document.getElementById("f-grp").value, fSg = document.getElementById("f-secgrade").value;
    const fCov = document.getElementById("f-cov").value, fMod = document.getElementById("f-model").value;
    const noDecel = document.getElementById("f-no-decel").checked, ocfPos = document.getElementById("f-ocf-pos").checked, fcfPos = document.getElementById("f-fcf-pos").checked;

    let vis = 0;
    document.querySelectorAll(".sector-block").forEach(secBlock => {{
      let sv = 0;
      secBlock.querySelectorAll("tbody tr.stock-row").forEach(tr => {{
        const d = tr.dataset; let ok = true;
        if (currentTier !== "all" && d.tier !== currentTier) ok = false;
        if (ok && q && !(d.code.toLowerCase().includes(q) || d.name.toLowerCase().includes(q) || d.sec33.toLowerCase().includes(q) || d.grp.toLowerCase().includes(q))) ok = false;
        if (ok && fMin !== null && (d.f === "" || parseFloat(d.f) < fMin)) ok = false;
        if (ok && bMin !== null && (d.b === "" || parseFloat(d.b) < bMin)) ok = false;
        if (ok && eqMin !== null && (d.eqr === "" || parseFloat(d.eqr) < eqMin)) ok = false;
        if (ok && fcfyMin !== null && (d.fcfy === "" || parseFloat(d.fcfy) < fcfyMin)) ok = false;
        if (ok && dyMin !== null && (d.dy === "" || parseFloat(d.dy) < dyMin)) ok = false;
        if (ok && roeMin !== null && (d.roe === "" || parseFloat(d.roe) < roeMin)) ok = false;
        if (ok && roaMin !== null && (d.roa === "" || parseFloat(d.roa) < roaMin)) ok = false;
        if (ok && mcMin !== null && (d.mcap === "" || parseFloat(d.mcap) < mcMin)) ok = false;
        if (ok && clMax !== null && (d.close === "" || parseFloat(d.close) > clMax)) ok = false;
        if (ok && fGrp && d.grp !== fGrp) ok = false;
        if (ok && fSg && d.secgrade !== fSg) ok = false;
        if (ok && fCov && d.cov !== fCov) ok = false;
        if (ok && fMod === "general" && d.model !== "general") ok = false;
        if (ok && fMod === "special" && d.model === "general") ok = false;
        if (ok && noDecel && d.decel === "1") ok = false;
        if (ok && ocfPos && d.ocfpos !== "1") ok = false;
        if (ok && fcfPos && d.fcfpos !== "1") ok = false;
        tr.style.display = ok ? "" : "none";
        if (ok) {{ sv++; vis++; }}
      }});
      secBlock.style.display = sv > 0 ? "" : "none";
      const ce = secBlock.querySelector(".sec-count"); if (ce) ce.textContent = `${{sv}} 銘柄`;
    }});
    document.getElementById("hit-count").textContent = `${{vis}} 件表示`;
  }}

  document.querySelectorAll(".tier-filter").forEach(b => b.addEventListener("click", () => {{
    currentTier = b.dataset.tier;
    document.querySelectorAll(".tier-filter").forEach(x => x.classList.toggle("active", x === b));
    applyFilters();
  }}));
  document.getElementById("search-input").addEventListener("input", applyFilters);
  document.querySelectorAll("#screener-panel input, #screener-panel select").forEach(el => el.addEventListener("input", applyFilters));
  document.getElementById("clear-btn").addEventListener("click", () => {{ document.getElementById("search-input").value = ""; applyFilters(); }});
  document.getElementById("reset-filters").addEventListener("click", () => {{
    document.querySelectorAll("#screener-panel input[type=number], #screener-panel select").forEach(el => el.value = "");
    document.querySelectorAll("#screener-panel input[type=checkbox]").forEach(el => el.checked = false);
    applyFilters();
  }});

  document.querySelectorAll(".sector-table th.sortable").forEach(th => {{
    let asc = false;
    th.addEventListener("click", () => {{
      const key = th.dataset.sort; asc = !asc;
      const tbody = th.closest("table").querySelector("tbody");
      const rows = Array.from(tbody.querySelectorAll("tr.stock-row"));
      rows.sort((a, b) => {{
        const va = a.dataset[key] || "", vb = b.dataset[key] || "";
        const na = parseFloat(va), nb = parseFloat(vb);
        if (!isNaN(na) && !isNaN(nb)) return asc ? na - nb : nb - na;
        return asc ? va.localeCompare(vb) : vb.localeCompare(va);
      }});
      rows.forEach(r => tbody.appendChild(r));
    }});
  }});

  function collectVisible() {{
    const out = [["軍", "コード", "銘柄", "業種", "業種グループ", "終値", "ファンダ点", "業績", "財務", "CF", "買い時", "利回り%", "ROE%", "ROA%", "カバレッジ"]];
    document.querySelectorAll(".sector-block tbody tr.stock-row").forEach(tr => {{
      if (tr.style.display === "none") return;
      const d = tr.dataset;
      out.push([d.tier === "0" ? "-" : d.tier + "軍", d.code, d.name, d.sec33, d.grp, d.close, d.f, d.perf, d.fin, d.cf, d.b, d.dy, d.roe, d.roa, d.cov]);
    }});
    return out;
  }}
  document.getElementById("csv-btn").addEventListener("click", () => {{
    const csv = "\\uFEFF" + collectVisible().map(r => r.map(v => `"${{String(v).replace(/"/g, '""')}}"`).join(",")).join("\\n");
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], {{ type: "text/csv;charset=utf-8;" }})); a.download = "jp_long_ranking.csv"; a.click();
  }});
  document.getElementById("tsv-btn").addEventListener("click", () => {{
    navigator.clipboard.writeText(collectVisible().map(r => r.join("\\t")).join("\\n")).then(() => alert("表示中の銘柄一覧をコピーしました！"));
  }});
}})();
</script>
</body>
</html>"""
    out = dist_dir / "index.html"
    out.write_text(html_doc, encoding="utf-8")
    return out
