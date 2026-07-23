#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
复合止损回测：MA21跌破 + 排名跌出 → 触发止损
对比三种止损策略：
  1. baseline: 当前v4.7止损（-8%成本 或 -10%高水）
  2. ma21_stop: 价格<MA21时止损（不等待-8%）
  3. composite_stop: 价格<MA21 且 不在top2时止损（最严格）
"""
import sys, os, json, glob, statistics
from datetime import datetime as dt
from collections import defaultdict

HISTORY_DIR = r"D:\Qclaw_Trading\data\history_long_v2"
POOL_FILE   = r"D:\Qclaw_Trading\data\etf_pool_V1_full.json"
OUTPUT_DIR   = r"D:\Qclaw_Trading\review"

# v4.7 参数
DEF_MAX_DEV, DEF_TOP_N, DEF_LB = 20.0, 1, 3
DEF_ATR_F   = 0.85
DEF_SC_W1, DEF_SC_W3, DEF_SC_W8 = 0.50, 0.50, 0.00
C_BONUS, DEF_CAPITAL = 0.00, 100000.0

def load_all_data():
    with open(POOL_FILE, encoding="utf-8") as f: pool = json.load(f)
    etfs = pool if isinstance(pool, list) else pool.get("data", [])
    series, ohlc, code_cat, avail_weeks = {}, {}, {}, set()
    for etf in etfs:
        code, cat = etf["code"], etf.get("category", "") or ""
        code_cat[code] = cat
        matches = glob.glob(os.path.join(HISTORY_DIR, code + ".json"))
        if not matches: matches = glob.glob(os.path.join(HISTORY_DIR, "*" + code + ".json"))
        if not matches: continue
        try:
            with open(matches[0], encoding="utf-8") as f:
                raw = f.read().replace("NaN", "null")
            d = json.loads(raw)
            recs = d.get("records", []) if isinstance(d, dict) else d
            if not recs: continue
            if isinstance(recs[0], list):
                recs = [{"date":r[0],"open":r[1],"high":r[2],"low":r[3],"close":r[4],"vol":r[5]} for r in recs]
            elif "w" in recs[0]:
                recs = [{"date":r.get("date","") or r.get("w",""),
                         "open":r.get("open",r.get("close",0)),
                         "high":r.get("high",r.get("close",0)),
                         "low":r.get("low",r.get("close",0)),
                         "close":r.get("close",0),
                         "vol":r.get("vol",0)} for r in recs]
            weeks = {}
            for r in recs:
                ds = r.get("date","") or r.get("w","")
                if not ds: continue
                try:
                    y, wn, _ = dt.strptime(ds, "%Y-%m-%d").isocalendar()
                    wk = "{}-W{:02d}".format(y, wn)
                    if wk not in weeks or ds > weeks[wk][0]:
                        weeks[wk] = (ds, r.get("close",0), r.get("open",0),
                                     r.get("high",0), r.get("low",0), r.get("vol",0))
                except: pass
            if not weeks: continue
            srt = sorted(weeks.items())
            series[code] = [(wk, v[1]) for wk, v in srt]
            ohlc[code]   = {wk: {"o":v[2],"h":v[3],"l":v[4],"c":v[1],"v":v[5]} for wk,v in srt}
            avail_weeks.update(w for w,_ in srt)
        except: continue
    all_weeks = sorted(avail_weeks)
    atr = {}
    for code, wd in ohlc.items():
        if len(wd) < 30: continue
        wk_list = sorted(wd.keys())
        trs = [None] * len(wk_list)
        for i in range(1, len(wk_list)):
            cur, prv = wd[wk_list[i]], wd[wk_list[i-1]]
            trs[i] = max(cur["h"]-cur["l"],
                          abs(cur["h"]-prv["c"]), abs(cur["l"]-prv["c"]))
        atrs = {}
        for i in range(21, len(wk_list)):
            vals = [trs[j] for j in range(i-20,i+1) if trs[j] is not None]
            if len(vals) >= 21:
                fast = sum(vals[-14:])/14; slow = sum(vals)/21
                if slow > 0: atrs[wk_list[i]] = fast / slow
        atr[code] = atrs
    return etfs, series, ohlc, code_cat, all_weeks, atr

def calc_factors(code, wk_list, idx, series, ohlc, atr):
    ohlc_c = ohlc.get(code, {}); srt = series.get(code, [])
    res = {"score":None}
    if idx < 21 or idx >= len(srt): return res
    price = srt[idx][1]
    if not price or price <= 0: return res
    ma5  = sum(srt[j][1] for j in range(idx-4, idx+1)) / 5
    ma21 = sum(srt[j][1] for j in range(idx-20, idx+1)) / 21
    if ma21 == 0: return res
    dev = abs(price / ma21 - 1) * 100
    if dev > DEF_MAX_DEV: return res
    if price <= ma21: return res          # v4.7 MA21硬过滤
    sig_week = srt[idx][0]
    ar = atr.get(code, {}).get(sig_week)
    if ar is not None and ar < DEF_ATR_F: return res
    mom   = price / srt[idx-DEF_LB][1] - 1
    mom1w = price / srt[idx-1][1] - 1 if idx >= 1 else mom
    mom8w = price / srt[idx-8][1] - 1 if idx >= 8 else mom
    score = DEF_SC_W1*mom1w + DEF_SC_W3*mom + DEF_SC_W8*mom8w
    res["score"] = score; res["dev"] = dev
    res["ma21"] = ma21; res["price"] = price
    # 计算量比（与backtest_yearly_v47.py一致）
    w0 = ohlc_c.get(sig_week, {})
    if w0 and all(w0.get(k) for k in ("c","o","h","l")):
        vol_vals = [ohlc_c.get(wk_list[j],{}).get("v",0) for j in range(max(0,idx-9),idx+1)]
        vol_vals = [v for v in vol_vals if v and v > 0]
        avg10 = sum(vol_vals)/len(vol_vals) if vol_vals else 1
        vr = w0.get("v",0)/avg10 if avg10 > 0 else 1
        res["vr"] = vr
    else:
        res["vr"] = 1.0
    return res

def run_oos(etfs, series, ohlc, code_cat, all_weeks, atr, is_end_idx, oos_end_idx,
            stop_mode="baseline", top_for_stop=2):
    """
    stop_mode:
      baseline:      -8%成本 或 -10%高水止损（当前v4.7）
      ma21_stop:     baseline + price < MA21 止损
      composite_stop: baseline + (price < MA21 AND 不在前top_for_stop名) 止损
    """
    code_wklist = {c: [wk for wk,_ in s] for c,s in series.items()}
    first_idx = {}
    for code, s in series.items():
        for j, (wk,_) in enumerate(s):
            if wk == all_weeks[is_end_idx]: first_idx[code] = j; break

    portfolio = {}; cash = DEF_CAPITAL; eq_curve = []
    n_buys = n_sells = n_ma21_stop = 0
    skip_set = set()

    for si in range(is_end_idx, max(oos_end_idx-1, is_end_idx)):
        sig_week  = all_weeks[si]
        exec_week = all_weeks[si+1]

        # 计算当前候选
        candidates = []
        for code, s in series.items():
            fi = first_idx.get(code)
            if fi is None: continue
            idx = fi + (si - is_end_idx)
            if idx < 21 or idx >= len(s): continue
            f = calc_factors(code, code_wklist.get(code,[]), idx, series, ohlc, atr)
            if "score" not in f: continue
            # 与backtest_yearly_v47.py一致：vr>1.5时跳过
            if f.get("vr", 1.0) > 1.5: continue
            adj = f["score"]
            candidates.append({
                "code": code, "close": s[idx][1],
                "_adj": adj, "cat": code_cat.get(code,""),
                "ma21": f.get("ma21",0), "price": f.get("price",0)
            })
        candidates = [c for c in candidates if c.get("_adj") is not None]
        candidates.sort(key=lambda x: x["_adj"], reverse=True)
        # 赛道去重
        cats=set(); target=[]
        for c in candidates:
            if c["cat"] not in cats: cats.add(c["cat"]); target.append(c)
        target = target[:DEF_TOP_N]
        top_candidates = candidates[:top_for_stop]   # 用于复合止损判断
        target_codes  = {t["code"] for t in target}
        top_codes      = {c["code"] for c in top_candidates}

        # 更新高水
        for code in portfolio:
            p = next((cl for wk,cl in series[code] if wk==sig_week), None)
            if p and p > portfolio[code]["hwm"]: portfolio[code]["hwm"] = p

        # 止损判断
        to_sell = []
        for code, pos in list(portfolio.items()):
            p = next((cl for wk,cl in series[code] if wk==sig_week), None)
            if p is None: to_sell.append((code,"nodata")); continue
            cost_pnl = p/pos["buy_price"] - 1
            hwm_pnl  = p/pos["hwm"]       - 1

            stop_triggered = False; stop_reason = ""
            # baseline 止损
            if cost_pnl <= -0.08 or hwm_pnl <= -0.10:
                stop_triggered = True; stop_reason = "cost/hwm"
            # ma21_stop
            elif stop_mode in ("ma21_stop","composite_stop"):
                # 获取当前MA21
                fi = first_idx.get(code)
                if fi is not None:
                    idx_now = fi + (si - is_end_idx)
                    if idx_now >= 21 and idx_now < len(series[code]):
                        srt_c = series[code]
                        ma21_now = sum(srt_c[j][1] for j in range(idx_now-20, idx_now+1)) / 21
                        price_now = srt_c[idx_now][1]
                        if price_now < ma21_now:
                            if stop_mode == "ma21_stop":
                                stop_triggered = True; stop_reason = "ma21_break"
                            elif stop_mode == "composite_stop":
                                # 复合：price<MA21 且 不在前top名
                                if code not in top_codes:
                                    stop_triggered = True; stop_reason = "ma21+rank"
            if stop_triggered:
                to_sell.append((code, stop_reason))
                if stop_reason in ("ma21_break","ma21+rank"): n_ma21_stop += 1

        # 执行卖出
        for code, reason in to_sell:
            pos = portfolio.pop(code)
            p = next((cl for wk,cl in series[code] if wk==sig_week), None)
            cash += pos["weight"] * (p or pos["buy_price"]); n_sells += 1

        # 买入
        slots = DEF_TOP_N - len(portfolio)
        if slots > 0 and cash > 0:
            buy_list = [t for t in target if t["code"] not in portfolio]
            total_assets = cash + sum(pos["weight"]*pos["buy_price"] for pos in portfolio.values())
            buy_weights = []
            for bc in buy_list[:slots]:
                p_exec = next((cl for wk,cl in series[bc["code"]] if wk==sig_week), None)
                if p_exec is None or p_exec <= 0: continue
                buy_weights.append((bc["code"], p_exec, 1.0))
            if buy_weights:
                total_w = sum(w for _,_,w in buy_weights)
                for code, p_exec, rw in buy_weights:
                    slot_val = total_assets * (rw/total_w)
                    weight   = slot_val / p_exec; cost = weight * p_exec
                    if cost > cash*0.98: weight = cash*0.98/p_exec; cost = weight*p_exec
                    if weight <= 0: continue
                    cash -= cost
                    portfolio[code] = {"weight":weight,"buy_price":p_exec,"hwm":p_exec}
                    n_buys += 1

        equity = cash + sum(
            pos["weight"] * next((cl for wk,cl in series[c] if wk==exec_week),
                                  pos["buy_price"])
            for c,pos in portfolio.items())
        eq_curve.append({"w":exec_week, "eq":equity})

    # 统计
    eqs = [e["eq"] for e in eq_curve]; n = len(eqs)
    if n < 2: return None
    init, final = eqs[0], eqs[-1]
    total_ret = (final/init - 1)*100; years = n/52
    ann_ret   = ((final/init)**(1/years)-1)*100 if years>0 else 0
    peak = eqs[0]; max_dd = 0
    for eq in eqs:
        if eq > peak: peak = eq
        dd = eq/peak - 1
        if dd < max_dd: max_dd = dd
    w_rets = [eqs[i]/eqs[i-1]-1 for i in range(1,n) if eqs[i-1]>0]
    if w_rets:
        avg_w = statistics.mean(w_rets); std_w = statistics.stdev(w_rets) if len(w_rets)>1 else 1e-9
        sharpe = (avg_w*52 - 0.02)/(std_w*52**0.5) if std_w>0 else 0
        win_rate = sum(1 for r in w_rets if r>0)/len(w_rets)*100
    else: sharpe = win_rate = 0
    return {
        "ann_ret":round(ann_ret,2), "total_ret":round(total_ret,2),
        "max_dd":round(max_dd*100,2), "sharpe":round(sharpe,3),
        "win_rate":round(win_rate,1), "n_buys":n_buys, "n_sells":n_sells,
        "n_ma21_stop": n_ma21_stop, "n_weeks":n
    }

def main():
    print("加载数据...")
    etfs, series, ohlc, code_cat, all_weeks, atr = load_all_data()
    print(f"ETF数:{len(series)}, 周数:{len(all_weeks)}")

    # 找分割点
    is_end_idx = None
    for i, w in enumerate(all_weeks):
        if w.startswith("2023"): is_end_idx = i; break
    if is_end_idx is None: is_end_idx = int(len(all_weeks)*0.6)
    print(f"IS截止: {all_weeks[is_end_idx-1]}, OOS: {all_weeks[is_end_idx]} ~ {all_weeks[-1]}")

    results = {}
    for mode in ["baseline","ma21_stop","composite_stop"]:
        r = run_oos(etfs, series, ohlc, code_cat, all_weeks, atr,
                     is_end_idx, len(all_weeks)-1, stop_mode=mode)
        results[mode] = r
        print(f"\n{'='*50}")
        print(f"止损模式: {mode}")
        if r:
            print(f"  年化收益: {r['ann_ret']:+.2f}%")
            print(f"  总收益:   {r['total_ret']:+.2f}%")
            print(f"  最大回撤: {r['max_dd']:.2f}%")
            print(f"  夏普比:   {r['sharpe']:.3f}")
            print(f"  胜率:     {r['win_rate']:.1f}%")
            print(f"  买入次数: {r['n_buys']}, 卖出:{r['n_sells']}")
            print(f"  MA21触发: {r['n_ma21_stop']}次")

    # 年度回报对比
    print(f"\n{'='*50}")
    print("年度回报对比 (2023-2026 OOS):")
    years_list = [2023,2024,2025,2026]
    for y in years_list:
        yr_key = f"{y}-W01"
        yr_end = f"{y}-W52"
        if yr_key not in all_weeks: continue
        yi_start = all_weeks.index(yr_key)
        yi_end   = all_weeks.index(yr_end) if yr_end in all_weeks else len(all_weeks)-1

        for mode in ["baseline","ma21_stop","composite_stop"]:
            # 重新跑只到该年
            r = run_oos(etfs, series, ohlc, code_cat, all_weeks, atr,
                        is_end_idx, yi_end, stop_mode=mode)
            if r: print(f"  {y} {mode:20s}: {r['ann_ret']:+.1f}%  MaxDD:{r['max_dd']:.1f}%  Sharpe:{r['sharpe']:.2f}")

if __name__ == "__main__": main()
