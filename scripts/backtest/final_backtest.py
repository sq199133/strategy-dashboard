# -*- coding: utf-8 -*-
"""
MA20+MACD 策略回测 - 纯净版
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
def get_etf_sina(code, start="2012-01-01", end="2026-04-17"):
    try:
        sym = ("sh" + code) if code.startswith(("1","5","6","9")) else ("sz" + code)
        df = ak.fund_etf_hist_sina(symbol=sym)
        if df is None or len(df) < 50:
            return None
        df.columns = [c.strip() for c in df.columns]
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df = df[(df["date"] >= start) & (df["date"] <= end)]
        for col in ["open","close","high","low","volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.dropna(subset=["close"]).reset_index(drop=True)
    except Exception:
        return None

def get_index_em(code, start="2005-01-01", end="2026-04-17"):
    try:
        sym = ("sh" + code) if code.startswith("0") else ("sz" + code)
        df = ak.stock_zh_index_daily(symbol=sym)
        if df is None or len(df) < 50:
            return None
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df = df[(df["date"] >= start) & (df["date"] <= end)]
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        return df[["date","close"]].dropna().reset_index(drop=True)
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
        price = float(closes[i])
        ma_val = sum(closes[i - ma + 1:i + 1]) / ma
        res = calc_macd(closes[:i + 1], mf, ms, sig)
        if res[0] is None:
            continue
        m0, s0, h0 = res[0][-1], res[1][-1], res[2][-1]
        m1, s1, h1 = res[0][-2], res[1][-2], res[2][-2]
        above_ma = price > ma_val
        ma_vals = [sum(closes[i - j - ma + 1:i - j + 1]) / ma for j in range(3)]
        ma_ok = ma_vals[0] >= min(ma_vals) - 0.001
        golden = bool((m1 <= s1) and (m0 > s0))
        above_zero = bool(m0 > 0)
        red_ok = bool((h1 > 0) and (h0 >= h1 * 0.8))
        buy = bool(above_ma and ma_ok and (golden or (above_zero and red_ok)))
        sell = bool((price < ma_val) or ((m1 >= s1) and (m0 < s0)) or ((h1 > 0) and (h0 < 0)))
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
def run_bt(closes, dates, sigs, init=100000.0, stop=0.05):
    n = len(closes)
    cash = float(init)
    shares = 0
    pos = 0
    equity = []
    trades = []
    for i in range(n):
        price = float(closes[i])
        # 止损
        if pos == 1 and shares > 0 and trades:
            cost_basis = shares * trades[-1]["buy_price"]
            loss = (shares * price - cost_basis) / cost_basis
            if loss <= -stop:
                cash = cash + shares * price
                trades[-1]["sell_date"] = str(dates[i])[:10]
                trades[-1]["sell_price"] = price
                trades[-1]["ret"] = (price - trades[-1]["buy_price"]) / trades[-1]["buy_price"]
                trades[-1]["stop"] = True
                shares = 0
                pos = 0
        sig_val = sigs[i] if i < len(sigs) else 0
        if sig_val == 1 and pos == 0:
            bp = float(price)
            sh = int(cash / bp)
            cash = cash - (sh * bp)
            shares = sh
            pos = 1
            trades.append({"buy_date": str(dates[i])[:10], "buy_price": bp, "shares": sh})
        elif sig_val == -1 and pos == 1:
            cash = cash + shares * float(price)
            trades[-1]["sell_date"] = str(dates[i])[:10]
            trades[-1]["sell_price"] = float(price)
            trades[-1]["ret"] = (float(price) - trades[-1]["buy_price"]) / trades[-1]["buy_price"]
            shares = 0
            pos = 0
        equity.append(float(cash + shares * price))
    # 平仓
    if pos == 1 and shares > 0:
        cash = cash + shares * float(closes[-1])
        trades[-1]["sell_date"] = str(dates[-1])[:10]
        trades[-1]["sell_price"] = float(closes[-1])
        trades[-1]["ret"] = (float(closes[-1]) - trades[-1]["buy_price"]) / trades[-1]["buy_price"]
        shares = 0
        pos = 0
    eq = np.array(equity, dtype=np.float64)
    total_ret = (cash - init) / init
    rets = np.diff(eq) / eq[:-1]
    rets = rets[np.isfinite(rets)]
    years = max((dates[-1] - dates[0]).days / 365.25, 0.01)
    ann_ret = (cash / init) ** (1.0 / years) - 1
    sharpe = (rets.mean() / max(rets.std(), 1e-10)) * np.sqrt(252)
    peak = float(init)
    max_dd = 0.0
    for v in eq:
        peak = max(peak, v)
        max_dd = max(max_dd, (peak - v) / peak)
    win = sum(1 for t in trades if t.get("ret", 0) > 0)
    win_rate = win / len(trades) if trades else 0.0
    return {
        "total_ret": float(total_ret), "annual_ret": float(ann_ret),
        "sharpe": float(sharpe), "max_dd": float(max_dd),
        "win_rate": float(win_rate), "n_trades": len(trades),
        "final": float(cash), "years": float(years),
        "start": str(dates[0])[:10], "end": str(dates[-1])[:10],
        "equity": [float(e) for e in equity],
    }

def buyhold_ret(closes):
    c = [float(x) for x in closes]
    if not c or c[0] <= 0:
        return None
    return (c[-1] - c[0]) / c[0]

# ============================================================
# 主程序
# ============================================================
def main():
    print("=" * 60)
    print("  MA20+MACD策略回测  2026-04-17")
    print("=" * 60)

    etfs = [
        ("沪深300ETF", "510300"),
        ("中证500ETF", "510500"),
        ("创业板ETF", "159915"),
        ("中证1000ETF", "512100"),
        ("纳指ETF", "513100"),
        ("恒生ETF", "513660"),
        ("黄金ETF", "518880"),
        ("上证50ETF", "510050"),
    ]
    benchmarks = [
        ("沪深300指数", "000300"),
        ("中证500指数", "000905"),
        ("上证指数", "000001"),
        ("创业板指", "399006"),
    ]
    params = [
        (15, 12, 26, 9, "MA15+MACD(12,26,9)"),
        (20, 12, 26, 9, "MA20+MACD(12,26,9)"),
        (25, 12, 26, 9, "MA25+MACD(12,26,9)"),
        (20, 8,  22, 6, "MA20+MACD(8,22,6)"),
        (30, 12, 26, 9, "MA30+MACD(12,26,9)"),
        (20, 6,  13, 5, "MA20+MACD(6,13,5)"),
    ]

    print("\n[1] 获取数据...")
    etf_data = {}
    for name, code in etfs:
        df = get_etf_sina(code)
        if df is not None:
            etf_data[code] = df
            print(f"  {name}({code}): {len(df)}条 {str(df['date'].min())[:10]}~{str(df['date'].max())[:10]}")
        else:
            print(f"  {name}({code}): FAIL")

    idx_data = {}
    for name, code in benchmarks:
        df = get_index_em(code)
        if df is not None:
            idx_data[code] = df
            print(f"  {name}({code}): {len(df)}条 {str(df['date'].min())[:10]}~{str(df['date'].max())[:10]}")
        else:
            print(f"  {name}({code}): FAIL")

    if not etf_data:
        print("ERROR: no ETF data!")
        return

    # 对齐：取所有ETF的共同日期范围（忽略交易日交集）
    all_starts = [df["date"].min() for df in etf_data.values()]
    all_ends = [df["date"].max() for df in etf_data.values()]
    cs = max(all_starts)  # 共同开始 = 最晚开始那只ETF的起点
    ce = min(all_ends)    # 共同结束 = 最早结束那只ETF的终点
    aligned = {}
    for code, df in etf_data.items():
        df2 = df[(df["date"] >= cs) & (df["date"] <= ce)].copy()
        df2 = df2.reset_index(drop=True)
        aligned[code] = df2

    years_span = (ce - cs).days / 365.25
    print(f"\n  共同区间: {str(cs)[:10]} ~ {str(ce)[:10]}  ({years_span:.1f}年)")

    print("\n[2] 回测中...")
    results = []
    for name, code in etfs:
        if code not in aligned:
            continue
        df = aligned[code]
        closes = df["close"].tolist()
        dates = df["date"].tolist()
        bm = buyhold_ret(closes)
        bm_ann = ((1 + bm) ** (1 / max(years_span, 0.01)) - 1) if bm else 0

        for ma, mf, ms, sig, label in params:
            sigs = gen_signals(closes, ma, mf, ms, sig)
            bt = run_bt(closes, dates, sigs)
            score = bt["annual_ret"] - 0.5 * bt["max_dd"]
            diff = bt["annual_ret"] - bm_ann
            results.append({
                "etf": name, "code": code, "label": label,
                "annual": bt["annual_ret"], "total": bt["total_ret"],
                "sharpe": bt["sharpe"], "max_dd": bt["max_dd"],
                "win_rate": bt["win_rate"], "n_trades": bt["n_trades"],
                "years": bt["years"], "bm_annual": bm_ann, "diff": diff,
                "score": score,
            })

    print(f"\n[3] 基准对比...")
    bm_results = {}
    for name, code in benchmarks:
        if code in idx_data:
            # 找对齐区间
            df_idx = idx_data[code]
            df_a = df_idx[(df_idx["date"] >= cs) & (df_idx["date"] <= ce)].reset_index(drop=True)
            if len(df_a) > 100:
                bm = buyhold_ret(df_a["close"].tolist())
                bm_ann = ((1 + bm) ** (1 / max(years_span, 0.01)) - 1) if bm else 0
                bm_results[name] = {"annual": bm_ann, "total": bm}
                print(f"  {name}: 年化{bm_ann*100:+.1f}% 总收益{bm*100:+.1f}%")

    results.sort(key=lambda x: x["score"], reverse=True)
    best = results[0] if results else None

    # ============================================================
    # 打印
    # ============================================================
    print("\n" + "=" * 60)
    print("  【一】全部回测结果")
    print("=" * 60)
    prev = None
    for r in results:
        if r["etf"] != prev:
            print(f"\n  == {r['etf']} ({r['years']:.1f}年) ==")
            prev = r["etf"]
        star = " <<<BEST" if r is best else ""
        print(f"    {r['label']}{star}")
        print(f"    总收益 {r['total']*100:+6.1f}%  年化 {r['annual']*100:+6.1f}%  "
              f"夏普{r['sharpe']:.2f}  DD{r['max_dd']*100:5.1f}%  "
              f"胜率{r['win_rate']*100:4.0f}%  交易{r['n_trades']:3d}次")

    print("\n" + "=" * 60)
    print("  【二】最优参数推荐")
    print("=" * 60)
    if best:
        print(f"  标的:     {best['etf']} ({best['code']})")
        print(f"  参数:     {best['label']}")
        print(f"  回测期:   {best['start']} ~ {best['end']} ({best['years']:.1f}年)")
        print(f"  总收益:   {best['total']*100:+.1f}%")
        print(f"  年化收益: {best['annual']*100:+.1f}%")
        print(f"  夏普比率: {best['sharpe']:.2f}")
        print(f"  最大回撤: {best['max_dd']*100:.1f}%")
        print(f"  胜率:     {best['win_rate']*100:.0f}%")
        print(f"  交易次数: {best['n_trades']}次")
        print(f"  vs基准年化 {best['bm_annual']*100:+6.1f}%  超额 {best['diff']*100:+6.1f}%")

    print("\n" + "=" * 60)
    print("  【三】策略优化建议")
    print("=" * 60)
    def avg(lst, k):
        if not lst: return None
        return sum(x[k] for x in lst) / len(lst)

    print("\n  MA周期对比:")
    for ma_v, lbl in [(15,"MA15"),(20,"MA20"),(25,"MA25"),(30,"MA30")]:
        g = [r for r in results if r["label"].startswith(lbl)]
        if g:
            a = avg(g,"annual"); d = avg(g,"max_dd"); s = avg(g,"score")
            b = avg(g,"bm_annual"); dx = avg(g,"diff")
            print(f"    {lbl}: 年化{a*100:+6.1f}% vs基准{b*100:+6.1f}% 超额{dx*100:+5.1f}% DD{d*100:5.1f}% 评分{s:.3f}")

    print("\n  MACD参数对比:")
    for mf,ms,sg,lbl in [(12,26,9,"标准(12,26,9)"),(8,22,6,"快速(8,22,6)"),(6,13,5,"更快(6,13,5)")]:
        g = [r for r in results if f"({mf},{ms},{sg})" in r["label"]]
        if g:
            a = avg(g,"annual"); d = avg(g,"max_dd"); s = avg(g,"score")
            print(f"    {lbl}: 年化{a*100:+6.1f}% DD{d*100:5.1f}% 评分{s:.3f}")

    print("\n  ETF品类对比（MA20基准）:")
    g = [r for r in results if "MA20+MACD(12,26,9)" == r["label"]]
    for name, grp in sorted({r["etf"]: [r] for r in g}.items(), key=lambda x: avg(x[1],"annual") or 0, reverse=True):
        a = avg(grp,"annual"); d = avg(grp,"max_dd"); b = avg(grp,"bm_annual"); dx = avg(grp,"diff")
        if a is not None:
            bar = "".join("=" * max(0, int(a * 200)) for _ in [1])
            print(f"    {name:10s} {a*100:+6.1f}% DD{d*100:5.1f}% vs基准{dx*100:+5.1f}% {bar}")

    # 保存
    out = {
        "run_date": "2026-04-17",
        "common_start": str(cs)[:10],
        "common_end": str(ce)[:10],
        "years": round(years_span, 1),
        "best": best,
        "benchmark": {k: {"annual": float(v["annual"]), "total": float(v["total"])} for k, v in bm_results.items()},
        "all_results": results,
    }
    out_path = "D:/QClaw_Trading/scripts/backtest/backtest_result_2026-04-17.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out_path}")

if __name__ == "__main__":
    main()
