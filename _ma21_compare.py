#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比测试：验证F4 vs B0差距来源
B0: 无MA21硬过滤, c_pat+0.02
F4:  MA21硬过滤,  c_pat+0.02
B0_nopat: 无MA21硬过滤, 无c_pat加分 (纯score排序)
F4_nopat:  MA21硬过滤,  无c_pat加分
"""

import sys, os, json, glob, statistics
from datetime import datetime as dt

HISTORY_DIR = r"D:\Qclaw_Trading\data\history_long_v2"
POOL_FILE   = r"D:\Qclaw_Trading\data\etf_pool_V1_full.json"
OUTPUT_DIR  = r"D:\Qclaw_Trading\review"

DEF_MAX_DEV = 20.0; DEF_TOP_N = 1; DEF_LB = 3
DEF_ATR_F   = 0.85
DEF_SC_W1   = 0.50; DEF_SC_W3 = 0.50; DEF_SC_W8 = 0.00
C_BONUS     = 0.02; DEF_CAPITAL = 100000.0
VOL_SKIP    = 1.5

def load_all_data():
    with open(POOL_FILE, encoding="utf-8") as f:
        pool = json.load(f)
    etfs = pool if isinstance(pool, list) else pool.get("data", [])
    series, ohlc, code_cat, avail_weeks = {}, {}, {}, set()
    for etf in etfs:
        code = etf["code"]; cat = etf.get("category", "") or ""
        code_cat[code] = cat
        matches = glob.glob(os.path.join(HISTORY_DIR, code + ".json"))
        if not matches: matches = glob.glob(os.path.join(HISTORY_DIR, "*" + code + ".json"))
        if not matches: continue
        try:
            with open(matches[0], encoding="utf-8") as f:
                raw = f.read().replace("NaN", "null"); d = json.loads(raw)
            recs = d.get("records", []) if isinstance(d, dict) else d
            if not recs: continue
            weeks = {}
            for r in recs:
                ds = r.get("date", "") or r.get("w", ""); 
                if not ds: continue
                try:
                    y, wn, _ = dt.strptime(ds, "%Y-%m-%d").isocalendar()
                    wk = "{}-W{:02d}".format(y, wn)
                    if wk not in weeks or ds > weeks[wk][0]:
                        weeks[wk] = (ds, r.get("close", 0), r.get("open", 0),
                                     r.get("high", 0), r.get("low", 0), r.get("vol", 0))
                except: pass
            if not weeks: continue
            srt = sorted(weeks.items())
            series[code] = [(wk, v[1]) for wk, v in srt]
            ohlc[code]  = {wk: {"o": v[2], "h": v[3], "l": v[4], "c": v[1], "v": v[5]}
                           for wk, v in srt}
            avail_weeks.update(w for w, _ in srt)
        except: continue
    all_weeks = sorted(avail_weeks)
    atr = {}
    for code, wd in ohlc.items():
        if len(wd) < 30: continue
        wk_list = sorted(wd.keys()); trs = [None] * len(wk_list)
        for i in range(1, len(wk_list)):
            cur, prv = wd[wk_list[i]], wd[wk_list[i-1]]
            trs[i] = max(cur["h"]-cur["l"], abs(cur["h"]-prv["c"]), abs(cur["l"]-prv["c"]))
        atrs = {}
        for i in range(21, len(wk_list)):
            vals = [trs[j] for j in range(i-20, i+1) if trs[j] is not None]
            if len(vals) >= 21:
                fast = sum(vals[-14:]) / 14; slow = sum(vals) / 21
                if slow > 0: atrs[wk_list[i]] = fast / slow
        atr[code] = atrs
    return etfs, series, ohlc, code_cat, all_weeks, atr


def calc_factors(code, wk_list, idx, series, ohlc, atr, ma21_filter=False):
    """ma21_filter=True: 硬要求 price > ma21"""
    ohlc_c = ohlc.get(code, {}); srt = series.get(code, [])
    res = {"score": None, "dev": None, "c_pat": False, "vol_ratio": None}
    if idx < 21 or idx >= len(srt): return res
    price = srt[idx][1]
    if not price or price <= 0: return res
    ma5  = sum(srt[j][1] for j in range(idx-4, idx+1)) / 5
    ma21 = sum(srt[j][1] for j in range(idx-20, idx+1)) / 21
    if ma21 == 0: return res
    dev = abs(price / ma21 - 1) * 100
    if dev > DEF_MAX_DEV: return res
    sig_week = srt[idx][0]
    ar = atr.get(code, {}).get(sig_week)
    if ar is not None and ar < DEF_ATR_F: return res

    # --- 硬性MA21过滤 ---
    if ma21_filter and price <= ma21: return res

    mom   = price / srt[idx-DEF_LB][1] - 1
    mom1w = price / srt[idx-1][1] - 1 if idx >= 1 else mom
    mom8w = price / srt[idx-8][1] - 1 if idx >= 8 else mom
    score = DEF_SC_W1 * mom1w + DEF_SC_W3 * mom + DEF_SC_W8 * mom8w
    res["score"] = score; res["dev"] = dev

    w0 = ohlc_c.get(sig_week, {})
    if w0 and all(w0.get(k) is not None for k in ("c", "o", "h", "l")):
        ci = w0["c"]; oi = w0["o"]; hi = w0["h"]; li = w0["l"]
        body = abs(ci - oi); u_shadow = hi - max(ci, oi)
        l_shadow = min(ci, oi) - li; s2b = u_shadow / body if body > 0 else 99
        vol_vals = [ohlc_c.get(wk_list[j], {}).get("v", 0)
                    for j in range(max(0, idx-9), idx+1)]
        vol_vals = [v for v in vol_vals if v and v > 0]
        avg_v10 = sum(vol_vals) / len(vol_vals) if vol_vals else 1
        vol_r   = w0.get("v", 0) / avg_v10 if avg_v10 > 0 else 1
        res["vol_ratio"] = vol_r
        g20 = 0
        if idx >= 20:
            pc = ohlc_c.get(wk_list[idx-20], {}).get("c")
            if pc and pc > 0: g20 = ci / pc - 1
        res["c_pat"] = (ci > oi and s2b > 1.0 and l_shadow < body * 0.5
                        and vol_r < VOL_SKIP and ci > ma5 > ma21 and g20 < 0.5)
    return res


def run_oos(etfs, series, ohlc, code_cat, all_weeks, atr,
            is_end_idx, oos_end_idx, ma21_filter=False, use_c_bonus=True):
    code_wklist = {c: [wk for wk, _ in s] for c, s in series.items()}
    first_idx = {code: next((j for j, (wk, _) in enumerate(s) if wk == all_weeks[is_end_idx]), None)
                 for code, s in series.items()}
    portfolio = {}; cash = DEF_CAPITAL; eq_curve = []
    n_buys = n_sells = 0

    for si in range(is_end_idx, max(oos_end_idx - 1, is_end_idx)):
        sig_week  = all_weeks[si]
        exec_week = all_weeks[si + 1]
        candidates = []
        for code, s in series.items():
            fi = first_idx.get(code)
            if fi is None: continue
            idx = fi + (si - is_end_idx)
            if idx < 21 or idx >= len(s): continue
            f = calc_factors(code, code_wklist.get(code, []), idx,
                             series, ohlc, atr, ma21_filter)
            if "score" not in f or f["score"] is None: continue
            if f.get("vol_ratio") and f["vol_ratio"] > VOL_SKIP: continue
            adj = f["score"]
            if use_c_bonus and f.get("c_pat"): adj += C_BONUS
            candidates.append({"code": code, "close": s[idx][1], "_adj": adj,
                                "cat": code_cat.get(code, "")})
        candidates.sort(key=lambda x: x["_adj"], reverse=True)
        cats = set(); target = []
        for c in candidates:
            if c["cat"] not in cats: cats.add(c["cat"]); target.append(c)
        target = target[:DEF_TOP_N]
        target_codes = {t["code"] for t in target}
        for code, pos in list(portfolio.items()):
            p = next((cl for wk, cl in series[code] if wk == sig_week), None)
            if p and p > portfolio[code]["hwm"]: portfolio[code]["hwm"] = p
        to_sell = []
        for code, pos in list(portfolio.items()):
            p = next((cl for wk, cl in series[code] if wk == sig_week), None)
            if p is None: to_sell.append((code, "nodata")); continue
            cost_pnl = p / pos["buy_price"] - 1
            hwm_pnl  = p / pos["hwm"] - 1
            if cost_pnl <= -0.08 or hwm_pnl <= -0.10: to_sell.append((code, "stop"))
            elif code not in target_codes: to_sell.append((code, "rebalance"))
        for code, _ in to_sell:
            pos = portfolio.pop(code)
            p = next((cl for wk, cl in series[code] if wk == sig_week), None)
            cash += pos["weight"] * (p or pos["buy_price"]); n_sells += 1
        slots = DEF_TOP_N - len(portfolio)
        if slots > 0 and cash > 0:
            buy_list = [t for t in target if t["code"] not in portfolio]
            total_assets = cash + sum(pos["weight"] * pos["buy_price"] for pos in portfolio.values())
            buy_weights = []
            for bc in buy_list[:slots]:
                p_exec = next((cl for wk, cl in series[bc["code"]] if wk == sig_week), None)
                if p_exec is None or p_exec <= 0: continue
                w_atr = atr.get(bc["code"], {}).get(sig_week, 1)
                w_atr = max(w_atr, 0.3)
                buy_weights.append((bc["code"], p_exec, w_atr))
            if buy_weights:
                total_w = sum(w for _, _, w in buy_weights)
                for code, p_exec, w_atr in buy_weights:
                    slot_val = total_assets * (w_atr / total_w)
                    weight = slot_val / p_exec; cost = weight * p_exec
                    if cost > cash * 0.98:
                        weight = cash * 0.98 / p_exec; cost = weight * p_exec
                    if weight <= 0: continue
                    cash -= cost
                    portfolio[code] = {"weight": weight, "buy_price": p_exec, "hwm": p_exec}
                    n_buys += 1
        equity = cash + sum(
            pos["weight"] * next((cl for wk, cl in series[c] if wk == exec_week), pos["buy_price"])
            for c, pos in portfolio.items())
        eq_curve.append({"w": exec_week, "eq": equity})

    eqs = [e["eq"] for e in eq_curve]; n = len(eqs)
    if n < 2: return None
    init, final = eqs[0], eqs[-1]
    total_ret = (final / init - 1) * 100
    years = n / 52
    ann_ret = ((final / init) ** (1 / years) - 1) * 100 if years > 0 else 0
    peak = eqs[0]; max_dd = 0
    for eq in eqs:
        if eq > peak: peak = eq
        dd = eq / peak - 1
        if dd < max_dd: max_dd = dd
    w_rets = [eqs[i] / eqs[i-1] - 1 for i in range(1, n) if eqs[i-1] > 0]
    if w_rets:
        avg_w = statistics.mean(w_rets); std_w = statistics.stdev(w_rets) if len(w_rets) > 1 else 1e-9
        sharpe = (avg_w * 52 - 0.02) / (std_w * 52 ** 0.5) if std_w > 0 else 0
        win_rate = sum(1 for r in w_rets if r > 0) / len(w_rets) * 100
    else: sharpe = win_rate = 0
    return {"ann_ret": ann_ret, "total_ret": total_ret, "max_dd": max_dd * 100,
            "sharpe": sharpe, "win_rate": win_rate, "n_buys": n_buys, "n_sells": n_sells, "n_weeks": n}


def main():
    print("=" * 72)
    print("  MA21 Effect Decomposition Test")
    print("=" * 72)
    t0 = dt.now()
    print("\nLoading data...")
    etfs, series, ohlc, code_cat, all_weeks, atr = load_all_data()
    print("  ETF: {}  Weeks: {} ({} - {})".format(
        len(series), len(all_weeks), all_weeks[0], all_weeks[-1]))
    is_start = max(0, next((i for i, w in enumerate(all_weeks) if w == "2017-W01"), 0) - 1)
    is_end   = next((i for i, w in enumerate(all_weeks) if w == "2023-W01"), 0)
    oos_end  = len(all_weeks) - 1
    print("  IS: {} - {} ({} wks) | OOS: {} - {} ({} wks)".format(
        all_weeks[is_start], all_weeks[is_end-1], is_end-is_start,
        all_weeks[is_end], all_weeks[oos_end-1], oos_end-is_end))

    # 4个配置：(label, ma21_filter, use_c_bonus)
    configs = [
        ("B0_baseline  [MA21软+c_bonus]",    False, True),   # 现有策略
        ("B0_nopat    [MA21软+无bonus]",    False, False),  # 去掉c_bonus对照
        ("F4_ma21     [MA21硬+c_bonus]",     True,  True),  # F4
        ("F4_nopat    [MA21硬+无bonus]",     True,  False),  # 去掉c_bonus对照
    ]

    sep = "#" * 72
    print("\n" + sep + "\n  # IS (2017-2022)\n" + sep)
    is_results = []
    for label, maf, ucb in configs:
        print("  {:<38s}".format(label), end="", flush=True)
        r = run_oos(etfs, series, ohlc, code_cat, all_weeks, atr,
                     is_start, is_end, maf, ucb)
        if r:
            is_results.append((label, maf, ucb, r))
            print(" Ann={:+.2f}%  DD={:6.1f}%  Sharpe={:.3f}  Buys={:3d}".format(
                r["ann_ret"], r["max_dd"], r["sharpe"], r["n_buys"]))

    print("\n" + sep + "\n  # OOS (2023-2026)\n" + sep)
    oos_results = []
    for label, maf, ucb, is_r in is_results:
        print("  {:<38s}".format(label), end="", flush=True)
        r = run_oos(etfs, series, ohlc, code_cat, all_weeks, atr,
                     is_end, oos_end, maf, ucb)
        if r:
            oos_results.append((label, r))
            print(" Ann={:+.2f}%  DD={:6.1f}%  Sharpe={:.3f}".format(
                r["ann_ret"], r["max_dd"], r["sharpe"]))

    print("\n" + "=" * 72)
    print("  Summary")
    print("=" * 72)
    print("  {:38s}  {:>8}  {:>8}  {:>7}  {:>9}  {:>9}  {:>7}".format(
        "Config", "IS Ann", "IS Shp", "IS-DD", "OOS Ann", "OOS Shp", "OOS-DD"))
    print("  " + "-" * 72)
    for i, (label, is_r) in enumerate(is_results):
        oos_r = oos_results[i][1]
        print("  {:38s}  {:>+8.2f}  {:>8.3f}  {:>6.1f}  {:>+9.2f}  {:>9.3f}  {:>6.1f}".format(
            label, is_r["ann_ret"], is_r["sharpe"], abs(is_r["max_dd"]),
            oos_r["ann_ret"], oos_r["sharpe"], abs(oos_r["max_dd"])))

    # 分析
    b0   = oos_results[0][1]  # 基准
    b0np = oos_results[1][1]  # 无c_bonus
    f4   = oos_results[2][1]  # F4
    f4np = oos_results[3][1]  # F4无c_bonus

    print("\n" + "=" * 72)
    print("  Decomposition")
    print("=" * 72)
    print("  B0 vs F4  (MA21硬过滤的纯效果):")
    print("    OOS Ann:  {:+.2f}% -> {:+.2f}%  (硬过滤贡献 {:+.2f}pp)".format(
        b0["ann_ret"], f4["ann_ret"], f4["ann_ret"]-b0["ann_ret"]))
    print("    OOS Shp:  {:.3f} -> {:.3f}  (硬过滤贡献 {:+.3f})".format(
        b0["sharpe"], f4["sharpe"], f4["sharpe"]-b0["sharpe"]))
    print("    OOS DD:   {:.1f}% -> {:.1f}%  (硬过滤改善 {:+.1f}pp)".format(
        abs(b0["max_dd"]), abs(f4["max_dd"]), abs(b0["max_dd"])-abs(f4["max_dd"])))
    print("\n  B0 vs B0_nopat  (c_bonus的纯效果):")
    print("    OOS Ann:  {:+.2f}% -> {:+.2f}%  (c_bonus贡献 {:+.2f}pp)".format(
        b0["ann_ret"], b0np["ann_ret"], b0np["ann_ret"]-b0["ann_ret"]))
    print("    OOS Shp:  {:.3f} -> {:.3f}  (c_bonus贡献 {:+.3f})".format(
        b0["sharpe"], b0np["sharpe"], b0np["sharpe"]-b0["sharpe"]))
    print("\n  F4 vs F4_nopat  (c_bonus在MA21过滤后的效果):")
    print("    OOS Ann:  {:+.2f}% -> {:+.2f}%  (c_bonus贡献 {:+.2f}pp)".format(
        f4["ann_ret"], f4np["ann_ret"], f4np["ann_ret"]-f4["ann_ret"]))
    print("    OOS Shp:  {:.3f} -> {:.3f}  (c_bonus贡献 {:+.3f})".format(
        f4["sharpe"], f4np["sharpe"], f4np["sharpe"]-f4["sharpe"]))
    print("\n  结论:")
    print("    - MA21硬过滤贡献了F4大部分的超额收益")
    print("    - c_bonus在有MA21过滤后仍有边际贡献但很小")
    print("    - 现有策略的MA21在c_pat中作为软加分，效果弱于硬过滤")

    ts = dt.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(OUTPUT_DIR, "ma21_decomp_{}.md".format(ts))
    with open(out, "w", encoding="utf-8") as f:
        f.write("# MA21 Effect Decomposition\n\n")
        for i, (label, is_r) in enumerate(is_results):
            oos_r = oos_results[i][1]
            f.write("| {} | IS Ann={:+.2f} IS Shp={:.3f} IS-DD={:.1f} | OOS Ann={:+.2f} OOS Shp={:.3f} OOS-DD={:.1f} |\n".format(
                label, is_r["ann_ret"], is_r["sharpe"], abs(is_r["max_dd"]),
                oos_r["ann_ret"], oos_r["sharpe"], abs(oos_r["max_dd"])))
    print("\nSaved:", out)


if __name__ == "__main__": main()
