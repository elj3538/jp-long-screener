"""日本株10年保有スクリーナーのファンダ点（品質スコア）・買い時スコア・軍分け・業種級を算出するモジュール。"""

from __future__ import annotations

import math
from statistics import median
from typing import Any


def _piecewise(val: float | None, points: list[tuple[float, float]]) -> float | None:
    if val is None or math.isnan(val) or math.isinf(val):
        return None
    if val <= points[0][0]:
        return points[0][1]
    if val >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= val <= x1:
            if x1 == x0:
                return y1
            return y0 + (val - x0) / (x1 - x0) * (y1 - y0)
    return None


def _avg(values: list[float | None]) -> float | None:
    valid = [v for v in values if v is not None]
    return sum(valid) / len(valid) if valid else None


def _weighted_avg(pairs: list[tuple[float | None, float]]) -> float | None:
    num, den = 0.0, 0.0
    for val, w in pairs:
        if val is not None:
            num += val * w
            den += w
    return num / den if den > 0 else None


def _calc_cagr(series: list[dict[str, Any]]) -> float | None:
    if len(series) < 2:
        return None
    latest, oldest = series[0]["value"], series[-1]["value"]
    years = len(series) - 1
    if oldest is None or latest is None or oldest <= 0 or latest <= 0:
        if oldest and oldest != 0 and latest is not None:
            pct = (latest - oldest) / abs(oldest) * 100.0 / years
            return max(-50.0, min(50.0, pct))
        return None
    cagr = ((latest / oldest) ** (1.0 / years) - 1.0) * 100.0
    return round(max(-80.0, min(150.0, cagr)), 2)


def classify_model(stock: dict[str, Any]) -> str:
    """業種グループから採点モデル（general / financial / lease）を判定する。"""
    grp = stock.get("sector_group", "")
    if grp == "銀行・保険・証券":
        return "financial"
    if grp == "リース・信販・その他金融":
        return "lease"
    return "general"


def _compute_raw_metrics(stock: dict[str, Any]) -> dict[str, Any]:
    fin = stock.get("financials", {})
    q = stock.get("quarterly", {})
    bs = stock.get("balance_sheet", {})
    cf = stock.get("cashflow", {})
    val = stock.get("valuation", {})
    price_info = stock.get("price", {})

    model = classify_model(stock)
    mkt_cap = price_info.get("market_cap")
    ev = price_info.get("enterprise_value")
    cur_price = price_info.get("current")

    rev_s = fin.get("revenue", [])
    op_s = fin.get("operating_income", [])
    ebit_s = fin.get("ebit", []) or op_s
    pretax_s = fin.get("pretax_income", [])
    ni_s = fin.get("net_income", [])
    eps_s = fin.get("eps", [])
    int_s = fin.get("interest_expense", [])

    debt_s = bs.get("total_debt", [])
    cash_s = bs.get("cash", [])
    eq_s = bs.get("equity", [])
    assets_s = bs.get("total_assets", [])

    ocf_s = cf.get("operating_cf", [])
    capex_s = cf.get("capex", [])
    fcf_s = cf.get("free_cf", [])
    div_paid_s = cf.get("dividends_paid", [])

    # --- 業績 ---
    rev_cagr = _calc_cagr(rev_s)
    eps_cagr = _calc_cagr(eps_s) or _calc_cagr(ni_s)
    op_margin = round(op_s[0]["value"] / rev_s[0]["value"] * 100.0, 2) if (rev_s and op_s and rev_s[0]["value"] and rev_s[0]["value"] > 0) else None

    profit_series = [x["value"] for x in (op_s or ni_s) if x.get("value") is not None]
    profit_stability = None
    if len(profit_series) >= 2:
        pos_ratio = sum(1 for v in profit_series if v > 0) / len(profit_series)
        mean_abs = sum(abs(v) for v in profit_series) / len(profit_series)
        if mean_abs > 0:
            diffs = [abs(profit_series[i] - profit_series[i + 1]) / mean_abs for i in range(len(profit_series) - 1)]
            vol = sum(diffs) / len(diffs)
            profit_stability = round(max(0.0, min(1.0, pos_ratio * 0.8 + max(0.0, 0.2 - vol * 0.35))), 2)

    # 直近四半期 急減速チェック
    q_rev = q.get("revenue", [])
    q_op = q.get("operating_income", [])
    q_ni = q.get("net_income", [])
    q_rev_yoy = round((q_rev[0]["value"] / q_rev[4]["value"] - 1.0) * 100.0, 2) if (len(q_rev) >= 5 and q_rev[4]["value"] and q_rev[4]["value"] > 0) else None
    pq = q_op if len(q_op) >= 5 else q_ni
    q_profit_yoy = round((pq[0]["value"] - pq[4]["value"]) / abs(pq[4]["value"]) * 100.0, 2) if (len(pq) >= 5 and pq[4]["value"] and abs(pq[4]["value"]) > 0) else None
    rapid_decel = bool(q_rev_yoy is not None and q_profit_yoy is not None and q_rev_yoy < -5.0 and q_profit_yoy < -15.0)

    # --- 財務（日本株専用：自己資本比率を採点） ---
    debt_v = debt_s[0]["value"] if debt_s else None
    cash_v = cash_s[0]["value"] if cash_s else 0.0
    eq_v = eq_s[0]["value"] if eq_s else None
    assets_v = assets_s[0]["value"] if assets_s else None
    ocf_v = ocf_s[0]["value"] if ocf_s else None
    capex_v = capex_s[0]["value"] if capex_s else None
    fcf_v = fcf_s[0]["value"] if fcf_s else (ocf_v - abs(capex_v) if (ocf_v is not None and capex_v is not None) else None)

    equity_ratio = round(eq_v / assets_v * 100.0, 1) if (eq_v is not None and assets_v and assets_v > 0) else None
    de_ratio = round(debt_v / eq_v, 2) if (debt_v is not None and eq_v and eq_v > 0) else None
    net_de = round((debt_v - (cash_v or 0.0)) / eq_v, 2) if (debt_v is not None and eq_v and eq_v > 0) else None
    debt_to_ocf = round(debt_v / ocf_v, 2) if (debt_v is not None and ocf_v and ocf_v > 0) else None

    # --- CF ---
    ocf_positive = bool(ocf_v is not None and ocf_v > 0)
    fcf_positive = bool(fcf_v is not None and fcf_v > 0)
    div_paid_v = abs(div_paid_s[0]["value"]) if (div_paid_s and div_paid_s[0]["value"]) else None
    fcf_payout = None
    if div_paid_v is not None and fcf_v is not None:
        fcf_payout = round(div_paid_v / fcf_v * 100.0, 1) if fcf_v > 0 else 150.0

    # --- ROE / ROA（一般企業は採点外表示、金融・リースでは専用採点に使用） ---
    ni_v = ni_s[0]["value"] if ni_s else None
    roe = round(ni_v / eq_v * 100.0, 1) if (ni_v is not None and eq_v and eq_v > 0) else (round(val["roe_info"] * 100.0, 1) if val.get("roe_info") is not None else None)
    roa = round(ni_v / assets_v * 100.0, 1) if (ni_v is not None and assets_v and assets_v > 0) else (round(val["roa_info"] * 100.0, 1) if val.get("roa_info") is not None else None)

    # --- バリュエーション ---
    ebit_v = ebit_s[0]["value"] if ebit_s else None
    ev_ebit = round(ev / ebit_v, 2) if (ev and ebit_v and ebit_v > 0 and 0 < ev / ebit_v < 200) else None
    fcf_yield = round(fcf_v / mkt_cap * 100.0, 2) if (fcf_v is not None and mkt_cap and mkt_cap > 0) else None
    trailing_pe = val.get("trailing_pe")
    if trailing_pe is not None and (trailing_pe <= 0 or trailing_pe > 200):
        trailing_pe = None
    pbr = val.get("price_to_book")
    if pbr is not None and (pbr <= 0 or pbr > 100):
        pbr = None

    # PER過去レンジ位置（%）
    per_range_pos = None
    yearly_prices = price_info.get("yearly_prices", {})
    if trailing_pe is not None and eps_s and yearly_prices:
        hist_pers = []
        for row in eps_s:
            yr, e = row["date"][:4], row["value"]
            p_info = yearly_prices.get(yr)
            if e and e > 0 and p_info and p_info.get("avg", 0) > 0:
                pe_yr = p_info["avg"] / e
                if 2.0 <= pe_yr <= 120.0:
                    hist_pers.append(pe_yr)
        if len(hist_pers) >= 2:
            p_min, p_max = min(hist_pers), max(hist_pers)
            per_range_pos = round(max(0.0, min(100.0, (p_max - trailing_pe) / (p_max - p_min) * 100.0)), 1) if p_max > p_min else 50.0

    # --- グループ別採点（0〜110点） ---
    s_rev = _piecewise(rev_cagr, [(-6, 20), (0, 55), (3, 78), (8, 96), (15, 110)])
    s_eps = _piecewise(eps_cagr, [(-8, 15), (0, 55), (5, 80), (12, 98), (20, 110)])
    s_margin = _piecewise(op_margin, [(0, 15), (4, 52), (10, 82), (18, 98), (28, 110)])
    s_stab = _piecewise(profit_stability, [(0.4, 20), (0.65, 58), (0.88, 90), (1.0, 110)])

    perf_raw = _avg([s_rev, s_eps, s_margin, s_stab])
    if perf_raw is not None and rapid_decel:
        perf_raw *= 0.80
    perf_score = round(perf_raw, 1) if perf_raw is not None else None

    s_eqr = _piecewise(equity_ratio, [(10, 15), (25, 55), (40, 84), (60, 100), (75, 110)])
    s_de = _piecewise(de_ratio, [(0.0, 108), (0.5, 95), (1.0, 80), (2.0, 50), (3.5, 15)])
    s_nde = _piecewise(net_de, [(-0.2, 110), (0.2, 96), (0.5, 82), (1.5, 50), (3.0, 15)])
    s_docf = _piecewise(debt_to_ocf, [(0.5, 108), (2.0, 92), (3.0, 80), (6.0, 48), (10.0, 15)])
    fin_raw = _avg([s_eqr, s_de, s_nde, s_docf])
    fin_score = round(fin_raw, 1) if fin_raw is not None else None

    s_ocf = 98.0 if ocf_positive else (20.0 if ocf_v is not None else None)
    s_fcf = 100.0 if fcf_positive else (18.0 if fcf_v is not None else None)
    s_fcf_pay = _piecewise(fcf_payout, [(20, 108), (50, 95), (70, 80), (100, 50), (130, 15)])
    cf_raw = _avg([s_ocf, s_fcf, s_fcf_pay])
    cf_score = round(cf_raw, 1) if cf_raw is not None else None

    # --- ファンダ点（品質スコア）統合 ---
    if model == "financial":
        s_roe_f = _piecewise(roe, [(0, 15), (5, 55), (8, 82), (12, 98), (18, 110)])
        f_parts = [s_roe_f, s_rev, s_eps, s_stab]
        valid_f = [x for x in f_parts if x is not None]
        funda_raw = sum(valid_f) / len(valid_f) if valid_f else None
        if funda_raw is not None and rapid_decel:
            funda_raw *= 0.85
        perf_score, fin_score, cf_score = None, None, None
        coverage = "高" if len(valid_f) == 4 else ("中" if len(valid_f) == 3 else "低")
    elif model == "lease":
        assets_cagr = _calc_cagr(assets_s)
        s_roa_l = _piecewise(roa, [(0.2, 30), (1.0, 75), (2.5, 95), (5.0, 110)])
        s_ag = _piecewise(assets_cagr, [(-5, 25), (0, 60), (5, 88), (12, 108)])
        pretax_v = pretax_s[0]["value"] if pretax_s else None
        int_v = abs(int_s[0]["value"]) if (int_s and int_s[0]["value"]) else None
        icov_l = (pretax_v + int_v) / int_v if (pretax_v is not None and int_v and int_v > 0) else None
        s_icov_l = _piecewise(icov_l, [(1.2, 25), (2.5, 65), (5.0, 92), (10.0, 110)])
        lease_cf = _avg([s_roa_l, s_ag, s_icov_l])
        cf_score = round(lease_cf, 1) if lease_cf is not None else None
        funda_raw = _weighted_avg([(perf_score, 0.28), (fin_score, 0.27), (cf_score, 0.15)])
        grp_ok = sum(1 for x in (perf_score, fin_score, cf_score) if x is not None)
        coverage = "高" if grp_ok == 3 else ("中" if grp_ok == 2 else "低")
    else:
        funda_raw = _weighted_avg([(perf_score, 0.28), (fin_score, 0.27), (cf_score, 0.15)])
        grp_ok = sum(1 for x in (perf_score, fin_score, cf_score) if x is not None)
        coverage = "高" if grp_ok == 3 else ("中" if grp_ok == 2 else "低")

    funda_score = round(min(110.0, max(0.0, funda_raw)), 1) if funda_raw is not None else None

    return {
        "code": stock["code"],
        "yf_symbol": stock["yf_symbol"],
        "name": stock["name"],
        "sector33": stock["sector33"],
        "sector_group": stock["sector_group"],
        "scale": stock.get("scale", ""),
        "model": model,
        "close": round(cur_price, 1) if cur_price is not None else None,
        "latest_date": price_info.get("latest_date"),
        "market_cap_oku": round(mkt_cap / 1e8, 0) if mkt_cap else None,
        "returns": price_info.get("returns", {}),
        "funda_score": funda_score,
        "perf_score": perf_score,
        "fin_score": fin_score,
        "cf_score": cf_score,
        "buy_score": None,
        "coverage": coverage,
        "rapid_decel": rapid_decel,
        "metrics": {
            "rev_cagr": rev_cagr,
            "eps_cagr": eps_cagr,
            "op_margin": op_margin,
            "profit_stability": profit_stability,
            "equity_ratio": equity_ratio,
            "de_ratio": de_ratio,
            "net_de": net_de,
            "debt_to_ocf": debt_to_ocf,
            "ocf_positive": ocf_positive,
            "fcf_positive": fcf_positive,
            "fcf_payout": fcf_payout,
            "ev_ebit": ev_ebit,
            "ev_ebit_rel": None,
            "fcf_yield": fcf_yield,
            "trailing_pe": round(trailing_pe, 1) if trailing_pe is not None else None,
            "per_rel": None,
            "per_range_pos": per_range_pos,
            "pbr": round(pbr, 2) if pbr is not None else None,
            "pbr_rel": None,
            "dividend_yield": val.get("dividend_yield"),
            "dividend_rate": val.get("dividend_rate"),
            "roe": roe,
            "roa": roa,
            "q_rev_yoy": q_rev_yoy,
            "q_profit_yoy": q_profit_yoy,
            "rsi14": price_info.get("rsi14"),
            "macd": price_info.get("macd"),
        },
        "detail": {
            "summary": stock.get("summary", ""),
            "analyst": stock.get("analyst", {}),
            "price_series_weekly": price_info.get("price_series_weekly", []),
        },
    }


def score_all_stocks(stocks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """全銘柄のファンダ点・買い時スコア・業種級・軍分けを算出する。"""
    items = [_compute_raw_metrics(s) for s in stocks]

    by_group: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        by_group.setdefault(it["sector_group"], []).append(it)

    grp_pe_med, grp_pbr_med, grp_ev_med = {}, {}, {}
    for grp, g_items in by_group.items():
        pes = [x["metrics"]["trailing_pe"] for x in g_items if x["metrics"]["trailing_pe"] is not None]
        pbrs = [x["metrics"]["pbr"] for x in g_items if x["metrics"]["pbr"] is not None]
        evs = [x["metrics"]["ev_ebit"] for x in g_items if x["metrics"]["ev_ebit"] is not None]
        if pes:
            grp_pe_med[grp] = median(pes)
        if pbrs:
            grp_pbr_med[grp] = median(pbrs)
        if evs:
            grp_ev_med[grp] = median(evs)

    # 買い時スコア算出
    for it in items:
        m = it["metrics"]
        grp = it["sector_group"]

        ev_rel = round(m["ev_ebit"] / grp_ev_med[grp], 2) if (m["ev_ebit"] is not None and grp in grp_ev_med and grp_ev_med[grp] > 0) else None
        per_rel = round(m["trailing_pe"] / grp_pe_med[grp], 2) if (m["trailing_pe"] is not None and grp in grp_pe_med and grp_pe_med[grp] > 0) else None
        pbr_rel = round(m["pbr"] / grp_pbr_med[grp], 2) if (m["pbr"] is not None and grp in grp_pbr_med and grp_pbr_med[grp] > 0) else None
        m["ev_ebit_rel"], m["per_rel"], m["pbr_rel"] = ev_rel, per_rel, pbr_rel

        s_ev = _piecewise(ev_rel, [(0.55, 110), (0.85, 92), (1.0, 75), (1.2, 52), (1.7, 20)])
        s_fcfy = _piecewise(m["fcf_yield"], [(0.0, 20), (3.0, 58), (6.0, 88), (9.0, 105), (12.0, 110)])
        s_per_rel = _piecewise(per_rel, [(0.6, 110), (0.95, 88), (1.2, 58), (1.6, 20)])
        s_per_pos = _piecewise(m["per_range_pos"], [(0, 20), (20, 48), (60, 85), (90, 106), (100, 110)])
        s_per = _avg([s_per_rel, s_per_pos])
        s_pbr = _piecewise(pbr_rel, [(0.55, 110), (1.0, 86), (1.4, 52), (2.0, 20)])

        if it["model"] == "financial":
            buy_raw = _avg([s_per if s_per is not None else 60.0, s_pbr if s_pbr is not None else 60.0])
        else:
            buy_raw = _avg([
                s_ev if s_ev is not None else 60.0,
                s_fcfy if s_fcfy is not None else 60.0,
                s_per if s_per is not None else 60.0,
                s_pbr if s_pbr is not None else 60.0,
            ])
        it["buy_score"] = round(min(110.0, max(0.0, buy_raw)), 1) if buy_raw is not None else None

    # 12業種グループ別 業種級＆軍分け
    group_stats: dict[str, dict[str, Any]] = {}
    small_test_mode = len(items) < 40
    for grp, g_items in by_group.items():
        g_items.sort(key=lambda x: (x["funda_score"] if x["funda_score"] is not None else -1.0), reverse=True)
        scores = [x["funda_score"] for x in g_items if x["funda_score"] is not None]
        med = round(median(scores), 1) if scores else 0.0
        grade = "A" if med >= 80.0 else ("B" if med >= 70.0 else "C")
        n = len(g_items)
        group_stats[grp] = {"count": n, "median": med, "grade": grade}

        for idx, it in enumerate(g_items):
            it["sector_grade"] = grade
            if not small_test_mode and n < 6:
                it["tier"] = 0
                continue
            r = idx / n
            tier = 1 if r < 0.25 else (2 if r < 0.70 else 3)
            if it["coverage"] == "低" and tier == 1:
                tier = 2
            if (it["funda_score"] or 0.0) >= 85.0 and tier == 3:
                tier = 2
            it["tier"] = tier

    items.sort(key=lambda x: (x["funda_score"] if x["funda_score"] is not None else -1.0), reverse=True)
    return items, group_stats
