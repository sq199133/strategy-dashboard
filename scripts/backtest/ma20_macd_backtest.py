# -*- coding: utf-8 -*-
"""
20年回测引擎 - MA20 + MACD 策略
对比基准：沪深300、中证500、上证指数、创业板指
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
def get_etf_hist(code, start="20050101", end="20260417"):
    """获取ETF历史K线（前复权）"""
    try:
        sym = "sh" + code if code.startswith(("1", "5", "6", "9")) else "sz" + code
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start[:4] + "-" + start[4:6] + "-" + start[6:],
            end_date=end[:4] + "-" + end[4:6] + "-" + end[6:],
            adjust="qfq"
        )
        if df is None or len(df) < 100:
            return None
        df.columns = [c.strip() for c in df.columns]
        col_map = {
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume"
        }
        df = df.rename(columns=col_map)
        df["date"] = pd.to_datetime(df["date"])
        return df[["date", "open", "high", "low", "close", "volume"]].dropna()
    except Exception:
        return None


def get_index_hist(symbol_code, start="20050101", end="20260417"):
    """获取A股指数历史（前复权）"""
    try:
        sym = "sh" + symbol_code if symbol_code.startswith("0") else "sz" + symbol_code
        df = ak.stock_zh_index_daily(symbol=sym)
        if df is None or len(df) < 100:
            return None
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        start_d = pd.to_datetime(start[:4] + "-" + start[4:6] + "-" + start[6:])
        end_d = pd.to_datetime(end[:4] + "-" + end[4:6] + "-" + end[6:])
        df = df[(df["date"] >= start_d) & (df["date"] <= end_d)]
        return df[["date", "close"]].reset_index(drop=True)
    except Exception:
        return None


# ============================================================
# 指标计算
# ============================================================
def ema(data, period):
    k = 2.0 / (period + 1)
    result = [data[0]]
    for v in data[1:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def macd(closes, fast=12, slow=26, signal=9):
    if len(closes) < slow + signal + 5:
        return None, None, None
    ef = ema(closes, fast)
    es = ema(closes, slow)
    mline = [ef[i] - es[i] for i in range(len(closes))]
    sline = ema(mline, signal)
    hist = [mline[i] - sline[i] for i in range(len(mline))]
    return mline, sline, hist


# ============================================================
# 策略信号
# ============================================================
def gen_signals(df, ma_period=20, mf=12, ms=26, sig=9):
    """生成交易信号列表: 1=买入, -1=卖出, 0=持有/观望"""
    closes = df["close"].tolist()
    dates = df["date"].tolist()
    n = len(closes)
    result = [0] * n
    pos = 0
    min_idx = max(ma_period + 3, ms + sig + 3)

    for i in range(min_idx, n):
        price = closes[i]

        # MA20
        ma_val = sum(closes[i - ma_period + 1:i + 1]) / ma_period
        above_ma = price > ma_val

        # MA方向（近3日走平或向上）
        ma_3 = [sum(closes[i - j - ma_period + 1:i - j + 1]) / ma_period for j in range(3)]
        ma_ok = ma_3[0] >= min(ma_3) - 0.001

        # MACD
        mline, sline, hist = macd(closes[:i + 1], mf, ms, sig)
        if mline is None:
            continue

        m0, s0, h0 = mline[-1], sline[-1], hist[-1]
        m1, s1, h1 = mline[-2], sline[-2], hist[-2]

        # 金叉 & 零轴上
        golden = (m1 <= s1) and (m0 > s0)
        above_zero = m0 > 0
        red_ok = (h1 > 0) and (h0 >= h1 * 0.8)

        buy_cond = above_ma and ma_ok and (golden or (above_zero and red_ok))

        # 卖出
        below_ma = price < ma_val
        dead = (m1 >= s1) and (m0 < s0)
        red2green = (h1 > 0) and (h0 < 0)
        sell_cond = below_ma or dead or red2green

        if pos == 0 and buy_cond:
            result[i] = 1
            pos = 1
        elif pos == 1 and sell_cond:
            result[i] = -1
            pos = 0

    return result


# ============================================================
# 回测引擎
# ============================================================
def run_backtest(df, signals, init_cap=100000, stop_loss=0.05):
    """单标的回测，返回绩效指标"""
    closes = df["close"].tolist()
    dates = df["date"].tolist()
    n = len(closes)

    cash = init_cap
    shares = 0
    pos = 0
    trades = []
    equity = []
    peak = init_cap

    for i in range(n):
        price = closes[i]
        sig = signals[i]

        # 止损检查
        if pos == 1 and shares > 0 and len(trades) > 0:
            cost_basis = shares * trades[-1]["buy_price"]
            loss_pct = (shares * price - cost_basis) / cost_basis
            if loss_pct <= -stop_loss:
                cash += shares * price
                trades[-1]["sell_date"] = str(dates[i])[:10]
                trades[-1]["sell_price"] = price
                trades[-1]["stop_loss"] = True
                trades[-1]["ret"] = (price - trades[-1]["buy_price"]) / trades[-1]["buy_price"]
                shares = 0
                pos = 0

        if sig == 1 and pos == 0:
            bp = price
            sh = int(cash / bp)
            cost = sh * bp
            cash -= cost
            pos = 1
            trades.append({"buy_date": str(dates[i])[:10], "buy_price": bp, "shares": sh, "cost": cost})

        elif sig == -1 and pos == 1:
            cash += shares * price
            trades[-1]["sell_date"] = str(dates[i])[:10]
            trades[-1]["sell_price"] = price
            trades[-1]["ret"] = (price - trades[-1]["buy_price"]) / trades[-1]["buy_price"]
            shares = 0
            pos = 0

        equity.append(float(cash + shares * price))

    # 平仓
    if pos == 1 and shares > 0:
        cash += shares * closes[-1]
        trades[-1]["sell_date"] = str(dates[-1])[:10]
        trades[-1]["sell_price"] = closes[-1]
        trades[-1]["ret"] = (closes[-1] - trades[-1]["buy_price"]) / trades[-1]["buy_price"]
        shares = 0
        pos = 0

    # 绩效计算
    final_val = float(cash)
    equity_arr = np.array(equity, dtype=np.float64)
    total_ret = (final_val - init_cap) / init_cap

    rets = np.diff(equity_arr) / equity_arr[:-1]
    rets = rets[np.isfinite(rets)]

    years = max((dates[-1] - dates[0]).days / 365.25, 0.001)
    ann_ret = (final_val / init_cap) ** (1.0 / years) - 1

    if rets.std() > 1e-10:
        sharpe = (rets.mean() / rets.std()) * np.sqrt(252)
    else:
        sharpe = 0.0

    peak_v = init_cap
    max_dd = 0.0
    for v in equity_arr:
        peak_v = max(peak_v, v)
        dd = (peak_v - v) / peak_v
        max_dd = max(max_dd, dd)

    win_cnt = sum(1 for t in trades if t.get("ret", 0) > 0)
    win_rate = win_cnt / len(trades) if trades else 0.0

    return {
        "total_return": float(total_ret),
        "annual_return": float(ann_ret),
        "sharpe": float(sharpe),
        "max_drawdown": float(max_dd),
        "win_rate": float(win_rate),
        "n_trades": len(trades),
        "final_value": float(final_val),
        "years": float(years),
        "start": str(dates[0])[:10],
        "end": str(dates[-1])[:10],
        "equity": [float(e) for e in equity],
        "trades": [
            {k: float(v) if isinstance(v, (np.floating, np.integer)) else v
             for k, v in t.items()}
            for t in trades
        ]
    }


def buy_hold(df, init=1.0):
    """Buy&Hold 基准"""
    closes = df["close"].tolist()
    if not closes:
        return None
    return {
        "total": (closes[-1] - closes[0]) / closes[0],
        "annual": (closes[-1] / closes[0]) ** (252.0 / len(closes)) - 1,
        "dates": df["date"].tolist(),
        "closes": closes,
    }


# ============================================================
# 主程序
# ============================================================
def main():
    print("=" * 62)
    print("  MA20 + MACD 策略  ·  20年回测  ·  2026-04-17")
    print("=" * 62)

    # 标的定义
    ETF_LIST = [
        {"name": "沪深300ETF",   "code": "510300", "type": "etf"},
        {"name": "中证500ETF",   "code": "510500", "type": "etf"},
        {"name": "纳指ETF",      "code": "513100", "type": "etf"},
        {"name": "恒生ETF",      "code": "513660", "type": "etf"},
        {"name": "黄金ETF",      "code": "518880", "type": "etf"},
        {"name": "创业板ETF",    "code": "159915", "type": "etf"},
    ]
    BENCHMARKS = [
        {"name": "沪深300指数",  "code": "000300"},
        {"name": "中证500指数",  "code": "000905"},
        {"name": "上证指数",     "code": "000001"},
        {"name": "创业板指",    "code": "399006"},
    ]

    # 参数组合
    PARAMS = [
        {"ma": 15, "mf": 12, "ms": 26, "sig": 9,  "label": "MA15+MACD(12,26,9)"},
        {"ma": 20, "mf": 12, "ms": 26, "sig": 9,  "label": "MA20+MACD(12,26,9)"},
        {"ma": 25, "mf": 12, "ms": 26, "sig": 9,  "label": "MA25+MACD(12,26,9)"},
        {"ma": 20, "mf": 8,  "ms": 22, "sig": 6,  "label": "MA20+MACD(8,22,6)"},
        {"ma": 30, "mf": 12, "ms": 26, "sig": 9,  "label": "MA30+MACD(12,26,9)"},
        {"ma": 20, "mf": 6,  "ms": 13, "sig": 5,  "label": "MA20+MACD(6,13,5)"},
    ]

    # ---- 获取数据 ----
    print("\n[1/4] 获取数据...")
    data = {}
    for t in ETF_LIST:
        code = t["code"]
        print(f"  获取 {t['name']}({code}) ...", end=" ", flush=True)
        df = get_etf_hist(code)
        if df is not None:
            data[code] = df
            print(f"OK  {len(df)}条  {str(df['date'].min())[:10]}~{str(df['date'].max())[:10]}")
        else:
            print("FAIL")

    for t in BENCHMARKS:
        code = t["code"]
        print(f"  获取 {t['name']}({code}) ...", end=" ", flush=True)
        df = get_index_hist(code)
        if df is not None:
            data[code] = df
            print(f"OK  {len(df)}条  {str(df['date'].min())[:10]}~{str(df['date'].max())[:10]}")
        else:
            print("FAIL")

    if not data:
        print("ERROR: No data loaded")
        return

    # 确定共同时间区间
    all_starts = [df["date"].min() for df in data.values()]
    all_ends = [df["date"].max() for df in data.values()]
    common_start = max(all_starts)
    common_end = min(all_ends)
    print(f"\n  共同区间: {str(common_start)[:10]} ~ {str(common_end)[:10]}")

    # 对齐到共同区间
    aligned = {}
    for code, df in data.items():
        df2 = df[(df["date"] >= common_start) & (df["date"] <= common_end)].copy()
        df2 = df2.reset_index(drop=True)
        aligned[code] = df2

    # ---- 回测 ----
    print(f"\n[2/4] 运行策略回测 ({len(PARAMS)}套参数)...")
    results = []
    best = None
    best_score = -999

    for etf in ETF_LIST:
        code = etf["code"]
        if code not in aligned:
            continue
        df = aligned[code]
        bm = buy_hold(df)
        bm_ret = bm["annual"] if bm else 0

        for p in PARAMS:
            sigs = gen_signals(df, p["ma"], p["mf"], p["ms"], p["sig"])
            bt = run_backtest(df, sigs)

            # 综合评分 = 年化 - 0.5*最大回撤 (偏好高收益低回撤)
            score = bt["annual_return"] - 0.5 * bt["max_drawdown"]

            diff_bm = bt["annual_return"] - bm_ret
            results.append({
                "etf": etf["name"],
                "code": code,
                "params": p["label"],
                "annual": bt["annual_return"],
                "total": bt["total_return"],
                "sharpe": bt["sharpe"],
                "max_dd": bt["max_drawdown"],
                "win_rate": bt["win_rate"],
                "n_trades": bt["n_trades"],
                "bm_annual": bm_ret,
                "diff_bm": diff_bm,
                "score": score,
                "equity": bt["equity"],
                "trades": bt["trades"],
                "start": bt["start"],
                "end": bt["end"],
            })

            if score > best_score:
                best_score = score
                best = results[-1]

    # ---- 基准 ----
    print(f"\n[3/4] Buy&Hold 基准...")
    bm_results = {}
    for t in BENCHMARKS:
        code = t["code"]
        if code in aligned:
            bm = buy_hold(aligned[code])
            bm_results[t["name"]] = {
                "annual": bm["annual"],
                "total": bm["total"],
                "dates": bm["dates"],
                "closes": bm["closes"],
            }

    # ---- 打印结果 ----
    print("\n" + "=" * 62)
    print("  回测结果（按综合评分排序）")
    print("=" * 62)
    results.sort(key=lambda x: x["score"], reverse=True)
    for r in results:
        flag = " *** BEST ***" if r is best else ""
        print(f"\n  {r['etf']}  {r['params']}{flag}")
        print(f"    总收益 {r['total']*100:+6.1f}%  年化 {r['annual']*100:+6.1f}%  "
              f"夏普 {r['sharpe']:.2f}  最大DD {r['max_dd']*100:5.1f}%")
        print(f"    胜率 {r['win_rate']*100:4.0f}%  交易 {r['n_trades']}次")
        print(f"    vs BuyHold年化 {r['bm_annual']*100:+6.1f}%  超额 {r['diff_bm']*100:+6.1f}%")

    print("\n" + "=" * 62)
    print("  Buy&Hold 基准（共同区间）")
    print("=" * 62)
    for name, bm in bm_results.items():
        print(f"  {name:12s}  总收益 {bm['total']*100:+7.1f}%  年化 {bm['annual']*100:+6.1f}%")

    if best:
        print("\n" + "=" * 62)
        print("  最优参数推荐")
        print("=" * 62)
        print(f"  标的: {best['etf']} ({best['code']})")
        print(f"  参数: {best['params']}")
        print(f"  回测区间: {best['start']} ~ {best['end']} ({best.get('years',0):.1f}年)")
        print(f"  总收益: {best['total']*100:+.1f}%")
        print(f"  年化收益: {best['annual']*100:+.1f}%")
        print(f"  夏普比率: {best['sharpe']:.2f}")
        print(f"  最大回撤: {best['max_dd']*100:.1f}%")
        print(f"  胜率: {best['win_rate']*100:.0f}%")
        print(f"  交易次数: {best['n_trades']}")
        print(f"  vs 沪深300年化: {best['bm_annual']*100:+6.1f}%  超额: {best['diff_bm']*100:+6.1f}%")

    # ---- 保存 ----
    out = {
        "run_date": "2026-04-17",
        "common_start": str(common_start)[:10],
        "common_end": str(common_end)[:10],
        "best": {
            "etf": best["etf"], "code": best["code"], "params": best["params"],
            "total": best["total"], "annual": best["annual"],
            "sharpe": best["sharpe"], "max_dd": best["max_dd"],
            "win_rate": best["win_rate"], "n_trades": best["n_trades"],
            "bm_annual": best["bm_annual"], "diff_bm": best["diff_bm"],
            "score": best["score"],
        } if best else None,
        "benchmark": {
            k: {"annual": float(v["annual"]), "total": float(v["total"])}
            for k, v in bm_results.items()
        },
        "all_results": [
            {k: float(v) if isinstance(v, float) else v
             for k, v in r.items()
             if k not in ("equity", "trades")}
            for r in results
        ],
    }
    out_path = "D:/QClaw_Trading/scripts/backtest/backtest_result_2026-04-17.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
