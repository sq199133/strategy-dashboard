# -*- coding: utf-8 -*-
"""
MA20 + MACD 策略 20年回测
数据：ETF→Sina接口(akshare fund_etf_hist_sina)，指数→akshare东方财富
"""
import sys
import json
import time
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import akshare as ak

# ============================================================
# 数据获取
# ============================================================
def fetch_etf_sina(code, start="2005-01-01", end="2026-04-17"):
    """通过新浪获取ETF历史（前复权），支持长区间"""
    try:
        # Sina格式需要 sh 前缀
        sym = ("sh" + code) if code.startswith(("1", "5", "6", "9")) else ("sz" + code)
        df = ak.fund_etf_hist_sina(symbol=sym)
        if df is None or len(df) < 50:
            return None
        df.columns = [c.strip() for c in df.columns]
        # 新浪字段名：date, code, name, open, close, high, low, volume
        if "date" not in df.columns:
            return None
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df = df[(df["date"] >= start) & (df["date"] <= end)]
        # 数值化
        for col in ["open", "close", "high", "low", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["close"]).reset_index(drop=True)
        return df[["date", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        return None


def fetch_index_em(code, start="2005-01-01", end="2026-04-17"):
    """通过东方财富获取指数历史"""
    try:
        sym = ("sh" + code) if code.startswith("0") else ("sz" + code)
        df = ak.stock_zh_index_daily(symbol=sym)
        if df is None or len(df) < 50:
            return None
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df = df[(df["date"] >= start) & (df["date"] <= end)]
        for col in ["close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["close"]).reset_index(drop=True)
        return df[["date", "close"]]
    except Exception:
        return None


# ============================================================
# 指标
# ============================================================
def calc_ema(data, period):
    k = 2.0 / (period + 1)
    r = [float(data[0])]
    for v in data[1:]:
        r.append(float(v) * k + r[-1] * (1 - k))
    return r


def calc_macd(closes, mf=12, ms=26, sig=9):
    if len(closes) < ms + sig + 5:
        return None, None, None
    ef = calc_ema(closes, mf)
    es = calc_ema(closes, ms)
    mline = [ef[i] - es[i] for i in range(len(closes))]
    sline = calc_ema(mline, sig)
    hist = [mline[i] - sline[i] for i in range(len(mline))]
    return mline, sline, hist


# ============================================================
# 策略信号
# ============================================================
def gen_signals(closes, ma=20, mf=12, ms=26, sig=9):
    n = len(closes)
    out = [0] * n
    pos = 0
    warmup = max(ma + 3, ms + sig + 3)

    for i in range(warmup, n):
        price = closes[i]
        ma_val = sum(closes[i - ma + 1:i + 1]) / ma

        res = calc_macd(closes[:i + 1], mf, ms, sig)
        if res[0] is None:
            continue
        m0, s0, h0 = res[0][-1], res[1][-1], res[2][-1]
        m1, s1, h1 = res[0][-2], res[1][-2], res[2][-2]

        above_ma = price > ma_val
        # MA方向（近3日走平或向上）
        ma_3 = [sum(closes[i - j - ma + 1:i - j + 1]) / ma for j in range(3)]
        ma_ok = ma_3[0] >= min(ma_3) - 0.001

        golden = (m1 <= s1) and (m0 > s0)
        above_zero = m0 > 0
        red_ok = (h1 > 0) and (h0 >= h1 * 0.8)

        buy = above_ma and ma_ok and (golden or (above_zero and red_ok))
        sell = (price < ma_val) or ((m1 >= s1) and (m0 < s0)) or ((h1 > 0) and (h0 < 0))

        if pos == 0 and buy:
            out[i] = 1
            pos = 1
        elif pos == 1 and sell:
            out[i] = -1
            pos = 0

    return out


# ============================================================
# 回测引擎
# ============================================================
def run_bt(df, sigs, init=100000.0, stop=0.05):
    closes = df["close"].tolist()
    dates = df["date"].tolist()
    n = len(closes)
    cash = float(init)
    shares = 0
    pos = 0
    equity = []
    trades = []

    for i in range(n):
        price = closes[i]

        # 止损
        if pos == 1 and shares > 0 and trades:
            loss = (shares * price - shares * trades[-1]["buy_price"]) / (shares * trades[-1]["buy_price"])
            if loss <= -stop:
                cash += shares * price
                trades[-1]["sell_date"] = str(dates[i])[:10]
                trades[-1]["sell_price"] = float(price)
                trades[-1]["ret"] = float((price - trades[-1]["buy_price"]) / trades[-1]["buy_price"])
                trades[-1]["stop"] = True
                shares = 0
                pos = 0

        sig = sigs[i]
        if sig == 1 and pos == 0:
            bp = float(price)
            sh = int(cash / bp)
            cash -= sh * bp
            pos = 1
            trades.append({"buy_date": str(dates[i])[:10], "buy_price": bp, "shares": sh})
        elif sig == -1 and pos == 1:
            cash += shares * float(price)
            trades[-1]["sell_date"] = str(dates[i])[:10]
            trades[-1]["sell_price"] = float(price)
            trades[-1]["ret"] = float((price - trades[-1]["buy_price"]) / trades[-1]["buy_price"])
            shares = 0
            pos = 0

        equity.append(float(cash + shares * price))

    # 平仓
    if pos == 1 and shares > 0:
        cash += shares * closes[-1]
        trades[-1]["sell_date"] = str(dates[-1])[:10]
        trades[-1]["sell_price"] = float(closes[-1])
        trades[-1]["ret"] = float((closes[-1] - trades[-1]["buy_price"]) / trades[-1]["buy_price"])
        shares = 0
        pos = 0

    # 绩效指标
    eq = np.array(equity, dtype=np.float64)
    total_ret = (cash - init) / init
    rets = np.diff(eq) / eq[:-1]
    rets = rets[np.isfinite(rets)]
    years = max((dates[-1] - dates[0]).days / 365.25, 0.01)
    ann = (cash / init) ** (1.0 / years) - 1
    sharpe = (rets.mean() / max(rets.std(), 1e-10)) * np.sqrt(252)
    peak = float(init)
    max_dd = 0.0
    for v in eq:
        peak = max(peak, v)
        max_dd = max(max_dd, (peak - v) / peak)
    win = sum(1 for t in trades if t.get("ret", 0) > 0)
    win_rate = win / len(trades) if trades else 0.0

    return {
        "total_ret": float(total_ret),
        "annual_ret": float(ann),
        "sharpe": float(sharpe),
        "max_dd": float(max_dd),
        "win_rate": float(win_rate),
        "n_trades": len(trades),
        "final": float(cash),
        "years": float(years),
        "start": str(dates[0])[:10],
        "end": str(dates[-1])[:10],
    }


def buyhold(df):
    c = df["close"].tolist()
    if not c or c[0] <= 0:
        return None
    ann = (c[-1] / c[0]) ** (252.0 / len(c)) - 1
    return {"total": (c[-1] - c[0]) / c[0], "annual": float(ann)}


# ============================================================
# 主程序
# ============================================================
def main():
    print("=" * 64)
    print("  MA20+MACD 策略  ·  长周期回测  ·  2026-04-17")
    print("=" * 64)

    etfs = [
        {"name": "沪深300ETF",   "code": "510300"},
        {"name": "中证500ETF",   "code": "510500"},
        {"name": "创业板ETF",    "code": "159915"},
        {"name": "中证1000ETF", "code": "512100"},
        {"name": "纳指ETF",      "code": "513100"},
        {"name": "恒生ETF",      "code": "513660"},
        {"name": "黄金ETF",      "code": "518880"},
        {"name": "上证50ETF",    "code": "510050"},
    ]

    benchmarks = [
        {"name": "沪深300指数", "code": "000300"},
        {"name": "中证500指数", "code": "000905"},
        {"name": "上证指数",    "code": "000001"},
        {"name": "创业板指",    "code": "399006"},
    ]

    param_sets = [
        {"ma": 15, "mf": 12, "ms": 26, "sig": 9,  "label": "MA15+MACD(12,26,9)"},
        {"ma": 20, "mf": 12, "ms": 26, "sig": 9,  "label": "MA20+MACD(12,26,9)"},
        {"ma": 25, "mf": 12, "ms": 26, "sig": 9,  "label": "MA25+MACD(12,26,9)"},
        {"ma": 20, "mf": 8,  "ms": 22, "sig": 6,  "label": "MA20+MACD(8,22,6)"},
        {"ma": 30, "mf": 12, "ms": 26, "sig": 9,  "label": "MA30+MACD(12,26,9)"},
        {"ma": 20, "mf": 6,  "ms": 13, "sig": 5,  "label": "MA20+MACD(6,13,5)"},
    ]

    # ---- 数据获取 ----
    print("\n[Step 1/4] 获取ETF历史数据（Sina接口）...")
    etf_data = {}
    for e in etfs:
        sys.stdout.write(f"  {e['name']}({e['code']})... ")
        sys.stdout.flush()
        df = fetch_etf_sina(e["code"])
        if df is not None and len(df) > 100:
            etf_data[e["code"]] = df
            print(f"OK  {len(df)}条 {str(df['date'].min())[:10]}~{str(df['date'].max())[:10]}")
        else:
            print(f"FAIL")

    print("\n[Step 2/4] 获取指数历史数据（akshare东方财富）...")
    idx_data = {}
    for b in benchmarks:
        sys.stdout.write(f"  {b['name']}({b['code']})... ")
        sys.stdout.flush()
        df = fetch_index_em(b["code"])
        if df is not None and len(df) > 100:
            idx_data[b["code"]] = df
            print(f"OK  {len(df)}条 {str(df['date'].min())[:10]}~{str(df['date'].max())[:10]}")
        else:
            print("FAIL")

    if not etf_data and not idx_data:
        print("ERROR: no data!")
        return

    # 对齐共同区间
    all_data = dict(etf_data)
    all_data.update(idx_data)
    starts = [df["date"].min() for df in all_data.values()]
    ends = [df["date"].max() for df in all_data.values()]
    cs = max(starts)
    ce = min(ends)
    aligned = {}
    for code, df in all_data.items():
        df2 = df[(df["date"] >= cs) & (df["date"] <= ce)].reset_index(drop=True)
        aligned[code] = df2

    years_span = (ce - cs).days / 365.25
    print(f"\n  共同区间: {str(cs)[:10]} ~ {str(ce)[:10]}  ({years_span:.1f}年)")

    # ---- 回测 ----
    print(f"\n[Step 3/4] 运行策略回测...")
    all_results = []
    best = None
    best_score = -999.0

    for e in etfs:
        code = e["code"]
        if code not in aligned:
            continue
        df = aligned[code]
        bm = buyhold(df)
        bm_ann = bm["annual"] if bm else 0.0
        closes = df["close"].tolist()

        for p in param_sets:
            sigs = gen_signals(closes, p["ma"], p["mf"], p["ms"], p["sig"])
            bt = run_bt(df, sigs)
            score = bt["annual_ret"] - 0.5 * bt["max_dd"]
            diff_bm = bt["annual_ret"] - bm_ann

            r = {
                "etf_name": e["name"], "code": code,
                "label": p["label"],
                "ma": p["ma"], "mf": p["mf"], "ms": p["ms"], "sig": p["sig"],
                "annual": bt["annual_ret"], "total": bt["total_ret"],
                "sharpe": bt["sharpe"], "max_dd": bt["max_dd"],
                "win_rate": bt["win_rate"], "n_trades": bt["n_trades"],
                "years": bt["years"], "start": bt["start"], "end": bt["end"],
                "bm_annual": bm_ann, "diff_bm": diff_bm, "score": score,
            }
            all_results.append(r)
            if score > best_score:
                best_score = score
                best = r

    # 基准
    print(f"\n[Step 4/4] Buy&Hold基准对比...")
    bm_results = {}
    for b in benchmarks:
        code = b["code"]
        if code in aligned:
            bm = buyhold(aligned[code])
            bm_results[b["name"]] = {"annual": bm["annual"], "total": bm["total"]}

    # ---- 输出 ----
    all_results.sort(key=lambda x: x["score"], reverse=True)

    print("\n" + "=" * 64)
    print("  【一】全部回测结果（按综合评分排序）")
    print("=" * 64)
    prev = None
    for r in all_results:
        if r["etf_name"] != prev:
            print(f"\n  === {r['etf_name']} ({r['years']:.1f}年) ===")
            prev = r["etf_name"]
        star = " <<<BEST" if r is best else ""
        print(f"    {r['label']}{star}")
        print(f"    总收益 {r['total']*100:+6.1f}%  年化 {r['annual']*100:+6.1f}%  "
              f"夏普{r['sharpe']:.2f}  DD{r['max_dd']*100:5.1f}%  "
              f"胜率{r['win_rate']*100:4.0f}%  交易{r['n_trades']:3d}次")

    print("\n" + "=" * 64)
    print("  【二】Buy&Hold 基准（共同区间）")
    print("=" * 64)
    for name, bm in sorted(bm_results.items(), key=lambda x: x[1]["annual"], reverse=True):
        print(f"  {name:12s}  年化{bm['annual']*100:+6.1f}%  总收益{bm['total']*100:+7.1f}%")

    print("\n" + "=" * 64)
    print("  【三】最优参数推荐")
    print("=" * 64)
    if best:
        print(f"  标的:     {best['etf_name']} ({best['code']})")
        print(f"  参数:     {best['label']}")
        print(f"  回测期:   {best['start']} ~ {best['end']} ({best['years']:.1f}年)")
        print(f"  总收益:   {best['total']*100:+.1f}%")
        print(f"  年化收益: {best['annual']*100:+.1f}%")
        print(f"  夏普比率: {best['sharpe']:.2f}")
        print(f"  最大回撤: {best['max_dd']*100:.1f}%")
        print(f"  胜率:     {best['win_rate']*100:.0f}%")
        print(f"  交易次数: {best['n_trades']}次")
        print(f"  vs基准年化: {best['bm_annual']*100:+6.1f}%  超额: {best['diff_bm']*100:+6.1f}%")

    # 优化分析
    print("\n" + "=" * 64)
    print("  【四】策略优化建议")
    print("=" * 64)

    def avg(lst, key):
        if not lst:
            return None
        return sum(x[key] for x in lst) / len(lst)

    print("\n  1. MA周期对比:")
    for ma_v, label in [(15, "MA15"), (20, "MA20"), (25, "MA25"), (30, "MA30")]:
        grp = [r for r in all_results if r["ma"] == ma_v]
        if grp:
            a = avg(grp, "annual")
            d = avg(grp, "max_dd")
            s = avg(grp, "score")
            b = avg(grp, "bm_annual")
            diff = avg(grp, "diff_bm")
            print(f"    {label:6s}  年化{a*100:+6.1f}%  vs基准{b*100:+6.1f}% 超额{diff*100:+5.1f}%  "
                  f"DD{d*100:5.1f}%  评分{s:.3f}")

    print("\n  2. MACD参数对比:")
    for lbl, mf, ms, sg in [
        ("标准MACD(12,26,9)", 12, 26, 9),
        ("快速MACD(8,22,6)", 8, 22, 6),
        ("更快MACD(6,13,5)", 6, 13, 5),
    ]:
        grp = [r for r in all_results if r["mf"] == mf and r["ms"] == ms and r["sig"] == sg]
        if grp:
            a = avg(grp, "annual")
            d = avg(grp, "max_dd")
            s = avg(grp, "score")
            print(f"    {lbl:22s}  年化{a*100:+6.1f}%  DD{d*100:5.1f}%  评分{s:.3f}")

    print("\n  3. ETF品类对比（MA20基准参数）:")
    ma20 = [r for r in all_results if r["ma"] == 20 and r["mf"] == 12 and r["ms"] == 26 and r["sig"] == 9]
    for name, grp in sorted({r["etf_name"]: [r for r in ma20 if r["etf_name"] == r["etf_name"]]
                             for r in ma20}.items(),
                             key=lambda x: avg(x[1], "annual") or 0, reverse=True):
        a = avg(grp, "annual")
        d = avg(grp, "max_dd")
        b = avg(grp, "bm_annual")
        diff = avg(grp, "diff_bm")
        print(f"    {name:10s}  年化{a*100:+6.1f}%  DD{d*100:5.1f}%  vs基准{diff*100:+5.1f}%")

    # 保存
    out = {
        "run_date": "2026-04-17",
        "common_start": str(cs)[:10],
        "common_end": str(ce)[:10],
        "years": round(years_span, 1),
        "best": best,
        "benchmark": {k: {"annual": float(v["annual"]), "total": float(v["total"])} for k, v in bm_results.items()},
        "all_results": all_results,
    }
    out_path = "D:/QClaw_Trading/scripts/backtest/backtest_result_2026-04-17.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
