# -*- coding: utf-8 -*-
"""
MA20+MACD 20年回测 - 腾讯行情API获取ETF历史数据
"""
import sys
import json
import time
import urllib.request
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

PYTHON = "D:/Python312/python.exe"

# ============================================================
# 腾讯API获取ETF日K（Node.js腾讯API分片抓取逻辑，用Python重写）
# ============================================================
def fetch_tencent_kline(code, market="SZ"):
    """通过腾讯行情API获取ETF历史K线（前复权）"""
    prefix = "sh" if market == "SH" else "sz"
    sym = prefix + code
    all_data = []
    # 腾讯API每次最多返回约700条，我们循环获取直到数据少于500条（已有足够历史）
    page_size = 600
    end_str = ""
    retry = 3

    for _ in range(retry):
        url = (
            f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            f"?_var=kline_dayqfq&param={sym},day,,,{page_size},qfq{','+end_str if end_str else ''}"
        )
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://gu.qq.com"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
        except Exception:
            time.sleep(1)
            continue

        try:
            json_str = raw[raw.index("=") + 1:]
            data = json.loads(json_str)
        except Exception:
            break

        fund_data = data.get("data", {}).get(sym, {})
        if not fund_data:
            break

        qfqday = fund_data.get("qfqday", [])
        day = fund_data.get("day", [])
        records = qfqday if qfqday else day

        if not records:
            break

        all_data.extend(records)

        if len(records) < page_size:
            break
        end_str = records[0][0]
        time.sleep(0.2)

    if not all_data:
        return None

    # 解析数据: [日期, 开, 收, 高, 低, 成交量, 涨跌额, 涨跌幅, ...]
    rows = []
    for r in all_data:
        if len(r) < 6:
            continue
        try:
            date_str = r[0]
            close = float(r[2])
            open_p = float(r[1])
            high = float(r[3])
            low = float(r[4])
            vol = float(r[5]) if len(r) > 5 else 0
            rows.append({
                "date": pd.to_datetime(date_str),
                "open": open_p,
                "close": close,
                "high": high,
                "low": low,
                "volume": vol,
            })
        except Exception:
            continue

    if not rows:
        return None

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    return df


def fetch_index_data(code, start="2005-01-01", end="2026-04-17"):
    """获取指数历史数据（用akshare的东方财富接口）"""
    try:
        import akshare as ak
        sym = ("sh" + code) if code.startswith("0") else ("sz" + code)
        df = ak.stock_zh_index_daily(symbol=sym)
        if df is None or len(df) < 50:
            return None
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df = df[(df["date"] >= start) & (df["date"] <= end)]
        return df[["date", "close"]].reset_index(drop=True)
    except Exception:
        return None


# ============================================================
# 指标
# ============================================================
def ema(data, period):
    k = 2.0 / (period + 1)
    r = [float(data[0])]
    for v in data[1:]:
        r.append(float(v) * k + r[-1] * (1 - k))
    return r


def macd_vals(closes, mf=12, ms=26, sig=9):
    if len(closes) < ms + sig + 5:
        return None, None, None
    ef = ema(closes, mf)
    es = ema(closes, ms)
    mline = [ef[i] - es[i] for i in range(len(closes))]
    sline = ema(mline, sig)
    hist = [mline[i] - sline[i] for i in range(len(mline))]
    return mline, sline, hist


# ============================================================
# 策略信号
# ============================================================
def signals(closes, ma=20, mf=12, ms=26, sig=9):
    n = len(closes)
    out = [0] * n
    pos = 0
    warmup = max(ma + 3, ms + sig + 3)

    for i in range(warmup, n):
        price = closes[i]
        ma_val = sum(closes[i - ma + 1:i + 1]) / ma

        res = macd_vals(closes[:i + 1], mf, ms, sig)
        if res[0] is None:
            continue
        m0, s0, h0 = res[0][-1], res[1][-1], res[2][-1]
        m1, s1, h1 = res[0][-2], res[1][-2], res[2][-2]

        above_ma = price > ma_val
        ma_up = sum(closes[i - ma + 1:i + 1]) / ma >= \
                min(sum(closes[i - j - ma + 1:i - j + 1]) / ma for j in range(3)) - 0.001

        golden = (m1 <= s1) and (m0 > s0)
        above_zero = m0 > 0
        red_ok = (h1 > 0) and (h0 >= h1 * 0.8)

        buy = above_ma and ma_up and (golden or (above_zero and red_ok))
        sell = (price < ma_val) or ((m1 >= s1) and (m0 < s0)) or ((h1 > 0) and (h0 < 0))

        if pos == 0 and buy:
            out[i] = 1
            pos = 1
        elif pos == 1 and sell:
            out[i] = -1
            pos = 0

    return out


# ============================================================
# 回测
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

        if pos == 1 and shares > 0 and trades:
            cost = shares * trades[-1]["buy_price"]
            loss = (shares * price - cost) / cost
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

    if pos == 1 and shares > 0:
        cash += shares * closes[-1]
        trades[-1]["sell_date"] = str(dates[-1])[:10]
        trades[-1]["sell_price"] = float(closes[-1])
        trades[-1]["ret"] = float((closes[-1] - trades[-1]["buy_price"]) / trades[-1]["buy_price"])
        shares = 0
        pos = 0

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
    if not c:
        return None
    return {"total": (c[-1] - c[0]) / c[0], "annual": (c[-1] / c[0]) ** (252.0 / len(c)) - 1}


# ============================================================
# 主程序
# ============================================================
def main():
    print("=" * 64)
    print("  MA20+MACD 策略  ·  20年回测  ·  2026-04-17")
    print("=" * 64)

    # ETF标的（代码 + 交易所）
    etfs = [
        {"name": "沪深300ETF",   "code": "510300", "mkt": "SH"},
        {"name": "中证500ETF",   "code": "510500", "mkt": "SH"},
        {"name": "创业板ETF",    "code": "159915", "mkt": "SZ"},
        {"name": "中证1000ETF",  "code": "512100", "mkt": "SH"},
        {"name": "纳指ETF",      "code": "513100", "mkt": "SH"},
        {"name": "恒生ETF",      "code": "513660", "mkt": "SH"},
        {"name": "黄金ETF",      "code": "518880", "mkt": "SH"},
        {"name": "上证50ETF",    "code": "510050", "mkt": "SH"},
    ]

    benchmarks = [
        {"name": "沪深300指数", "code": "000300"},
        {"name": "中证500指数", "code": "000905"},
        {"name": "上证指数",    "code": "000001"},
        {"name": "创业板指",    "code": "399006"},
    ]

    param_sets = [
        {"ma": 15, "mf": 12, "ms": 26, "sig": 9,  "label": "MA15+MACD(12,26,9)"},
        {"ma": 20, "mf": 12, "ms": 26, "sig": 9,  "label": "MA20+MACD(12,26,9) [基准]"},
        {"ma": 25, "mf": 12, "ms": 26, "sig": 9,  "label": "MA25+MACD(12,26,9)"},
        {"ma": 20, "mf": 8,  "ms": 22, "sig": 6,  "label": "MA20+MACD(8,22,6)"},
        {"ma": 30, "mf": 12, "ms": 26, "sig": 9,  "label": "MA30+MACD(12,26,9)"},
        {"ma": 20, "mf": 6,  "ms": 13, "sig": 5,  "label": "MA20+MACD(6,13,5)"},
    ]

    # ---- Step 1: 获取ETF数据 ----
    print("\n[Step 1/4] 获取ETF历史数据（腾讯API）...")
    etf_data = {}
    for e in etfs:
        sys.stdout.write(f"  {e['name']}({e['code']})... ")
        sys.stdout.flush()
        df = fetch_tencent_kline(e["code"], e["mkt"])
        if df is not None and len(df) > 100:
            etf_data[e["code"]] = df
            print(f"OK  {len(df)}条 {str(df['date'].min())[:10]}~{str(df['date'].max())[:10]}")
        else:
            print(f"FAIL ({len(df) if df else 0}条)")

    # ---- Step 2: 获取指数数据 ----
    print("\n[Step 2/4] 获取指数历史数据（akshare）...")
    idx_data = {}
    for b in benchmarks:
        sys.stdout.write(f"  {b['name']}({b['code']})... ")
        sys.stdout.flush()
        df = fetch_index_data(b["code"])
        if df is not None and len(df) > 100:
            idx_data[b["code"]] = df
            print(f"OK  {len(df)}条 {str(df['date'].min())[:10]}~{str(df['date'].max())[:10]}")
        else:
            print("FAIL")

    if not etf_data and not idx_data:
        print("ERROR: No data loaded!")
        return

    # 对齐共同区间
    all_data = dict(etf_data)
    for code, df in idx_data.items():
        all_data[code] = df

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

    # ---- Step 3: 运行回测 ----
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
            sigs = signals(closes, p["ma"], p["mf"], p["ms"], p["sig"])
            bt = run_bt(df, sigs)
            score = bt["annual_ret"] - 0.5 * bt["max_dd"]
            diff_bm = bt["annual_ret"] - bm_ann

            r = {
                "etf_name": e["name"],
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
                "start": bt["start"],
                "end": bt["end"],
            }
            all_results.append(r)
            if score > best_score:
                best_score = score
                best = r

    # ---- Step 4: 基准 ----
    print(f"\n[Step 4/4] Buy&Hold基准对比...")
    bm_results = {}
    for b in benchmarks:
        code = b["code"]
        if code in aligned:
            bm = buyhold(aligned[code])
            bm_results[b["name"]] = {"annual": bm["annual"], "total": bm["total"]}

    # ============================================================
    # 打印结果
    # ============================================================
    all_results.sort(key=lambda x: x["score"], reverse=True)

    print("\n" + "=" * 64)
    print("  【一】全部回测结果（按综合评分排序）")
    print("=" * 64)
    prev = None
    for r in all_results:
        sep = ("" if r["etf_name"] == prev else f"\n  === {r['etf_name']} ===")
        prev = r["etf_name"]
        star = " <<<" if r is best else ""
        print(f"{sep}")
        print(f"    {r['label']}{star}")
        print(f"    总收益 {r['total']*100:+6.1f}%  年化 {r['annual']*100:+6.1f}%  "
              f"夏普 {r['sharpe']:.2f}  最大DD {r['max_dd']*100:5.1f}%  "
              f"胜率 {r['win_rate']*100:4.0f}%  交易 {r['n_trades']:3d}次")

    print("\n" + "=" * 64)
    print("  【二】Buy&Hold 基准（共同区间内）")
    print("=" * 64)
    for name, bm in sorted(bm_results.items(), key=lambda x: x[1]["annual"], reverse=True):
        print(f"  {name:12s}  年化 {bm['annual']*100:+6.1f}%  总收益 {bm['total']*100:+7.1f}%")

    # ---- 最优推荐 ----
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
        print(f"  vs BuyHold年化 {best['bm_annual']*100:+6.1f}%  超额 {best['diff_bm']*100:+6.1f}%")

    # ---- 策略对比 ----
    print("\n" + "=" * 64)
    print("  【四】策略优化建议")
    print("=" * 64)

    def avg_results(lst, key):
        if not lst:
            return None
        return sum(x[key] for x in lst) / len(lst)

    print("\n  MA周期对比（按ETF平均）:")
    for ma_label, ma_val in [("MA15", 15), ("MA20", 20), ("MA25", 25), ("MA30", 30)]:
        grp = [r for r in all_results if f"MA{ma_val}+" in r["label"] and "(基准" not in r["label"]]
        if grp:
            a = avg_results(grp, "annual")
            d = avg_results(grp, "max_dd")
            s = avg_results(grp, "score")
            bm = avg_results(grp, "bm_annual")
            diff = avg_results(grp, "diff_bm")
            print(f"    {ma_label}: 年化{a*100:+6.1f}% vs基准{bm*100:+6.1f}% 超额{diff*100:+5.1f}%  "
                  f"DD{d*100:5.1f}% 夏普{s:.3f}")

    print("\n  MACD参数对比:")
    for lbl, mf, ms, sg in [
        ("标准MACD(12,26,9)", 12, 26, 9),
        ("快MACD(8,22,6)", 8, 22, 6),
        ("更快MACD(6,13,5)", 6, 13, 5),
    ]:
        grp = [r for r in all_results
               if f"({mf},{ms},{sg})" in r["label"] and "(基准" not in r["label"]]
        if grp:
            a = avg_results(grp, "annual")
            d = avg_results(grp, "max_dd")
            s = avg_results(grp, "score")
            print(f"    {lbl}: 年化{a*100:+6.1f}% DD{d*100:5.1f}% 评分{s:.3f}")

    print("\n  ETF品类对比（MA20基准参数）:")
    ma20_grp = [r for r in all_results
                if "MA20+" in r["label"] and "(基准" not in r["label"]]
    ma20_by_etf = {}
    for r in ma20_grp:
        if r["etf_name"] not in ma20_by_etf:
            ma20_by_etf[r["etf_name"]] = []
        ma20_by_etf[r["etf_name"]].append(r)
    for name, grp in sorted(ma20_by_etf.items(), key=lambda x: avg_results(x[1], "annual") or 0, reverse=True):
        a = avg_results(grp, "annual")
        d = avg_results(grp, "max_dd")
        bm = avg_results(grp, "bm_annual")
        diff = avg_results(grp, "diff_bm")
        bar = "●" * int(max(0, a * 100 + 5))
        bar2 = "○" * int(max(0, -a * 100 + 5))
        sign = "+" if a > 0 else ""
        print(f"    {name:10s} {sign}{a*100:5.1f}% DD{d*100:5.1f}% vs基准{diff*100:+5.1f}% {bar}")

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
