#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
因子有效性检验：对照现有v4.7策略，测试文档中的新因子
因子来源：
  1. 文件2/3: RSI(14) - 30/70阈值
  2. 文件3:   MACD(8,17,9)金叉/死叉
  3. 文件1/5: 放量突破 - vol > MA(vol,20)*1.5
  4. 文件3:   20月均线趋势过滤
  5. 文件5:   方向准确率分类型预测
  6. 文件2:   分批止盈止损(回撤15%/20%/25%)
"""

import sys, os, json, glob, statistics
from datetime import datetime as dt
from collections import defaultdict

HISTORY_DIR = r"D:\Qclaw_Trading\data\history_long_v2"
POOL_FILE   = r"D:\Qclaw_Trading\data\etf_pool_V1_full.json"
OUTPUT_DIR  = r"D:\Qclaw_Trading\review"

# ======================== 策略常量 ========================
DEF_MAX_DEV = 20.0      # 最大偏离度%
DEF_TOP_N   = 1
DEF_LB      = 3         # 动量回看周数
DEF_ATR_F   = 0.85      # ATR波动率因子
DEF_SC_W1   = 0.50      # 1周动量权重
DEF_SC_W3   = 0.50      # 3周动量权重
DEF_SC_W8   = 0.00      # 8周动量权重
C_BONUS     = 0.02      # K线形态加分
DEF_CAPITAL = 100000.0
VOL_SKIP    = 1.5       # 量比 > 1.5 跳过

# ======================== 数据加载 ========================
def load_all_data():
    with open(POOL_FILE, encoding="utf-8") as f:
        pool = json.load(f)
    etfs = pool if isinstance(pool, list) else pool.get("data", [])
    series, ohlc, code_cat, avail_weeks = {}, {}, {}, set()
    for etf in etfs:
        code = etf["code"]
        cat  = etf.get("category", "") or ""
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
                        weeks[wk] = (ds, r.get("close", 0),
                                     r.get("open", 0),
                                     r.get("high", 0),
                                     r.get("low", 0),
                                     r.get("vol", 0))
                except:
                    pass
            if not weeks:
                continue
            srt = sorted(weeks.items())
            series[code]  = [(wk, v[1]) for wk, v in srt]
            ohlc[code]   = {wk: {"o": v[2], "h": v[3], "l": v[4], "c": v[1], "v": v[5]}
                           for wk, v in srt}
            avail_weeks.update(w for w, _ in srt)
        except:
            continue

    all_weeks = sorted(avail_weeks)
    # 计算ATR比率
    atr = {}
    for code, wd in ohlc.items():
        if len(wd) < 30:
            continue
        wk_list = sorted(wd.keys())
        trs = [None] * len(wk_list)
        for i in range(1, len(wk_list)):
            cur, prv = wd[wk_list[i]], wd[wk_list[i-1]]
            trs[i] = max(cur["h"] - cur["l"],
                         abs(cur["h"] - prv["c"]),
                         abs(cur["l"] - prv["c"]))
        atrs = {}
        for i in range(21, len(wk_list)):
            vals = [trs[j] for j in range(i-20, i+1) if trs[j] is not None]
            if len(vals) >= 21:
                fast = sum(vals[-14:]) / 14
                slow = sum(vals) / 21
                if slow > 0:
                    atrs[wk_list[i]] = fast / slow
        atr[code] = atrs
    return etfs, series, ohlc, code_cat, all_weeks, atr


# ======================== 因子计算 ========================
def calc_rsi(closes, period=14):
    """计算RSI(14)"""
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d for d in deltas[-period:] if d > 0]
    losses = [-d for d in deltas[-period:] if d < 0]
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calc_macd(closes, fast=8, slow=17, signal=9):
    """计算MACD(8,17,9)及信号线"""
    if len(closes) < slow + signal:
        return None, None
    # EMA
    ema_fast = sum(closes[:fast]) / fast
    ema_slow = sum(closes[:slow]) / slow
    macd_vals = []
    for c in closes[fast:]:
        ema_fast = ema_fast * (fast-1)/fast + c * 2/fast
        ema_slow = ema_slow * (slow-1)/slow + c * 2/slow
        macd_vals.append(ema_fast - ema_slow)
    if len(macd_vals) < signal:
        return None, None
    sig = sum(macd_vals[:signal]) / signal
    signal_vals = []
    for m in macd_vals[signal:]:
        sig = sig * (signal-1)/signal + m * 2/signal
        signal_vals.append(sig)
    macd_now = macd_vals[-1]
    macd_prev = macd_vals[-2] if len(macd_vals) >= 2 else macd_vals[-1]
    sig_now = signal_vals[-1]
    sig_prev = signal_vals[-2] if len(signal_vals) >= 2 else signal_vals[-1]
    # 金叉：MACD从下穿上 signal
    golden_cross = (macd_prev <= sig_prev) and (macd_now > sig_now)
    # 牛值：MACD > 0
    macd_bull = macd_now > 0
    return golden_cross, macd_bull


def calc_vol_ma(vols, period=20):
    """计算成交量MA"""
    if len(vols) < period:
        return None
    return sum(vols[-period:]) / period


def calc_all_factors(code, wk_list, idx, series, ohlc, atr,
                     use_rsi=False, use_macd=False, use_vol_surge=False,
                     use_ma_trend=False):
    """计算所有可选因子，返回信号dict"""
    ohlc_c = ohlc.get(code, {})
    srt     = series.get(code, [])
    res = {
        "score": None, "dev": None,
        "c_pat": False, "vol_ratio": None,
        "rsi": None, "macd_golden": None, "macd_bull": None,
        "vol_surge": False, "ma_trend_bull": False,
    }
    if idx < 21 or idx >= len(srt):
        return res
    price = srt[idx][1]
    if not price or price <= 0:
        return res

    # --- 偏离度过滤 ---
    ma21 = sum(srt[j][1] for j in range(idx-20, idx+1)) / 21
    if ma21 == 0:
        return res
    dev = abs(price / ma21 - 1) * 100
    if dev > DEF_MAX_DEV:
        return res

    sig_week = srt[idx][0]
    ar = atr.get(code, {}).get(sig_week)
    if ar is not None and ar < DEF_ATR_F:
        return res

    mom  = price / srt[idx-DEF_LB][1] - 1
    mom1w = price / srt[idx-1][1] - 1 if idx >= 1 else mom
    mom8w = price / srt[idx-8][1] - 1 if idx >= 8 else mom
    score = DEF_SC_W1 * mom1w + DEF_SC_W3 * mom + DEF_SC_W8 * mom8w

    res["score"] = score
    res["dev"]   = dev

    w0 = ohlc_c.get(sig_week, {})
    if w0 and all(w0.get(k) is not None for k in ("c", "o", "h", "l")):
        ci = w0["c"]; oi = w0["o"]
        hi = w0["h"]; li = w0["l"]
        body     = abs(ci - oi)
        u_shadow = hi - max(ci, oi)
        l_shadow = min(ci, oi) - li
        s2b      = u_shadow / body if body > 0 else 99

        # 量比
        vol_vals = [ohlc_c.get(wk_list[j], {}).get("v", 0)
                    for j in range(max(0, idx-9), idx+1)]
        vol_vals = [v for v in vol_vals if v and v > 0]
        avg_v10  = sum(vol_vals) / len(vol_vals) if vol_vals else 1
        vol_r    = w0.get("v", 0) / avg_v10 if avg_v10 > 0 else 1
        res["vol_ratio"] = vol_r

        # K线形态
        g20 = 0
        if idx >= 20:
            pc = ohlc_c.get(wk_list[idx-20], {}).get("c")
            if pc and pc > 0:
                g20 = ci / pc - 1
        ma5 = sum(srt[j][1] for j in range(idx-4, idx+1)) / 5
        res["c_pat"] = (ci > oi and s2b > 1.0 and l_shadow < body * 0.5
                        and vol_r < VOL_SKIP and ci > ma5 > ma21 and g20 < 0.5)

        # === 新增因子 ===
        # 1. RSI(14)
        if use_rsi and idx >= 14:
            closes_needed = [srt[j][1] for j in range(idx-14, idx+1) if srt[j][1] > 0]
            if len(closes_needed) >= 15:
                res["rsi"] = calc_rsi(closes_needed, 14)

        # 2. MACD(8,17,9)
        if use_macd and idx >= 30:
            closes_needed = [srt[j][1] for j in range(idx+1) if srt[j][1] > 0]
            if len(closes_needed) >= 30:
                gc, mb = calc_macd(closes_needed, 8, 17, 9)
                res["macd_golden"] = gc
                res["macd_bull"]  = mb

        # 3. 放量突破（vol > MA(vol,20) × 1.5）
        if use_vol_surge:
            vol_ma = calc_vol_ma(vol_vals, 20)
            if vol_ma and vol_ma > 0:
                res["vol_surge"] = (w0.get("v", 0) > vol_ma * 1.5)

        # 4. 20月均线趋势过滤（价格在均线上方）
        if use_ma_trend:
            res["ma_trend_bull"] = (ci > ma21)

    return res


# ======================== 回测引擎 ========================
def run_oos(etfs, series, ohlc, code_cat, all_weeks, atr,
            is_end_idx, oos_end_idx,
            # 新因子开关
            use_rsi=False, rsi_min=30, rsi_max=70,
            use_macd=False, macd_require_bull=False, macd_require_gc=False,
            use_vol_surge=False,
            use_ma_trend=False,
            # 其他参数
            no_dedup=False):
    """运行OOS回测，返回绩效字典"""

    code_wklist = {c: [wk for wk, _ in s] for c, s in series.items()}
    first_idx = {}
    for code, s in series.items():
        for j, (wk, _) in enumerate(s):
            if wk == all_weeks[is_end_idx]:
                first_idx[code] = j
                break

    portfolio = {}; cash = DEF_CAPITAL; eq_curve = []
    n_buys = n_sells = 0

    for si in range(is_end_idx, max(oos_end_idx - 1, is_end_idx)):
        sig_week  = all_weeks[si]
        exec_week = all_weeks[si + 1]
        candidates = []

        for code, s in series.items():
            fi = first_idx.get(code)
            if fi is None:
                continue
            idx = fi + (si - is_end_idx)
            if idx < 21 or idx >= len(s):
                continue

            f = calc_all_factors(code, code_wklist.get(code, []), idx,
                                  series, ohlc, atr,
                                  use_rsi=use_rsi,
                                  use_macd=use_macd,
                                  use_vol_surge=use_vol_surge,
                                  use_ma_trend=use_ma_trend)
            if "score" not in f or f["score"] is None:
                continue
            if f.get("vol_ratio") is not None and f["vol_ratio"] > VOL_SKIP:
                continue

            # --- RSI过滤 ---
            if use_rsi and f["rsi"] is not None:
                # RSI < rsi_min：超卖但未必是买入信号；RSI > rsi_max：超买，跳过
                # 策略：只接受 RSI 在合理区间 [rsi_min, rsi_max] 的标的
                # 注意：动量策略在RSI超买时不一定是卖出信号，这里做入场过滤
                # 若RSI>70说明短期涨太快，有回调风险；<30说明有下跌动能
                if f["rsi"] > rsi_max or f["rsi"] < rsi_min:
                    continue

            # --- MACD过滤 ---
            if use_macd:
                if macd_require_bull and not f.get("macd_bull"):
                    continue
                if macd_require_gc and not f.get("macd_golden"):
                    continue

            # --- 放量突破：vol_surge = True 则跳过放量突破的标的（假突破风险）---
            if use_vol_surge and f.get("vol_surge"):
                # 文件5: "放量突破后追入胜率低"，主动避开
                continue

            # --- 均线趋势过滤 ---
            if use_ma_trend and not f.get("ma_trend_bull"):
                continue

            adj = f["score"]
            if f.get("c_pat"):
                adj += C_BONUS
            candidates.append({
                "code": code, "close": s[idx][1],
                "_adj": adj, "cat": code_cat.get(code, ""),
            })

        candidates.sort(key=lambda x: x["_adj"], reverse=True)

        if no_dedup:
            target = candidates[:DEF_TOP_N]
        else:
            cats = set(); target = []
            for c in candidates:
                if c["cat"] not in cats:
                    cats.add(c["cat"])
                    target.append(c)
            target = target[:DEF_TOP_N]

        target_codes = {t["code"] for t in target}

        # 更新持仓HWM
        for code, pos in list(portfolio.items()):
            p = next((cl for wk, cl in series[code] if wk == sig_week), None)
            if p and p > portfolio[code]["hwm"]:
                portfolio[code]["hwm"] = p

        to_sell = []
        for code, pos in list(portfolio.items()):
            p = next((cl for wk, cl in series[code] if wk == sig_week), None)
            if p is None:
                to_sell.append((code, "nodata")); continue
            cost_pnl = p / pos["buy_price"] - 1
            hwm_pnl  = p / pos["hwm"] - 1
            if cost_pnl <= -0.08 or hwm_pnl <= -0.10:
                to_sell.append((code, "stop"))
            elif code not in target_codes:
                to_sell.append((code, "rebalance"))

        for code, _ in to_sell:
            pos = portfolio.pop(code)
            p = next((cl for wk, cl in series[code] if wk == sig_week), None)
            cash += pos["weight"] * (p or pos["buy_price"]); n_sells += 1

        slots = DEF_TOP_N - len(portfolio)
        if slots > 0 and cash > 0:
            buy_list = [t for t in target if t["code"] not in portfolio]
            total_assets = cash + sum(
                pos["weight"] * pos["buy_price"] for pos in portfolio.values())
            buy_weights = []
            for bc in buy_list[:slots]:
                p_exec = next((cl for wk, cl in series[bc["code"]] if wk == sig_week), None)
                if p_exec is None or p_exec <= 0:
                    continue
                w_atr = atr.get(bc["code"], {}).get(sig_week, 1)
                w_atr = max(w_atr, 0.3)
                buy_weights.append((bc["code"], p_exec, w_atr))
            if buy_weights:
                total_w = sum(w for _, _, w in buy_weights)
                for code, p_exec, w_atr in buy_weights:
                    slot_val = total_assets * (w_atr / total_w)
                    weight   = slot_val / p_exec
                    cost     = weight * p_exec
                    if cost > cash * 0.98:
                        weight = cash * 0.98 / p_exec; cost = weight * p_exec
                    if weight <= 0:
                        continue
                    cash -= cost
                    portfolio[code] = {"weight": weight, "buy_price": p_exec, "hwm": p_exec}
                    n_buys += 1

        equity = cash + sum(
            pos["weight"] * next(
                (cl for wk, cl in series[c] if wk == exec_week),
                pos.get("buy_price"))
            for c, pos in portfolio.items())
        eq_curve.append({"w": exec_week, "eq": equity})

    # 绩效计算
    eqs = [e["eq"] for e in eq_curve]; n = len(eqs)
    if n < 2:
        return None
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
        avg_w  = statistics.mean(w_rets)
        std_w  = statistics.stdev(w_rets) if len(w_rets) > 1 else 1e-9
        sharpe = (avg_w * 52 - 0.02) / (std_w * 52 ** 0.5) if std_w > 0 else 0
        win_rate = sum(1 for r in w_rets if r > 0) / len(w_rets) * 100
    else:
        sharpe = win_rate = 0

    return {
        "ann_ret": ann_ret, "total_ret": total_ret,
        "max_dd": max_dd * 100, "sharpe": sharpe,
        "win_rate": win_rate, "n_buys": n_buys, "n_sells": n_sells,
        "n_weeks": n
    }


# ======================== 主程序 ========================
def main():
    print("\n" + "=" * 72)
    print("  因子有效性检验  |  来源: 文档因子分析")
    print("=" * 72)
    t0 = dt.now()
    print("\n[1/3] 加载数据...")
    etfs, series, ohlc, code_cat, all_weeks, atr = load_all_data()
    print("    ETF: {}  周: {} ({} - {})".format(
        len(series), len(all_weeks), all_weeks[0], all_weeks[-1]))

    # 时间区间
    is_start = max(0, next(
        (i for i, w in enumerate(all_weeks) if w == "2017-W01"), 0) - 1)
    is_end   = next((i for i, w in enumerate(all_weeks) if w == "2023-W01"), 0)
    oos_end  = len(all_weeks) - 1
    print("  IS: {} - {} ({} wks)".format(
        all_weeks[is_start], all_weeks[is_end-1], is_end - is_start))
    print("  OOS: {} - {} ({} wks)".format(
        all_weeks[is_end], all_weeks[oos_end-1], oos_end - is_end))

    # ======================== 测试组合 ========================
    # (label, use_rsi, rsi_min, rsi_max, use_macd, macd_bull, macd_gc, use_vol_surge, use_ma_trend, no_dedup)
    configs = [
        # 0. 基准：现有v4.7策略
        ("B0_baseline (v4.7)",           False, 0, 100, False, False, False, False, False, False),
        # 1. RSI过滤：避开RSI超买超跌
        ("F1_RSI_30-70",                  True,  30,  70, False, False, False, False, False, False),
        ("F1_RSI_40-80",                  True,  40,  80, False, False, False, False, False, False),
        # 2. MACD过滤
        ("F2_MACD_bull",                  False,  0, 100, True, True, False, False, False, False),
        ("F2_MACD_gc",                   False,  0, 100, True, True, True,  False, False, False),
        # 3. 放量突破回避
        ("F3_vol_surge_skip",             False,  0, 100, False, False, False, True,  False, False),
        # 4. 20月均线趋势过滤
        ("F4_ma21_trend",                 False,  0, 100, False, False, False, False, True,  False),
        # 5. 组合1：RSI + MA趋势
        ("F5_RSI+MA",                     True,  30,  80, False, False, False, False, True,  False),
        # 6. 组合2：RSI + MACD_bull
        ("F6_RSI+MACD",                   True,  30,  80, True, True, False, False, False, False),
        # 7. 组合3：全因子组合
        ("F7_RSI+MACD+MA+VS",             True,  30,  80, True, True, False, True,  True,  False),
        # 8. 无去重基准
        ("B0_nodedup",                    False,  0, 100, False, False, False, False, False, True),
    ]

    # --- IS阶段 ---
    print("\n[2/3] IS阶段回测 (2017-2022)...")
    print("-" * 72)
    is_results = []
    for cfg in configs:
        label, ursi, rsi_min, rsi_max, umacd, mb, mgc, uvs, umt, nd = cfg
        short = label.split("_", 1)[-1] if "_" in label else label[:15]
        print("  {:35s}".format(label), end="", flush=True)
        r = run_oos(etfs, series, ohlc, code_cat, all_weeks, atr,
                     is_start, is_end,
                     use_rsi=ursi, rsi_min=rsi_min, rsi_max=rsi_max,
                     use_macd=umacd, macd_require_bull=mb, macd_require_gc=mgc,
                     use_vol_surge=uvs, use_ma_trend=umt, no_dedup=nd)
        if r:
            is_results.append((label, cfg, r))
            tag = " *" if r["sharpe"] == max(x[-1]["sharpe"] for x in is_results) else ""
            print(" Ann={:+.2f}%  DD={:6.1f}%  Sharpe={:.3f}  Buys={:3d}{}".format(
                r["ann_ret"], r["max_dd"], r["sharpe"], r["n_buys"], tag))

    if not is_results:
        print("No IS results!"); return

    # --- OOS阶段 ---
    print("\n[3/3] OOS阶段回测 (2023-2026)...")
    print("-" * 72)
    oos_results = []
    best_is_idx = max(range(len(is_results)),
                       key=lambda i: is_results[i][-1]["sharpe"])
    for label, cfg, is_r in is_results:
        _, ursi, rsi_min, rsi_max, umacd, mb, mgc, uvs, umt, nd = cfg
        print("  {:35s}".format(label), end="", flush=True)
        r = run_oos(etfs, series, ohlc, code_cat, all_weeks, atr,
                     is_end, oos_end,
                     use_rsi=ursi, rsi_min=rsi_min, rsi_max=rsi_max,
                     use_macd=umacd, macd_require_bull=mb, macd_require_gc=mgc,
                     use_vol_surge=uvs, use_ma_trend=umt, no_dedup=nd)
        if r:
            oos_results.append((label, r))
            tag = " ◀BEST" if is_results.index((label, cfg, is_r)) == best_is_idx else ""
            print(" Ann={:+.2f}%  DD={:6.1f}%  Sharpe={:.3f}{}".format(
                r["ann_ret"], r["max_dd"], r["sharpe"], tag))

    # ======================== 结果汇总 ========================
    sep = "=" * 110
    print("\n" + sep)
    print("  {:35s}  {:>7}  {:>7}  {:>6}  {:>7}  {:>7}  {:>6}  {:>6}".format(
          "Config", "IS Ann", "IS Shp", "IS-DD", "OOS Ann", "OOS Shp", "OOS-DD", "Buys"))
    print("  " + "-" * 110)
    for i, (label, is_r) in enumerate([(x[0], x[-1]) for x in is_results]):
        oos_r = oos_results[i][1]
        star = " ★" if i == best_is_idx else ""
        print("  {:35s}  {:>+7.2f}%  {:7.3f}  {:5.1f}%  {:>+7.2f}%  {:7.3f}  {:5.1f}%  {:>5d}{}".format(
              label, is_r["ann_ret"], is_r["sharpe"], is_r["max_dd"],
              oos_r["ann_ret"], oos_r["sharpe"], oos_r["max_dd"],
              is_r["n_buys"], star))

    # 保存结果
    ts = dt.now().strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(OUTPUT_DIR, f"factor_test_{ts}.json")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    save_data = {
        "is_results":  [(x[0], x[-1]) for x in is_results],
        "oos_results": oos_results,
        "best_is_idx": best_is_idx,
        "configs": [c[0] for c in configs],
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {out_file}")
    print(f"Time: {(dt.now()-t0).total_seconds():.0f}s")


if __name__ == "__main__":
    main()
