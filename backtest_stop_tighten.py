#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test tighter stop-loss thresholds for win rate improvement."""
import sys, os, json, glob, statistics, time
from datetime import datetime as dt

HISTORY_DIR = r"D:\Qclaw_Trading\data\history_long_v2"
POOL_FILE = r"D:\Qclaw_Trading\data\etf_pool_V1_full.json"
OUTPUT_DIR = r"D:\Qclaw_Trading\review"

DEF_MAX_DEV = 15.0; DEF_TOP_N = 3; DEF_LB = 3; DEF_ATR_F = 0.85
DEF_SC_W1 = 0.40; DEF_SC_W3 = 0.40; DEF_SC_W8 = 0.20
C_BONUS = 0.02; DEF_CAPITAL = 100000.0

def load_all_data():
    with open(POOL_FILE, encoding="utf-8") as f:
        pool = json.load(f)
    etfs = pool if isinstance(pool, list) else pool.get("data", [])
    series, ohlc, code_cat, avail_weeks = {}, {}, {}, set()
    for etf in etfs:
        code, cat = etf["code"], etf.get("category", "") or ""
        code_cat[code] = cat
        matches = glob.glob(os.path.join(HISTORY_DIR, code + ".json"))
        if not matches:
            matches = glob.glob(os.path.join(HISTORY_DIR, "*" + code + ".json"))
        if not matches:
            continue
        try:
            with open(matches[0], encoding="utf-8") as f:
                raw = f.read().replace("NaN", "null")
            d = json.loads(raw)
            recs = d.get("records", []) if isinstance(d, dict) else d
            if not recs:
                continue
            weeks = {}
            for r in recs:
                ds = r.get("date", "") or r.get("w", "")
                if not ds:
                    continue
                try:
                    y, wn, _ = dt.strptime(ds, "%Y-%m-%d").isocalendar()
                    wk = "{}-W{:02d}".format(y, wn)
                    if wk not in weeks or ds > weeks[wk][0]:
                        weeks[wk] = (ds, r.get("close", 0), r.get("open", 0),
                                     r.get("high", 0), r.get("low", 0), r.get("vol", 0))
                except:
                    pass
            if not weeks:
                continue
            srt = sorted(weeks.items())
            series[code] = [(wk, v[1]) for wk, v in srt]
            ohlc[code] = {wk: {"o": v[2], "h": v[3], "l": v[4], "c": v[1], "v": v[5]} for wk, v in srt}
            avail_weeks.update(w for w, _ in srt)
        except:
            continue
    all_weeks = sorted(avail_weeks)
    atr = {}
    for code, wd in ohlc.items():
        if len(wd) < 30:
            continue
        wk_list = sorted(wd.keys())
        trs = [None] * len(wk_list)
        for i in range(1, len(wk_list)):
            cur, prv = wd[wk_list[i]], wd[wk_list[i-1]]
            trs[i] = max(cur["h"] - cur["l"], abs(cur["h"] - prv["c"]), abs(cur["l"] - prv["c"]))
        atrs = {}
        for i in range(21, len(wk_list)):
            vals = [trs[j] for j in range(i-20, i+1) if trs[j] is not None]
            if len(vals) >= 21:
                fast = sum(vals[-14:]) / 14; slow = sum(vals) / 21
                if slow > 0:
                    atrs[wk_list[i]] = fast / slow
        atr[code] = atrs
    return etfs, series, ohlc, code_cat, all_weeks, atr

def calc_score(code, idx, srt, ohlc_c, atr_c, sig_week):
    if idx < 21 or idx >= len(srt):
        return None
    price = srt[idx][1]
    if not price or price <= 0:
        return None
    ma5 = sum(srt[j][1] for j in range(idx-4, idx+1)) / 5
    ma21 = sum(srt[j][1] for j in range(idx-20, idx+1)) / 21
    if ma21 == 0:
        return None
    dev = abs(price / ma21 - 1) * 100
    if dev > DEF_MAX_DEV:
        return None
    ar = atr_c.get(sig_week)
    if ar is not None and ar < DEF_ATR_F:
        return None
    mom = price / srt[idx-DEF_LB][1] - 1
    mom1w = price / srt[idx-1][1] - 1 if idx >= 1 else mom
    mom8w = price / srt[idx-8][1] - 1 if idx >= 8 else mom
    score = DEF_SC_W1 * mom1w + DEF_SC_W3 * mom + DEF_SC_W8 * mom8w
    c_pat = False
    w0 = ohlc_c.get(sig_week, {})
    if w0 and all(w0.get(k) is not None for k in ("c", "o", "h", "l")):
        ci, oi, hi, li = w0["c"], w0["o"], w0["h"], w0["l"]
        body = abs(ci - oi); u_shadow = hi - max(ci, oi); l_shadow = min(ci, oi) - li
        s2b = u_shadow / body if body > 0 else 99
        vol_vals = [ohlc_c.get(wk, {}).get("v", 0) for wk in srt[max(0, idx-9):idx+1] if ohlc_c.get(wk, {}).get("v", 0) > 0]
        avg_v10 = sum(vol_vals) / len(vol_vals) if vol_vals else 1
        vol_ratio = w0.get("v", 0) / avg_v10 if avg_v10 > 0 else 1
        g20 = 0
        if idx >= 20:
            pc = ohlc_c.get(srt[idx-20][0], {}).get("c")
            if pc and pc > 0:
                g20 = ci / pc - 1
        c_pat = (ci > oi and s2b > 1.0 and l_shadow < body * 0.5 and vol_ratio < 1.5 and ci > ma5 > ma21 and g20 < 0.5)
    return {"score": score, "c_pat": c_pat, "vol_ratio": (w0.get("v", 0) / avg_v10 if avg_v10 > 0 else 1) if w0 else 1}

def run_backtest(series, ohlc, code_cat, all_weeks, atr,
                 is_start, is_end, oos_end, cost_stop=-0.08, hwm_stop=-0.10):
    first_idx = {}
    for code, s in series.items():
        for j, (wk, _) in enumerate(s):
            if wk == all_weeks[is_start]:
                first_idx[code] = j
                break
    portfolio = {}
    cash = DEF_CAPITAL; eq_curve = []
    n_buys = n_sells = n_stop_sells = 0
    trade_details = []
    for si in range(is_start, oos_end):
        sig_week = all_weeks[si]
        exec_week = all_weeks[si+1] if si+1 < len(all_weeks) else sig_week
        for code in list(portfolio.keys()):
            p = next((cl for wk, cl in series[code] if wk == sig_week), None)
            if p and p > portfolio[code]["hwm"]:
                portfolio[code]["hwm"] = p
        candidates = []
        for code, s in series.items():
            fi = first_idx.get(code)
            if fi is None: continue
            idx = fi + (si - is_start)
            if idx < 21 or idx >= len(s): continue
            f = calc_score(code, idx, s, ohlc.get(code, {}), atr.get(code, {}), sig_week)
            if f is None: continue
            candidates.append({"code": code, "close": s[idx][1],
                               "_adj": f["score"] + (C_BONUS if f["c_pat"] else 0),
                               "cat": code_cat.get(code, "")})
        if not candidates:
            for code in list(portfolio.keys()):
                pos = portfolio.pop(code)
                p = next((cl for wk, cl in series[code] if wk == sig_week), None)
                cash += pos["weight"] * (p or pos["buy_price"])
                n_sells += 1
            eq_curve.append({"w": exec_week, "eq": cash}); continue
        candidates.sort(key=lambda x: x["_adj"], reverse=True)
        cats = set(); target = []
        for c in candidates:
            if c["cat"] not in cats: cats.add(c["cat"]); target.append(c)
        target = target[:DEF_TOP_N]; target_codes = {t["code"] for t in target}
        to_sell = []
        for code, pos in list(portfolio.items()):
            p = next((cl for wk, cl in series[code] if wk == sig_week), None)
            if p is None: to_sell.append((code, "nodata")); continue
            cost_pnl = p / pos["buy_price"] - 1; hwm_pnl = p / pos["hwm"] - 1
            if cost_pnl <= cost_stop or hwm_pnl <= hwm_stop:
                to_sell.append((code, "stop"))
            elif code not in target_codes:
                to_sell.append((code, "rebalance"))
        for code, reason in to_sell:
            pos = portfolio.pop(code)
            p = next((cl for wk, cl in series[code] if wk == sig_week), None)
            sell_price = p or pos["buy_price"]; pnl = sell_price / pos["buy_price"] - 1
            cash += pos["weight"] * sell_price; n_sells += 1
            if reason == "stop": n_stop_sells += 1
            trade_details.append({"code": code, "pnl": pnl, "reason": reason})
        slots = DEF_TOP_N - len(portfolio)
        if slots > 0 and cash > 0:
            buy_list = [t for t in target if t["code"] not in portfolio]
            total_assets = cash + sum(pos["weight"] * pos["buy_price"] for pos in portfolio.values())
            for bc in buy_list[:slots]:
                p_exec = next((cl for wk, cl in series[bc["code"]] if wk == sig_week), None)
                if p_exec is None or p_exec <= 0: continue
                slot_val = total_assets / DEF_TOP_N; weight = slot_val / p_exec
                cost = weight * p_exec
                if cost > cash: weight = cash / p_exec; cost = weight * p_exec
                if weight <= 0: continue
                cash -= cost; portfolio[bc["code"]] = {"weight": weight, "buy_price": p_exec, "hwm": p_exec}; n_buys += 1
        equity = cash + sum(pos["weight"] * next((cl for wk, cl in series[c] if wk == exec_week), pos["buy_price"]) for c, pos in portfolio.items())
        eq_curve.append({"w": exec_week, "eq": equity})
    eqs = [e["eq"] for e in eq_curve]; n = len(eqs)
    if n < 2: return None
    init, final = eqs[0], eqs[-1]; years = n / 52
    ann_ret = ((final / init) ** (1 / years) - 1) * 100 if years > 0 else 0
    peak = eqs[0]; max_dd = 0
    for eq in eqs:
        if eq > peak: peak = eq
        dd = eq / peak - 1
        if dd < max_dd: max_dd = dd
    w_rets = [eqs[i] / eqs[i-1] - 1 for i in range(1, n) if eqs[i-1] > 0]
    win_trades = sum(1 for t in trade_details if t["pnl"] > 0)
    total_trades = len(trade_details)
    trade_win_rate = win_trades / total_trades * 100 if total_trades > 0 else 0
    stop_pnls = [t["pnl"] for t in trade_details if t["reason"] == "stop"]
    avg_loss = statistics.mean([p*100 for p in stop_pnls]) if stop_pnls else 0
    if w_rets:
        avg_w = statistics.mean(w_rets); std_w = statistics.stdev(w_rets) if len(w_rets) > 1 else 1e-9
        sharpe = (avg_w * 52 - 0.02) / (std_w * 52 ** 0.5) if std_w > 0 else 0
        weekly_win = sum(1 for r in w_rets if r > 0) / len(w_rets) * 100
    else: sharpe = weekly_win = 0
    return {"ann_ret": ann_ret, "total_ret": (final/init-1)*100, "max_dd": max_dd*100, "sharpe": sharpe,
            "weekly_win_rate": weekly_win, "trade_win_rate": trade_win_rate,
            "n_buys": n_buys, "n_sells": n_sells, "n_stop_sells": n_stop_sells,
            "total_trades": total_trades, "avg_loss_pct": avg_loss, "n_weeks": n}

def main():
    t0 = time.time()
    print("=" * 80)
    print("  STOP-LOSS TIGHTENING TEST")
    print("=" * 80)
    print("\nLoading data...")
    etfs, series, ohlc, code_cat, all_weeks, atr = load_all_data()
    print("  {} ETFs, {} weeks".format(len(series), len(all_weeks)))
    is_start = max(0, next((i for i, w in enumerate(all_weeks) if w == "2017-W01"), 0) - 1)
    is_end = next((i for i, w in enumerate(all_weeks) if w == "2023-W01"), 0)
    oos_end = len(all_weeks) - 1
    configs = [
        ("Baseline -8%/-10%", -0.08, -0.10),
        ("Tight -6%/-8%", -0.06, -0.08),
        ("Tight -5%/-7%", -0.05, -0.07),
        ("Tight -4%/-6%", -0.04, -0.06),
        ("Tight -3%/-5%", -0.03, -0.05),
    ]
    print("\n" + "#" * 80)
    print("  IS (2017-2022)")
    print("#" * 80)
    is_results = []
    for label, cs, hs in configs:
        print("  {:40s}".format(label), end="", flush=True)
        r = run_backtest(series, ohlc, code_cat, all_weeks, atr, is_start, is_end, is_end, cs, hs)
        if r:
            is_results.append((label, r))
            print("  Ann={:+.2f}%  Sharpe={:.3f}  DD={:6.1f}%  TWR={:.1f}%  Stops={}".format(
                  r["ann_ret"], r["sharpe"], r["max_dd"], r["trade_win_rate"], r["n_stop_sells"]))
    print("\n" + "#" * 80)
    print("  OOS (2023-2026)")
    print("#" * 80)
    oos_results = []
    for label, cs, hs in [(x[0], -0.08, -0.10) for x in is_results]:
        print("  {:40s}".format(label), end="", flush=True)
        # Get actual cs/hs from configs
        cs_hs = {x[0]: (x[1], x[2]) for x in configs}[label]
        r = run_backtest(series, ohlc, code_cat, all_weeks, atr, is_end, is_end, oos_end, cs_hs[0], cs_hs[1])
        if r:
            oos_results.append((label, r))
            print("  Ann={:+.2f}%  Sharpe={:.3f}  DD={:6.1f}%  TWR={:.1f}%  Stops={}".format(
                  r["ann_ret"], r["sharpe"], r["max_dd"], r["trade_win_rate"], r["n_stop_sells"]))
    print("\n" + "=" * 100)
    print("  {:40s}  {:>8}  {:>8}  {:>7}  {:>8}  {:>8}  {:>7}".format(
          "Config", "IS Ann", "IS Shp", "IS-DD", "OOS Ann", "OOS Shp", "OOS-DD"))
    print("  " + "-" * 100)
    for i, (label, is_r) in enumerate(is_results):
        oos_r = oos_results[i][1]
        print("  {:40s}  {:>+8.2f}%  {:8.3f}  {:6.1f}%  {:>+8.2f}%  {:8.3f}  {:6.1f}%".format(
              label, is_r["ann_ret"], is_r["sharpe"], is_r["max_dd"],
              oos_r["ann_ret"], oos_r["sharpe"], oos_r["max_dd"]))
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(OUTPUT_DIR, "stop_loss_test_{}.json".format(ts))
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"is_results": [(x[0], x[1]) for x in is_results],
                   "oos_results": [(x[0], x[1]) for x in oos_results]}, f, ensure_ascii=False, indent=2)
    print("\nSaved: " + out_file)
    print("Time: {:.0f}s".format(time.time() - t0))

if __name__ == "__main__":
    main()
