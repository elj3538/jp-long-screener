"""日本株の個別詳細レポート（dist/reports/<CODE>.html）を生成するモジュール。"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def _fmt(val: float | None, digits: int = 1, suffix: str = "") -> str:
    if val is None:
        return "―"
    return f"{val:.{digits}f}{suffix}"


def _build_price_svg(pts: list[dict[str, Any]]) -> str:
    if len(pts) < 2:
        return '<p style="color:var(--muted);font-size:12px;">株価推移データなし</p>'
    vals = [p["close"] for p in pts]
    v_min, v_max = min(vals), max(vals)
    span = (v_max - v_min) or 1.0
    w, h, pad = 620, 170, 22
    coords = []
    for i, p in enumerate(pts):
        x = pad + (w - pad * 2) * i / (len(pts) - 1)
        y = h - pad - (h - pad * 2) * (p["close"] - v_min) / span
        coords.append(f"{x:.1f},{y:.1f}")
    return f"""<svg viewBox="0 0 {w} {h}" style="width:100%;max-width:{w}px;height:auto;display:block;">
  <line x1="{pad}" y1="{pad}" x2="{w-pad}" y2="{pad}" stroke="var(--border)" stroke-dasharray="3,3"/>
  <line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{h-pad}" stroke="var(--border)"/>
  <polyline fill="none" stroke="var(--accent)" stroke-width="2.2" points="{' '.join(coords)}"/>
  <text x="{pad}" y="14" font-size="11" fill="var(--muted)">高値 ¥{v_max:,.0f}</text>
  <text x="{pad}" y="{h-5}" font-size="11" fill="var(--muted)">{pts[0]['date']}（安値 ¥{v_min:,.0f}）</text>
  <text x="{w-pad}" y="{h-5}" font-size="11" fill="var(--muted)" text-anchor="end">{pts[-1]['date']}（終値 ¥{vals[-1]:,.0f}）</text>
</svg>"""


def generate_reports(items: list[dict[str, Any]], dist_dir: Path) -> int:
    reports_dir = dist_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    for it in items:
        code = html.escape(it["code"])
        name = html.escape(it["name"])
        m = it["metrics"]
        det = it.get("detail", {})
        an = det.get("analyst", {})
        tier_label = f"{it['tier']}軍" if it["tier"] in (1, 2, 3) else "―"
        price_svg = _build_price_svg(det.get("price_series_weekly", []))
        close_str = f"¥{it['close']:,.0f}" if it["close"] is not None else "―"
        mcap_str = f"{it['market_cap_oku']:,.0f}億円" if it["market_cap_oku"] is not None else "―"

        page = f"""<!DOCTYPE html>
<html lang="ja" data-theme="genko" data-mode="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{code} {name}｜10年保有できる優良企業ランキング（日本株）</title>
<style>
:root {{ --bg:#f8fafc; --surface:#fff; --surface2:#f1f5f9; --text:#0f172a; --muted:#475569; --border:#e2e8f0; --accent:#1d4ed8; }}
[data-mode="dark"] {{ --bg:#0b1120; --surface:#111827; --surface2:#1e293b; --text:#f1f5f9; --muted:#94a3b8; --border:#334155; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Hiragino Kaku Gothic ProN","Yu Gothic",sans-serif; background:var(--bg); color:var(--text); font-size:14px; line-height:1.6; }}
a {{ color:var(--accent); text-decoration:none; }}
header {{ background:var(--surface); border-bottom:1px solid var(--border); padding:14px 16px; }}
.wrap {{ max-width:960px; margin:0 auto; padding:16px; }}
.nav {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:8px; font-size:13px; }}
.score-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; margin-bottom:16px; }}
.score-box {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:14px; }}
.score-val {{ font-size:30px; font-weight:800; color:var(--accent); }}
.card {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:16px; margin-bottom:16px; }}
.card h2 {{ margin:0 0 12px 0; font-size:16px; border-left:4px solid var(--accent); padding-left:8px; }}
table.kv {{ width:100%; border-collapse:collapse; font-size:13px; }}
table.kv th, table.kv td {{ padding:7px 8px; border-bottom:1px solid var(--border); text-align:left; }}
table.kv th {{ color:var(--muted); width:46%; font-weight:600; }}
table.kv td.num {{ text-align:right; font-weight:700; font-variant-numeric:tabular-nums; }}
</style>
</head>
<body>
<header>
  <div class="wrap" style="padding:0;">
    <div class="nav">
      <a href="../index.html">← ランキング一覧へ戻る</a>
      <a href="../watchlist.html">☆ ウォッチリスト</a>
      <a href="../portfolio.html">💼 ポートフォリオ</a>
      <a href="../guide.html">📖 使い方・見方</a>
    </div>
    <h1 style="margin:4px 0;font-size:22px;">{code} — {name}</h1>
    <div style="color:var(--muted);font-size:13px;">
      {html.escape(it['sector_group'])}（{html.escape(it['sector33'])}）｜ 業種級 {it.get('sector_grade','-')} ｜ <strong>{tier_label}</strong> ｜ カバレッジ {it['coverage']} ｜ 終値 <strong>{close_str}</strong> ｜ 時価総額 {mcap_str}
    </div>
  </div>
</header>
<div class="wrap">
  <div class="score-grid">
    <div class="score-box">
      <div style="font-size:12px;color:var(--muted);font-weight:600;">ファンダ点（品質スコア・0〜110）</div>
      <div class="score-val">{_fmt(it["funda_score"], 1)}</div>
      <div style="font-size:12px;color:var(--muted);">業績 {_fmt(it["perf_score"], 1)} / 財務 {_fmt(it["fin_score"], 1)} / CF {_fmt(it["cf_score"], 1)}</div>
    </div>
    <div class="score-box">
      <div style="font-size:12px;color:var(--muted);font-weight:600;">買い時スコア（0〜110）</div>
      <div class="score-val">{_fmt(it["buy_score"], 1)}</div>
      <div style="font-size:12px;color:var(--muted);">PER {_fmt(m["trailing_pe"], 1, "倍")} / PBR {_fmt(m["pbr"], 2, "倍")} / FCF利回り {_fmt(m["fcf_yield"], 2, "%")}</div>
    </div>
  </div>

  <section class="card">
    <h2>① 業績・財務・キャッシュフロー</h2>
    <table class="kv">
      <tr><th>売上高成長率（CAGR） / EPS成長率（CAGR）</th><td class="num">{_fmt(m["rev_cagr"], 1, "%")} / {_fmt(m["eps_cagr"], 1, "%")}</td></tr>
      <tr><th>営業利益率 / 利益安定度</th><td class="num">{_fmt(m["op_margin"], 1, "%")} / {_fmt(m["profit_stability"], 2)}</td></tr>
      <tr><th>直近四半期 売上YoY / 利益YoY</th><td class="num">{_fmt(m["q_rev_yoy"], 1, "%")} / {_fmt(m["q_profit_yoy"], 1, "%")}</td></tr>
      <tr><th>自己資本比率</th><td class="num">{_fmt(m["equity_ratio"], 1, "%")}</td></tr>
      <tr><th>D/Eレシオ / ネットD/E</th><td class="num">{_fmt(m["de_ratio"], 2, "倍")} / {_fmt(m["net_de"], 2, "倍")}</td></tr>
      <tr><th>有利子負債÷営業CF（返済年数）</th><td class="num">{_fmt(m["debt_to_ocf"], 2, "年")}</td></tr>
      <tr><th>営業CF / フリーCF / FCF配当性向</th><td class="num">{"黒字" if m["ocf_positive"] else "赤字/不明"} / {"黒字" if m["fcf_positive"] else "赤字/不明"} / {_fmt(m["fcf_payout"], 1, "%")}</td></tr>
    </table>
  </section>

  <section class="card">
    <h2>② 買い時・参考指標</h2>
    <table class="kv">
      <tr><th>EV/EBIT / 対業種中央値倍率</th><td class="num">{_fmt(m["ev_ebit"], 1, "倍")} / {_fmt(m["ev_ebit_rel"], 2, "倍")}</td></tr>
      <tr><th>FCF利回り</th><td class="num">{_fmt(m["fcf_yield"], 2, "%")}</td></tr>
      <tr><th>PER（実績） / 対業種倍率 / 過去レンジ位置</th><td class="num">{_fmt(m["trailing_pe"], 1, "倍")} / {_fmt(m["per_rel"], 2, "倍")} / {_fmt(m["per_range_pos"], 1, "%")}</td></tr>
      <tr><th>PBR（実績） / 対業種倍率</th><td class="num">{_fmt(m["pbr"], 2, "倍")} / {_fmt(m["pbr_rel"], 2, "倍")}</td></tr>
      <tr><th>ROE / ROA / 予想配当利回り（採点外参考）</th><td class="num">{_fmt(m["roe"], 1, "%")} / {_fmt(m["roa"], 1, "%")} / {_fmt(m["dividend_yield"], 2, "%")}</td></tr>
    </table>
  </section>

  <section class="card">
    <h2>株価推移（直近約2年）</h2>
    {price_svg}
    <div style="margin-top:8px;font-size:12px;color:var(--muted);">
      RSI(14): {_fmt(m.get("rsi14"), 1)} ｜ MACD: {_fmt(m.get("macd"), 2)} ｜ アナリスト目標株価平均: {f"¥{an['target_mean_price']:,.0f}" if an.get("target_mean_price") else "―"}
    </div>
  </section>
</div>
<script>
document.documentElement.setAttribute("data-theme", localStorage.getItem("pp_theme_jp_long") || "genko");
document.documentElement.setAttribute("data-mode", localStorage.getItem("pp_mode_jp_long") || "light");
</script>
</body>
</html>"""
        (reports_dir / f"{it['code']}.html").write_text(page, encoding="utf-8")
    return len(items)
