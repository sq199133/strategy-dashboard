# -*- coding: utf-8 -*-
"""
MA20 + MACD 策略 20年回测引擎
"""
import sys
import json
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import akshare as ak

# ============================================================
# 数据获取
# ============================================================
def fetch_etf(code, start="20050101", end="20260417"):
    """获取ETF日K（前复权）"""
    try:
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start[:4] + "-" + start[4:6] + "-" + start[6:],
            end_date=end[:4] + "-" + end[4:6] + "-" + end[6:],
            adjust="qfq"
        )
        if df is None or len(df) < 50:
            return None
        df.columns = [c.strip() for c in df.columns]
        df = df.rename(columns={
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume"
        })
        df["date"] = pd.to_datetime(df["date"])
        return df[["date", "open", "high", "low", "close", "volume"]].dropna()
    except Exception:
        return None


def fetch_index(code, start="20050101", end="20260417"):
    """获取A股指数日K"""
    try:
        sym = ("sh" + code) if code.startswith("0") else ("sz" + code)
        df = ak.stock_zh_index_daily(symbol=sym)
        if df is None or len(df) < 50:
            return None
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        s = pd.to_datetime(start[:4] + "-" + start[4:6] + "-" + start[6:])
        e = pd.to_datetime(end[:4] + "-" + end[4:6] + "-" + end[6:])
        return df[(df["date"] >= s) & (df["date"] <= e)][["date", "close"]].reset_index(drop=True)
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


def calc_macd(closes, fast=12, slow=26, sig=9):
    if len(closes) < slow + sig + 5:
        return None, None, None
    ef = calc_ema(closes, fast)
    es = calc_ema(closes, slow)
    mline = [ef[i] - es[i] for i in range(len(closes))]
    sline = calc_ema(mline, sig)
    hist = [mline[i] - sline[i] for i in range(len(mline))]
    return mline, sline, hist


# ============================================================
# 策略信号
# ============================================================
def gen_signals(closes, ma_period=20, mf=12, ms=26, sig=9):
    n = len(closes)
    signals = [0] * n
    pos = 0
    warmup = max(ma_period + 3, ms + sig + 3)

    for i in range(warmup, n):
        price = closes[i]
        ma_val = sum(closes[i - ma_period + 1:i + 1]) / ma_period

        m, s, h = calc_macd(closes[:i + 1], mf, ms, sig)
        if m is None:
            continue

        # 当前 + 前一根
        m0, s0, h0 = m[-1], s[-1], h[-1]
        m1, s1, h1 = m[-2], s[-2], h[-2]

        above_ma = price > ma_val
        ma_ok = sum(closes[i - ma_period + 1:i + 1]) / ma_period >= \
                min(sum(closes[i - j - ma_period + 1:i - j + 1]) / ma_period for j in range(3)) - 0.001

        golden = (m1 <= s1) and (m0 > s0)
        above_zero = m0 > 0
        red_ok = (h1 > 0) and (h0 >= h1 * 0.8)

        buy = above_ma and ma_ok and (golden or (above_zero and red_ok))
        sell = (price < ma_val) or ((m1 >= s1) and (m0 < s0)) or ((h1 > 0) and (h0 < 0))

        if pos == 0 and buy:
            signals[i] = 1
            pos = 1
        elif pos == 1 and sell:
            signals[i] = -1
            pos = 0

    return signals


# ============================================================
# 回测
# ============================================================
def backtest(df, signals, init=100000.0, stop=0.05):
    closes = df["close"].tolist()
    dates = df["date"].tolist()
    n = len(closes)

    cash = float(init)
    shares = 0
    pos = 0
    equity = []
    trades = []
    peak = float(init)

    for i in range(n):
        price = closes[i]

        # 止损
        if pos == 1 and shares > 0 and len(trades) > 0:
            cost = shares * trades[-1]["buy_price"]
            loss = (shares * price - cost) / cost
            if loss <= -stop:
                cash += shares * price
                trades[-1]["sell_date"] = str(dates[i])[:10]
                trades[-1]["sell_price"] = price
                trades[-1]["ret"] = float((price - trades[-1]["buy_price"]) / trades[-1]["buy_price"])
                trades[-1]["stop"] = True
                shares = 0
                pos = 0

        sig = signals[i]
        if sig == 1 and pos == 0:
            bp = float(price)
            sh = int(cash / bp)
            cost = sh * bp
            cash -= cost
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
        peak = max(peak, equity[-1])

    # 平仓
    if pos == 1 and shares > 0:
        cash += shares * closes[-1]
        trades[-1]["sell_date"] = str(dates[-1])[:10]
        trades[-1]["sell_price"] = float(closes[-1])
        trades[-1]["ret"] = float((closes[-1] - trades[-1]["buy_price"]) / trades[-1]["buy_price"])
        shares = 0
        pos = 0

    # 绩效
    equity_arr = np.array(equity, dtype=np.float64)
    total_ret = (cash - init) / init
    rets = np.diff(equity_arr) / equity_arr[:-1]
    rets = rets[np.isfinite(rets)]
    years = max((dates[-1] - dates[0]).days / 365.25, 0.01)
    ann_ret = (cash / init) ** (1.0 / years) - 1
    sharpe = (rets.mean() / max(rets.std(), 1e-10)) * np.sqrt(252)
    max_dd = 0.0
    pk = float(init)
    for v in equity_arr:
        pk = max(pk, v)
        dd = (pk - v) / pk
        max_dd = max(max_dd, dd)
    win = sum(1 for t in trades if t.get("ret", 0) > 0)
    win_rate = win / len(trades) if trades else 0.0

    return {
        "total_ret": float(total_ret),
        "annual_ret": float(ann_ret),
        "sharpe": float(sharpe),
        "max_dd": float(max_dd),
        "win_rate": float(win_rate),
        "n_trades": len(trades),
        "final": float(cash),
        "equity": [float(e) for e in equity],
        "years": float(years),
        "start": str(dates[0])[:10],
        "end": str(dates[-1])[:10],
    }


def buyhold(df):
    c = df["close"].tolist()
    if not c:
        return None
    ann = (c[-1] / c[0]) ** (252.0 / len(c)) - 1
    return {"total": (c[-1] - c[0]) / c[0], "annual": float(ann)}


# ============================================================
# 主程序
# ============================================================
def main():
    print("=" * 64)
    print("  MA20+MACD策略  ·  20年回测  ·  2026-04-17")
    print("=" * 64)

    # ETF标的
    etfs = [
        {"name": "沪深300ETF",  "code": "510300"},
        {"name": "中证500ETF",  "code": "510500"},
        {"name": "创业板ETF",   "code": "159915"},
        {"name": "纳指ETF",    "code": "513100"},
        {"name": "恒生ETF",    "code": "513660"},
        {"name": "黄金ETF",    "code": "518880"},
        {"name": "中证1000ETF", "code": "512100"},
    ]

    # 基准
    benchmarks = [
        {"name": "沪深300指数", "code": "000300"},
        {"name": "中证500指数", "code": "000905"},
        {"name": "上证指数",    "code": "000001"},
        {"name": "创业板指",    "code": "399006"},
    ]

    # 参数组合
    param_sets = [
        {"ma": 15, "mf": 12, "ms": 26, "sig": 9,  "label": "MA15+MACD(12,26,9)"},
        {"ma": 20, "mf": 12, "ms": 26, "sig": 9,  "label": "MA20+MACD(12,26,9) [基准]"},
        {"ma": 25, "mf": 12, "ms": 26, "sig": 9,  "label": "MA25+MACD(12,26,9)"},
        {"ma": 20, "mf": 8,  "ms": 22, "sig": 6,  "label": "MA20+MACD(8,22,6)"},
        {"ma": 30, "mf": 12, "ms": 26, "sig": 9,  "label": "MA30+MACD(12,26,9)"},
        {"ma": 20, "mf": 6,  "ms": 13, "sig": 5,  "label": "MA20+MACD(6,13,5)"},
    ]

    # ---- 数据获取 ----
    print("\n[Step 1/4] 获取数据...")
    data = {}
    for e in etfs:
        sys.stdout.write(f"  {e['name']}({e['code']})... ")
        sys.stdout.flush()
        df = fetch_etf(e["code"])
        if df is not None:
            data[e["code"]] = df
            print(f"OK  {len(df)}条 {str(df['date'].min())[:10]}~{str(df['date'].max())[:10]}")
        else:
            print("FAIL")

    for b in benchmarks:
        sys.stdout.write(f"  {b['name']}({b['code']})... ")
        sys.stdout.flush()
        df = fetch_index(b["code"])
        if df is not None:
            data[b["code"]] = df
            print(f"OK  {len(df)}条 {str(df['date'].min())[:10]}~{str(df['date'].max())[:10]}")
        else:
            print("FAIL")

    if not data:
        print("ERROR: no data loaded")
        return

    # 对齐到共同区间
    starts = [df["date"].min() for df in data.values()]
    ends = [df["date"].max() for df in data.values()]
    cs = max(starts)
    ce = min(ends)
    aligned = {}
    for code, df in data.items():
        df2 = df[(df["date"] >= cs) & (df["date"] <= ce)].reset_index(drop=True)
        aligned[code] = df2

    print(f"\n  共同区间: {str(cs)[:10]} ~ {str(ce)[:10]}")
    years_span = (ce - cs).days / 365.25
    print(f"  共 {years_span:.1f} 年交易日")

    # ---- 回测 ----
    print(f"\n[Step 2/4] 运行策略回测...")
    all_results = []
    best = None
    best_score = -999.0

    for etf in etfs:
        code = etf["code"]
        if code not in aligned:
            continue
        df = aligned[code]
        bm = buyhold(df)
        bm_ann = bm["annual"] if bm else 0.0
        closes = df["close"].tolist()

        for p in param_sets:
            sigs = gen_signals(closes, p["ma"], p["mf"], p["ms"], p["sig"])
            bt = backtest(df, sigs)

            # 综合评分：年化 - 0.5*最大回撤
            score = bt["annual_ret"] - 0.5 * bt["max_dd"]
            diff_bm = bt["annual_ret"] - bm_ann

            r = {
                "etf_name": etf["name"],
                "code": code,
                "label": p["label"],
                "annual": bt["annual_ret"],
                "total": bt["total_ret"],
                "sharpe": bt["sharpe"],
                "max_dd": bt["max_dd"],
                "win_rate": bt["win_rate"],
                "n_trades": bt["n_trades"],
                "years": bt["years"],
                "bm_annual": bm_ann,
                "diff_bm": diff_bm,
                "score": score,
            }
            all_results.append(r)

            if score > best_score:
                best_score = score
                best = r

    # ---- 基准 ----
    print(f"\n[Step 3/4] Buy&Hold 基准对比...")
    bm_results = {}
    for b in benchmarks:
        code = b["code"]
        if code in aligned:
            bm = buyhold(aligned[code])
            bm_results[b["name"]] = {"annual": bm["annual"], "total": bm["total"]}

    # ---- 打印结果 ----
    print("\n" + "=" * 64)
    print("  全部回测结果（按综合评分排序）")
    print("=" * 64)
    all_results.sort(key=lambda x: x["score"], reverse=True)

    prev_etf = None
    for r in all_results:
        sep = ("\n  --- " + r["etf_name"] + " ---") if r["etf_name"] != prev_etf else ""
        prev_etf = r["etf_name"]
        print(f"{sep}")
        star = " <<<" if r is best else ""
        print(f"    {r['label']}{star}")
        print(f"    总收益 {r['total']*100:+6.1f}%  年化 {r['annual']*100:+6.1f}%  "
              f"夏普 {r['sharpe']:.2f}  最大DD {r['max_dd']*100:5.1f}%  "
              f"胜率 {r['win_rate']*100:4.0f}%  交易 {r['n_trades']}次")

    print("\n" + "=" * 64)
    print("  Buy&Hold 基准")
    print("=" * 64)
    for name, bm in sorted(bm_results.items(), key=lambda x: x[1]["annual"], reverse=True):
        print(f"  {name:12s}  年化 {bm['annual']*100:+6.1f}%  总收益 {bm['total']*100:+7.1f}%")

    # ---- 最优推荐 ----
    if best:
        print("\n" + "=" * 64)
        print("  最优参数推荐")
        print("=" * 64)
        print(f"  标的: {best['etf_name']} ({best['code']})")
        print(f"  参数: {best['label']}")
        print(f"  回测期: {best.get('years',0):.1f}年 ({all_results[0]['start'] if all_results else 'N/A'}~{all_results[0]['end'] if all_results else 'N/A'})")
        print(f"  总收益:   {best['total']*100:+.1f}%")
        print(f"  年化收益: {best['annual']*100:+.1f}%")
        print(f"  夏普比率: {best['sharpe']:.2f}")
        print(f"  最大回撤: {best['max_dd']*100:.1f}%")
        print(f"  胜率:     {best['win_rate']*100:.0f}%")
        print(f"  交易次数: {best['n_trades']}次")
        bm_a = best.get("bm_annual", 0)
        diff = best.get("diff_bm", 0)
        print(f"  vs BuyHold年化 {bm_a*100:+6.1f}%  超额 {diff*100:+6.1f}%")

    # ---- 策略对比总结 ----
    print("\n" + "=" * 64)
    print("  策略优化建议")
    print("=" * 64)
    ma20_results = [r for r in all_results if "MA20" in r["label"] and "基准" not in r["label"]]
    ma15_results = [r for r in all_results if "MA15" in r["label"]]
    ma25_results = [r for r in all_results if "MA25" in r["label"]]
    ma30_results = [r for r in all_results if "MA30" in r["label"]]
    macd_short_results = [r for r in all_results if "(6,13,5)" in r["label"] or "(8,22,6)" in r["label"]]

    def avg(lst, key):
        if not lst:
            return None
        return sum(x[key] for x in lst) / len(lst)

    summary = [
        ("MA15 参数", ma15_results),
        ("MA20 参数", ma20_results),
        ("MA25 参数", ma25_results),
        ("MA30 参数", ma30_results),
        ("快MACD(6,13,5)/(8,22,6)", macd_short_results),
    ]
    for name, lst in summary:
        if lst:
            a = avg(lst, "annual")
            d = avg(lst, "max_dd")
            s = avg(lst, "score")
            print(f"  {name}: 年化{((a*100) if a else 'N/A'):+6.1f}%  平均DD{d*100 if d else 0:5.1f}%  "
                  f"评分{s:.3f}" if s else "  " + name + ": 数据不足")

    # ---- 保存 ----
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
