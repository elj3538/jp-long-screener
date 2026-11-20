"""日本株10年保有スクリーナーの補助ページ（watchlist.html, portfolio.html, guide.html, terms.html）を生成するモジュール。"""

from __future__ import annotations

from pathlib import Path

_CSS = """
:root { --bg:#f8fafc; --surface:#fff; --surface2:#f1f5f9; --text:#0f172a; --muted:#475569; --border:#e2e8f0; --accent:#1d4ed8; }
[data-mode="dark"] { --bg:#0b1120; --surface:#111827; --surface2:#1e293b; --text:#f1f5f9; --muted:#94a3b8; --border:#334155; }
* { box-sizing:border-box; }
body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Hiragino Kaku Gothic ProN","Yu Gothic",sans-serif; background:var(--bg); color:var(--text); font-size:14px; line-height:1.65; }
a { color:var(--accent); text-decoration:none; }
header { background:var(--surface); border-bottom:1px solid var(--border); padding:14px 16px; }
.wrap { max-width:1120px; margin:0 auto; padding:16px; }
.nav { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:8px; font-size:13px; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:16px; margin-bottom:16px; }
.card h2 { margin:0 0 10px 0; font-size:17px; border-left:4px solid var(--accent); padding-left:8px; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th, td { padding:8px; border-bottom:1px solid var(--border); text-align:left; }
th { background:var(--surface2); color:var(--muted); font-size:12px; }
.num { text-align:right; font-variant-numeric:tabular-nums; }
.btn { border:1px solid var(--border); background:var(--surface2); color:var(--text); padding:6px 12px; border-radius:7px; cursor:pointer; font-size:12px; font-weight:600; }
.kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; margin-bottom:16px; }
.kpi { background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:14px; }
.kpi .label { font-size:12px; color:var(--muted); font-weight:600; }
.kpi .val { font-size:26px; font-weight:800; color:var(--accent); }
"""

_SCRIPT = """<script>
document.documentElement.setAttribute("data-theme", localStorage.getItem("pp_theme_jp_long") || "genko");
document.documentElement.setAttribute("data-mode", localStorage.getItem("pp_mode_jp_long") || "light");
</script>"""


def _shell(title: str, h1: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ja" data-theme="genko" data-mode="light">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}｜10年保有できる優良企業ランキング（日本株）</title><style>{_CSS}</style></head>
<body>
<header><div class="wrap" style="padding:0;">
  <div class="nav">
    <a href="index.html">🏠 ランキング</a>
    <a href="guide.html">📖 使い方・見方</a>
    <a href="watchlist.html">☆ ウォッチリスト</a>
    <a href="portfolio.html">💼 ポートフォリオ</a>
    <a href="terms.html">📜 利用規約・免責</a>
  </div>
  <h1 style="margin:4px 0;font-size:21px;">{h1}</h1>
</div></header>
<div class="wrap">{body}</div>
{_SCRIPT}</body></html>"""


def generate_auxiliary_pages(dist_dir: Path) -> None:
    dist_dir.mkdir(parents=True, exist_ok=True)

    wl_body = """
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
    <h2 style="margin:0;">☆ 登録銘柄一覧</h2>
    <button class="btn" id="clear-wl">すべて解除</button>
  </div>
  <div style="overflow-x:auto;"><table>
    <thead><tr><th>コード</th><th>銘柄</th><th>業種</th><th>軍</th><th class="num">終値</th><th class="num">ファンダ</th><th class="num">買い時</th><th class="num">利回り</th><th class="num">ROE</th><th>操作</th></tr></thead>
    <tbody id="wl-tbody"><tr><td colspan="10">読み込み中...</td></tr></tbody>
  </table></div>
</div>
<script>
(async function() {
  const LS_WL = "pp_watchlist_jp_long";
  const data = await (await fetch("ranking.json")).json();
  const byCode = Object.fromEntries(data.items.map(x => [x.code, x]));
  function render() {
    const codes = JSON.parse(localStorage.getItem(LS_WL) || "[]");
    const tb = document.getElementById("wl-tbody");
    if (!codes.length) { tb.innerHTML = '<tr><td colspan="10" style="color:var(--muted);">ウォッチリストは空です。ランキングの「☆」にチェックを入れて登録してください。</td></tr>'; return; }
    tb.innerHTML = codes.map(c => {
      const it = byCode[c];
      if (!it) return `<tr><td>${c}</td><td colspan="8">対象外</td><td><button class="btn rm" data-c="${c}">削除</button></td></tr>`;
      return `<tr>
        <td><a href="reports/${it.code}.html"><strong>${it.code}</strong></a></td>
        <td>${it.name}</td><td>${it.sector33}</td><td>${it.tier ? it.tier + "軍" : "―"}</td>
        <td class="num">¥${it.close ? Math.round(it.close).toLocaleString() : "-"}</td>
        <td class="num"><strong>${it.funda_score ?? "-"}</strong></td>
        <td class="num">${it.buy_score ?? "-"}</td>
        <td class="num">${it.dividend_yield ?? "-"}%</td>
        <td class="num">${it.roe ?? "-"}%</td>
        <td><button class="btn rm" data-c="${c}">削除</button></td>
      </tr>`;
    }).join("");
    tb.querySelectorAll(".rm").forEach(b => b.addEventListener("click", () => {
      localStorage.setItem(LS_WL, JSON.stringify(codes.filter(x => x !== b.dataset.c))); render();
    }));
  }
  document.getElementById("clear-wl").addEventListener("click", () => { if (confirm("空にしますか？")) { localStorage.setItem(LS_WL, "[]"); render(); } });
  render();
})();
</script>"""
    (dist_dir / "watchlist.html").write_text(_shell("ウォッチリスト", "☆ ウォッチリスト", wl_body), encoding="utf-8")

    pf_body = """
<div class="kpi-grid">
  <div class="kpi"><div class="label">ポートフォリオ評価額</div><div class="val" id="pf-val">¥0</div></div>
  <div class="kpi"><div class="label">年間予想配当金（税引前）</div><div class="val" id="pf-div">¥0</div></div>
  <div class="kpi"><div class="label">加重平均 利回り</div><div class="val" id="pf-yld">0.00%</div></div>
  <div class="kpi"><div class="label">登録銘柄数</div><div class="val" id="pf-cnt">0</div></div>
</div>
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
    <h2 style="margin:0;">💼 保有銘柄（円建てシミュレーション）</h2>
    <button class="btn" id="clear-pf">すべて解除</button>
  </div>
  <div style="overflow-x:auto;"><table>
    <thead><tr><th>コード</th><th>銘柄</th><th>業種</th><th class="num">終値</th><th class="num">保有株数</th><th class="num">評価額</th><th class="num">利回り</th><th class="num">年間予想配当</th><th>操作</th></tr></thead>
    <tbody id="pf-tbody"><tr><td colspan="9">読み込み中...</td></tr></tbody>
  </table></div>
</div>
<script>
(async function() {
  const LS_PF = "pp_portfolio_jp_long";
  const data = await (await fetch("ranking.json")).json();
  const byCode = Object.fromEntries(data.items.map(x => [x.code, x]));
  function render() {
    const pf = JSON.parse(localStorage.getItem(LS_PF) || "{}");
    const codes = Object.keys(pf);
    const tb = document.getElementById("pf-tbody");
    let tVal = 0, tDiv = 0;
    if (!codes.length) {
      tb.innerHTML = '<tr><td colspan="9" style="color:var(--muted);">ポートフォリオは空です。ランキングの「💼」にチェックを入れて登録してください。</td></tr>';
    } else {
      tb.innerHTML = codes.map(c => {
        const it = byCode[c], sh = Number(pf[c]?.shares || 0);
        if (!it) return `<tr><td>${c}</td><td colspan="7">対象外</td><td><button class="btn rm" data-c="${c}">削除</button></td></tr>`;
        const val = (it.close || 0) * sh;
        const annDiv = (it.dividend_rate || ((it.close || 0) * (it.dividend_yield || 0) / 100)) * sh;
        tVal += val; tDiv += annDiv;
        return `<tr>
          <td><a href="reports/${it.code}.html"><strong>${it.code}</strong></a></td>
          <td>${it.name}</td><td>${it.sector33}</td>
          <td class="num">¥${it.close ? Math.round(it.close).toLocaleString() : "-"}</td>
          <td class="num"><input type="number" class="sh-inp" data-c="${c}" value="${sh}" min="0" step="100" style="width:82px;padding:3px 6px;text-align:right;"></td>
          <td class="num">¥${Math.round(val).toLocaleString()}</td>
          <td class="num">${it.dividend_yield?.toFixed(2) ?? "-"}%</td>
          <td class="num"><strong>¥${Math.round(annDiv).toLocaleString()}</strong></td>
          <td><button class="btn rm" data-c="${c}">削除</button></td>
        </tr>`;
      }).join("");
    }
    document.getElementById("pf-val").textContent = "¥" + Math.round(tVal).toLocaleString();
    document.getElementById("pf-div").textContent = "¥" + Math.round(tDiv).toLocaleString();
    document.getElementById("pf-yld").textContent = (tVal > 0 ? (tDiv / tVal * 100).toFixed(2) : "0.00") + "%";
    document.getElementById("pf-cnt").textContent = codes.length;
    tb.querySelectorAll(".sh-inp").forEach(inp => inp.addEventListener("change", () => {
      pf[inp.dataset.c] = { shares: Math.max(0, Number(inp.value || 0)) };
      localStorage.setItem(LS_PF, JSON.stringify(pf)); render();
    }));
    tb.querySelectorAll(".rm").forEach(b => b.addEventListener("click", () => {
      delete pf[b.dataset.c]; localStorage.setItem(LS_PF, JSON.stringify(pf)); render();
    }));
  }
  document.getElementById("clear-pf").addEventListener("click", () => { if (confirm("空にしますか？")) { localStorage.setItem(LS_PF, "{}"); render(); } });
  render();
})();
</script>"""
    (dist_dir / "portfolio.html").write_text(_shell("ポートフォリオ", "💼 ポートフォリオ", pf_body), encoding="utf-8")

    guide_body = """
<div class="card">
  <h2>このサイトのコンセプト</h2>
  <p>配当利回りを採点に一切含めず、「10年保有できる良い会社か（<strong>ファンダ点</strong>）」と「今割安か（<strong>買い時スコア</strong>）」の2軸（各 0〜110点）で評価します。</p>
</div>
<div class="card">
  <h2>対象銘柄と12業種グループ</h2>
  <ul>
    <li><strong>対象銘柄</strong>: JPX 東証上場銘柄一覧の TOPIX 500 相当（Core30 + Large70 + Mid400、J-REIT・ETF除外）。</li>
    <li><strong>採点モデル</strong>: 一般企業は「業績×0.28＋財務（自己資本比率・D/E・ネットD/E・有利子負債÷営業CF）×0.27＋CF×0.15」。銀行・保険・証券は専用の金融品質スコア＋PER/PBR買い時。その他金融業はリース・信販品質スコアを使用。</li>
    <li><strong>軍分け</strong>: 12業種グループ内でファンダ点順に 上位25%＝1軍 / 続く45%＝2軍 / 残り30%＝3軍。カバレッジ低は最高2軍まで、85点以上は最低2軍保証。</li>
  </ul>
</div>"""
    (dist_dir / "guide.html").write_text(_shell("使い方・見方", "📖 使い方・見方", guide_body), encoding="utf-8")

    terms_body = """
<div class="card">
  <h2>利用規約・免責事項</h2>
  <p>本サイトは個人の投資研究を目的として自動生成されたものであり、特定銘柄の売買を推奨するものではありません。公開データをもとに機械的に算出しているため正確性を保証せず、投資判断は必ずご自身の責任で行ってください。</p>
</div>"""
    (dist_dir / "terms.html").write_text(_shell("利用規約・免責事項", "📜 利用規約・免責事項", terms_body), encoding="utf-8")
