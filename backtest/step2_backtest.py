"""
Step 2: Multi-strategy backtest for each stock
Tests 5 strategies + combined, finds best fit per stock
"""
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────
STOCKS = {
    "300179": "四方达", "002222": "福晶科技", "688599": "天合光能",
    "300690": "双一科技", "301091": "深城交", "603322": "超讯科技",
    "300102": "乾照光电", "002389": "航天彩虹", "300058": "蓝色光标",
    "603901": "永创智能", "603667": "五洲新春", "603286": "日盈电子",
    "600118": "中国卫星",
}

DATA_DIR = r"D:\QClaw_Trading\data"
TRADE_COST = 0.0007  # 0.07% round-trip (commission + stamp)
INITIAL_CAP = 100000

# ── Helpers ─────────────────────────────────────────────────────

def load_data(code):
    name = STOCKS[code]
    fname = os.path.join(DATA_DIR, f"{code}_{name}.csv")
    df = pd.read_csv(fname, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    for col in ["open","high","low","close","volume","amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close","volume"]).copy()
    return df


def compute_indicators(df):
    """Compute all technical indicators used across strategies."""
    d = df.copy()
    # MA
    d["ma5"] = d["close"].rolling(5).mean()
    d["ma10"] = d["close"].rolling(10).mean()
    d["ma20"] = d["close"].rolling(20).mean()
    d["ma30"] = d["close"].rolling(30).mean()
    d["ma60"] = d["close"].rolling(60).mean()
    d["ma120"] = d["close"].rolling(120).mean()

    # MACD
    exp12 = d["close"].ewm(span=12, adjust=False).mean()
    exp26 = d["close"].ewm(span=26, adjust=False).mean()
    d["macd"] = exp12 - exp26
    d["macd_signal"] = d["macd"].ewm(span=9, adjust=False).mean()
    d["macd_hist"] = d["macd"] - d["macd_signal"]

    # RSI (14)
    delta = d["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    d["rsi"] = 100 - (100 / (1 + rs))

    # Bollinger Bands (20, 2)
    d["bb_mid"] = d["ma20"]
    d["bb_std"] = d["close"].rolling(20).std()
    d["bb_upper"] = d["bb_mid"] + 2 * d["bb_std"]
    d["bb_lower"] = d["bb_mid"] - 2 * d["bb_std"]

    # ATR (14)
    tr1 = d["high"] - d["low"]
    tr2 = (d["high"] - d["close"].shift()).abs()
    tr3 = (d["low"] - d["close"].shift()).abs()
    d["atr"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()

    # Volume metrics
    d["vol_ma20"] = d["volume"].rolling(20).mean()
    d["vol_ratio"] = d["volume"] / d["vol_ma20"].replace(0, np.nan)
    d["close_pct"] = d["close"].pct_change()

    # OBV
    obv = (np.sign(d["close"].diff()) * d["volume"]).fillna(0).cumsum()
    d["obv"] = obv
    d["obv_ma20"] = obv.rolling(20).mean()

    return d.dropna()


# ── Strategy Simulators ─────────────────────────────────────────

def strategy_ma_crossover(d):
    """MA20/MA60 crossover: trend-following"""
    signal = pd.Series(0, index=d.index)
    # Golden cross (20 up through 60)
    condition_buy = (d["ma20"] > d["ma60"]) & (d["ma20"].shift(1) <= d["ma60"].shift(1))
    signal[condition_buy] = 1
    # Death cross (20 down through 60)
    condition_sell = (d["ma20"] < d["ma60"]) & (d["ma20"].shift(1) >= d["ma60"].shift(1))
    signal[condition_sell] = -1
    return signal


def strategy_ma_trend(d):
    """Multi-MA trend: 5>10>20>60 = strong uptrend"""
    signal = pd.Series(0, index=d.index)
    cond_buy = (d["ma5"] > d["ma10"]) & (d["ma10"] > d["ma20"]) & (d["close"] > d["ma20"])
    signal[cond_buy] = 1
    cond_sell = (d["ma5"] < d["ma10"]) & (d["close"] < d["ma20"])
    signal[cond_sell] = -1
    return signal


def strategy_macd(d):
    """MACD golden cross + above zero confirmation"""
    signal = pd.Series(0, index=d.index)
    # Golden cross (hist turns positive from negative)
    cond_buy = (d["macd_hist"] > 0) & (d["macd_hist"].shift(1) <= 0) & (d["macd"] > 0)
    signal[cond_buy] = 1
    # Death cross (hist turns negative)
    cond_sell = (d["macd_hist"] < 0) & (d["macd_hist"].shift(1) >= 0)
    signal[cond_sell] = -1
    return signal


def strategy_rsi_reversal(d):
    """RSI oversold/overbought mean reversion"""
    signal = pd.Series(0, index=d.index)
    # Oversold bounce (RSI < 30 -> buy when crossing back above 30)
    cond_buy = (d["rsi"] > 30) & (d["rsi"].shift(1) <= 30)
    signal[cond_buy] = 1
    # Overbought sell (RSI > 70 -> sell when crossing back below 70)
    cond_sell = (d["rsi"] < 70) & (d["rsi"].shift(1) >= 70)
    signal[cond_sell] = -1
    return signal


def strategy_bollinger(d):
    """Bollinger Bands mean reversion + breakout"""
    signal = pd.Series(0, index=d.index)
    # Touch lower band = buy
    cond_buy = (d["low"] <= d["bb_lower"]) & (d["close"] > d["bb_lower"] * 0.99)
    signal[cond_buy] = 1
    # Touch upper band mid-trend = hold; above upper band early = sell
    cond_sell = (d["high"] >= d["bb_upper"]) | (d["close"] < d["bb_mid"] & (d["close"].shift(1) >= d["bb_upper"]))
    signal[cond_sell] = -1
    return signal


def strategy_volume_breakout(d):
    """Volume surge + price breakout confirmation"""
    signal = pd.Series(0, index=d.index)
    # Volume > 1.5x average + close > MA20 (recent uptrend)
    cond_buy = (d["vol_ratio"] > 1.5) & (d["close_pct"] > 0.02) & (d["close"] > d["ma20"])
    signal[cond_buy] = 1
    # Volume surge on down day or close < MA10
    cond_sell = ((d["vol_ratio"] > 1.3) & (d["close_pct"] < -0.02)) | (d["close"] < d["ma10"])
    signal[cond_sell] = -1
    return signal


def strategy_combined_ma_macd_vol(d):
    """Combined: MA trend + MACD confirmation + Volume validation"""
    signal = pd.Series(0, index=d.index)
    cond_buy = (
        (d["close"] > d["ma20"]) &                # Above 20 MA
        (d["ma20"] > d["ma60"]) &                  # 20 above 60 = uptrend
        (d["macd_hist"] > 0) &                     # MACD positive momentum
        (d["vol_ratio"] > 1.2)                     # Above average volume
    )
    signal[cond_buy] = 1
    cond_sell = (
        (d["close"] < d["ma20"]) |                # Price below 20 MA
        ((d["macd_hist"] < 0) & (d["close"] < d["ma60"]))  # MACD negative + below 60
    )
    signal[cond_sell] = -1
    return signal


# ── Backtest Engine ─────────────────────────────────────────────

STRATEGIES = [
    ("MA_Crossover", strategy_ma_crossover),
    ("MA_Trend", strategy_ma_trend),
    ("MACD", strategy_macd),
    ("RSI_Reversal", strategy_rsi_reversal),
    ("Bollinger", strategy_bollinger),
    ("Volume_Breakout", strategy_volume_breakout),
    ("Combined_MA_MACD_Vol", strategy_combined_ma_macd_vol),
]


def run_backtest(d, strat_name, strat_fn):
    """Run a single strategy backtest, returns performance metrics."""
    signal = strat_fn(d)
    d = d.copy()
    d["signal"] = signal

    # Generate trading positions (1 = long, 0 = cash)
    d["position"] = 0
    in_position = False
    trades = []
    entry_price = 0
    entry_date = None

    for i in range(len(d)):
        sig = d.iloc[i]["signal"]
        if sig == 1 and not in_position:
            in_position = True
            entry_price = d.iloc[i]["close"]
            entry_date = d.iloc[i]["date"]
        elif sig == -1 and in_position:
            in_position = False
            exit_price = d.iloc[i]["close"]
            ret = (exit_price / entry_price - 1) * 1  # 不考虑杠杆
            ret_net = ret - TRADE_COST
            trades.append({
                "entry_date": entry_date,
                "exit_date": d.iloc[i]["date"],
                "entry_price": float(entry_price),
                "exit_price": float(exit_price),
                "return": float(ret_net),
                "holding_days": (d.iloc[i]["date"] - entry_date).days,
            })
        d.iloc[i, d.columns.get_loc("position")] = 1 if in_position else 0

    # Close any open position at end
    if in_position:
        exit_price = d.iloc[-1]["close"]
        ret = (exit_price / entry_price - 1) - TRADE_COST
        trades.append({
            "entry_date": entry_date,
            "exit_date": d.iloc[-1]["date"],
            "entry_price": float(entry_price),
            "exit_price": float(exit_price),
            "return": float(ret),
            "holding_days": (d.iloc[-1]["date"] - entry_date).days,
        })

    # Compute portfolio returns
    d["daily_ret"] = d["close"].pct_change() * d["position"].shift(1)
    d["equity"] = (1 + d["daily_ret"].fillna(0)).cumprod() * INITIAL_CAP

    # Metrics
    total_days = (d["date"].iloc[-1] - d["date"].iloc[0]).days
    total_years = max(total_days / 365.25, 0.5)

    if len(trades) < 2:
        return None

    # Returns
    final_return = (d["equity"].iloc[-1] / INITIAL_CAP - 1)
    ann_return = (1 + final_return) ** (1 / total_years) - 1

    # Sharpe (daily, risk-free ~0)
    daily_rets = d["daily_ret"].dropna()
    sharpe = np.sqrt(252) * daily_rets.mean() / (daily_rets.std() + 1e-10)

    # Max drawdown
    equity_series = d["equity"]
    running_max = equity_series.cummax()
    drawdown = (equity_series - running_max) / running_max
    max_dd = drawdown.min()

    # Trade stats
    win_trades = [t for t in trades if t["return"] > 0]
    win_rate = len(win_trades) / max(len(trades), 1)
    avg_ret = np.mean([t["return"] for t in trades]) if trades else 0
    avg_win = np.mean([t["return"] for t in win_trades]) if win_trades else 0
    avg_loss = np.mean([t["return"] for t in trades if t["return"] <= 0]) if any(t["return"] <= 0 for t in trades) else 0
    profit_factor = abs(sum(t["return"] for t in win_trades) / sum(abs(t["return"]) for t in trades if t["return"] <= 0)) if any(t["return"] <= 0 for t in trades) else 0

    # Calmar ratio
    calmar = ann_return / abs(max_dd) if max_dd != 0 else 0

    # Return / max drawdown ratio
    rdd = (1 + final_return) / (1 - max_dd) - 1 if max_dd < 0 else final_return

    # Volatility
    vol = daily_rets.std() * np.sqrt(252)

    return {
        "strategy": strat_name,
        "total_return": float(final_return),
        "ann_return": float(ann_return),
        "sharpe": float(sharpe),
        "max_drawdown": float(max_dd),
        "calmar": float(calmar),
        "volatility": float(vol),
        "win_rate": float(win_rate),
        "num_trades": len(trades),
        "avg_trade_return": float(avg_ret),
        "avg_win": float(avg_win),
        "avg_loss": float(avg_loss),
        "profit_factor": float(profit_factor),
        "total_years": float(total_years),
    }


# ── Main ────────────────────────────────────────────────────────

def analyze_stock(code):
    """Run all strategies on one stock and return best fit."""
    df = load_data(code)
    d = compute_indicators(df)

    results = []
    for name, fn in STRATEGIES:
        try:
            res = run_backtest(d, name, fn)
            if res and res["num_trades"] >= 5:
                results.append(res)
        except Exception as e:
            print(f"  [{name}] Error: {e}")
            continue

    if not results:
        return None, []

    # Score each strategy (weighted composite)
    for r in results:
        sharpe_score = min(max((r["sharpe"] + 1) / 3, 0), 1)
        return_score = min(max(r["ann_return"] * 5, 0), 1)
        dd_score = 1 - min(max(abs(r["max_drawdown"]) * 3, 0), 1)
        win_score = r["win_rate"]
        compound = 0.3 * sharpe_score + 0.25 * return_score + 0.2 * dd_score + 0.25 * win_score
        r["score"] = round(compound, 4)

    results.sort(key=lambda x: x["score"], reverse=True)
    best = results[0]
    best["stock_code"] = code
    best["stock_name"] = STOCKS[code]

    # Stock personality assessment
    d_analysis = d.copy()
    avg_vol = d_analysis["volume"].mean()
    avg_turnover = (d_analysis["volume"] * d_analysis["close"]).mean() / 1e8
    price_volatility = d_analysis["close"].pct_change().std() * np.sqrt(252)

    # Determine stock type
    personality = "混合型"
    if price_volatility > 0.45:
        personality = "高波动/题材型"
    elif price_volatility < 0.25:
        personality = "低波动/稳健型"
    else:
        personality = "中等波动/趋势型"

    best["stock_type"] = personality
    best["price_volatility"] = float(price_volatility)
    best["avg_daily_amount"] = float(avg_turnover)

    return best, results


def generate_strategy_advice(best, all_results):
    """Generate human-readable strategy recommendations."""
    stock_name = best["stock_name"]
    stock_code = best["stock_code"]
    lines = []
    lines.append("=" * 72)
    lines.append(f"{stock_code} {stock_name} | {best['stock_type']}")
    lines.append("=" * 72)

    # Stock characteristics
    lines.append(f"  日均成交额: {best['avg_daily_amount']:.1f}亿")
    lines.append(f"  年化波动率: {best['volatility']*100:.1f}%")
    lines.append("")

    # Top 3 strategies
    lines.append("  ┌─ 策略排名 ────────────────────────────────────")
    for i, r in enumerate(all_results[:3], 1):
        lines.append(f"  │ #{i} {r['strategy']:<25s}  score={r['score']:.3f}  "
                     f"收益={r['ann_return']*100:+.1f}%  夏普={r['sharpe']:.2f}  "
                     f"回撤={r['max_drawdown']*100:.1f}%  胜率={r['win_rate']*100:.0f}%")
    lines.append("  └───────────────────────────────────────────────")
    lines.append("")

    # Best strategy detail
    s = best
    lines.append(f"  ★ 推荐策略: {s['strategy']}")
    lines.append(f"     年化收益: {s['ann_return']*100:+.2f}%")
    lines.append(f"     夏普比率: {s['sharpe']:.2f}")
    lines.append(f"     最大回撤: {s['max_drawdown']*100:.2f}%")
    lines.append(f"     卡玛比率: {s['calmar']:.2f}")
    lines.append(f"     交易次数: {s['num_trades']}次")
    lines.append(f"     胜    率: {s['win_rate']*100:.1f}%")
    lines.append(f"     盈/亏比: {s['avg_win']*100:.1f}% / {s['avg_loss']*100:.1f}%")
    lines.append(f"     总回报率: {s['total_return']*100:+.2f}%")
    lines.append("")

    # Strategy fit analysis
    lines.append("  ── 适配分析 ──")

    if s["strategy"].startswith("MA_Crossover") or s["strategy"].startswith("MA_Trend"):
        if s["sharpe"] > 1.0:
            lines.append(f"  ✓ {stock_name}具有良好的趋势性，适合趋势跟踪策略")
        else:
            lines.append(f"  △ {stock_name}虽有趋势策略表现靠前，但效果一般，需补充止损")
    elif s["strategy"] == "MACD":
        lines.append(f"  ✓ {stock_name}的MACD信号有效，关注顶底背离配合")
        if best['stock_type'] == '高波动/题材型':
            lines.append(f"  ⚠ 高波动股MACD滞后明显，建议结合量比确认")
    elif s["strategy"] == "RSI_Reversal":
        lines.append(f"  ✓ {stock_name}呈箱体震荡特征，适合RSI反向交易")
        if s["sharpe"] > 0.8:
            lines.append(f"  ✓ RSI参数14表现稳定，可尝试调至9或21优化")
    elif s["strategy"] == "Bollinger":
        lines.append(f"  ✓ {stock_name}波动率有规律，布林带策略有效")
    elif s["strategy"] == "Volume_Breakout":
        lines.append(f"  ✓ {stock_name}量价关系可靠，放量突破信号指向性好")
    elif s["strategy"] == "Combined_MA_MACD_Vol":
        lines.append(f"  ✓ {stock_name}多维度信号共振有效，综合条件过滤噪音")
        if s["win_rate"] < 0.4:
            lines.append(f"  ⚠ 组合策略胜率偏低，说明各维度信号一致性不足")

    # Risk warning
    if s["max_drawdown"] < -0.3:
        lines.append(f"  ⚠ 最大回撤超过30%，务必设置严格止损线")
    if s["sharpe"] < 0.5:
        lines.append(f"  ⚠ 夏普低于0.5，风险调整后收益不理想，该股票可能不适合趋势策略")
    if s["win_rate"] < 0.35:
        lines.append(f"  ⚠ 胜率不足35%，高盈亏比策略需严格执行纪律")
    if best['stock_type'] == '高波动/题材型' and s["win_rate"] < 0.4:
        lines.append(f"  ⚠ 高波动股用技术策略效果有限，建议重点看筹码和板块情绪")

    lines.append("")
    return "\n".join(lines)


# ── Run ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    print("=" * 72)
    print("  个股量化 - 多策略回测分析")
    print(f"  标的数: {len(STOCKS)} | 数据源: baostock 日线 | 交易成本: 0.07%/次")
    print(f"  回测期间: 2019-01 ~ 2025-06")
    print("=" * 72)
    print()

    all_best = {}
    all_summary = {}

    for code in STOCKS:
        print(f"▶ 分析 {code} {STOCKS[code]} ...")
        best, results = analyze_stock(code)
        if best is None:
            print(f"  ✗ 数据不足，跳过")
            print()
            continue

        all_best[code] = best
        report = generate_strategy_advice(best, results)
        all_summary[code] = report
        print(report)

    # ── Output: summary table ──
    print()
    print("=" * 72)
    print("  综合排名 - 各股最佳策略一览")
    print("=" * 72)
    print(f"  {'代码':<10} {'名称':<10} {'推荐策略':<25} {'年化收益':<10} {'夏普':<8} {'最大回撤':<10} {'胜率':<8} {'类型':<12}")
    print(f"  {'-'*8} {'-'*8} {'-'*23} {'-'*8} {'-'*6} {'-'*8} {'-'*6} {'-'*10}")

    sorted_stocks = sorted(all_best.values(), key=lambda x: x["score"], reverse=True)
    for s in sorted_stocks:
        print(f"  {s['stock_code']:<10} {s['stock_name']:<10} {s['strategy']:<25} "
              f"{s['ann_return']*100:+.2f}%    {s['sharpe']:<8.2f} {s['max_drawdown']*100:<8.1f}% "
              f"{s['win_rate']*100:<6.0f}% {s['stock_type']:<10}")

    print()
    print(f"  分析完成: {len(all_best)}/13只成功分析")

    # Save full results
    out_path = r"D:\QClaw_Trading\backtest\stock_analysis_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "analysis_date": datetime.now().isoformat(),
            "stocks": {k: {kk: vv for kk, vv in v.items() if kk not in ("stock_name", "stock_code")} for k, v in all_best.items()},
            "summary_table": "\n".join(all_summary.values()),
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f"  结果已保存: {out_path}")

    # Save human-readable report
    report_path = r"D:\QClaw_Trading\backtest\stock_analysis_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(all_summary.values()))
    print(f"  报告已保存: {report_path}")
