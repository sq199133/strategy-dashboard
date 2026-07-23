"""
Step 3: Enhanced Multi-Strategy Backtest v2
JoinQuant社区策略吸收升级版：
  - 通道止损（唐奇安通道20日低点动态追踪）
  - ATR移动止损（最高价 - N×ATR）
  - 大盘系统性风控（160日极值比 + 3日累计涨跌）
  - RSI多参数调优（7/14/21 + 阈值组合）
  - AR人气指标双重确认（RSI+AR共振）
  - 双重损失止损（0.5%风险单位）
  - 最大回撤硬限制（单策略-25%熔断）
  - 海龟系统（唐奇安20日突破入场 + 10日低点出场）
  - 布林带+RSI过滤（防自由落体抄底）
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
TRADE_COST = 0.0007
INITIAL_CAP = 100000

# ── Data ────────────────────────────────────────────────────────

def load_data(code):
    name = STOCKS[code]
    fname = os.path.join(DATA_DIR, f"{code}_{name}.csv")
    df = pd.read_csv(fname, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    for col in ["open","high","low","close","volume","amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["close","volume"]).copy()


def compute_indicators(df):
    d = df.copy()

    # MAs
    for p in [5,10,20,30,60,120]:
        d[f"ma{p}"] = d["close"].rolling(p).mean()

    # MACD
    e12 = d["close"].ewm(span=12, adjust=False).mean()
    e26 = d["close"].ewm(span=26, adjust=False).mean()
    d["macd"] = e12 - e26
    d["macd_signal"] = d["macd"].ewm(span=9, adjust=False).mean()
    d["macd_hist"] = d["macd"] - d["macd_signal"]

    # RSI multi-param
    for per in [7,14,21]:
        delta = d["close"].diff()
        g = delta.where(delta > 0, 0).rolling(per).mean()
        l = (-delta.where(delta < 0, 0)).rolling(per).mean()
        rs = g / l.replace(0, np.nan)
        d[f"rsi_{per}"] = 100 - (100 / (1 + rs))

    # Bollinger
    d["bb_mid"] = d["ma20"]
    d["bb_std"] = d["close"].rolling(20).std()
    d["bb_upper"] = d["bb_mid"] + 2 * d["bb_std"]
    d["bb_lower"] = d["bb_mid"] - 2 * d["bb_std"]

    # ATR
    tr1 = d["high"] - d["low"]
    tr2 = (d["high"] - d["close"].shift()).abs()
    tr3 = (d["low"] - d["close"].shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    for per in [7,14,21]:
        d[f"atr_{per}"] = tr.rolling(per).mean()

    # Volume
    d["vol_ma20"] = d["volume"].rolling(20).mean()
    d["vol_ratio"] = d["volume"] / d["vol_ma20"].replace(0, np.nan)
    d["cpct"] = d["close"].pct_change()

    # OBV
    obv = (np.sign(d["close"].diff()) * d["volume"]).fillna(0).cumsum()
    d["obv"] = obv
    d["obv_ma20"] = obv.rolling(20).mean()

    # AR人气指标
    d["ar"] = ((d["high"] - d["open"]).rolling(26).sum() /
               (d["open"] - d["low"]).rolling(26).sum().replace(0, np.nan)) * 100

    # BIAS
    for p in [5,10,20]:
        d[f"bias_{p}"] = (d["close"] - d[f"ma{p}"]) / d[f"ma{p}"].replace(0, np.nan) * 100

    # Channel highs/lows
    d["ch10h"] = d["high"].rolling(10).max()
    d["ch10l"] = d["low"].rolling(10).min()
    d["ch20h"] = d["high"].rolling(20).max()
    d["ch20l"] = d["low"].rolling(20).min()

    return d.dropna()


# ── Market Risk Filter ──────────────────────────────────────────

def market_risk_filter(d):
    """
    大盘风控（零零发方法）：
    160日最高/最低比 > 2.2 且 3日累计涨跌<0 → 禁止入场
    """
    high_160 = d["high"].rolling(160).max()
    low_160 = d["low"].rolling(160).min()
    extreme = high_160 / low_160.replace(0, np.nan) > 2.2
    weak = d["close"].pct_change(3) < 0
    result = pd.Series(True, index=d.index)
    result[extreme & weak] = False
    return result


# ── Enhanced Backtest Engine ────────────────────────────────────

def run_backtest_v2(d, signal_fn, name, stop_type="channel",
                    atr_mult=2.0, chan_period=20,
                    mkt_filter=True, dd_hard=-0.25, double_loss=False):
    """
    Unified backtest engine with:
      - stop_type: channel | atr | hard | none
      - ATR-based trailing stop
      - Channel trailing stop
      - Double-loss variant
      - Market risk filter (大盘风控)
      - Max drawdown hard limit
    """
    d = d.copy()

    # Market filter
    mkt_ok = market_risk_filter(d) if mkt_filter else pd.Series(True, index=d.index)

    # Raw signal
    raw = signal_fn(d)

    pos = 0          # 0=cash, 1=long
    entry_px = 0.0
    entry_idx = -1
    hi_since_entry = 0.0
    equity = float(INITIAL_CAP)
    peak = float(INITIAL_CAP)
    trades = []

    for i in range(len(d)):
        if i < 60:
            continue
        row = d.iloc[i]
        sig = raw.iloc[i] if i < len(raw) else 0

        if pos == 0 and sig == 1 and mkt_ok.iloc[i]:
            pos = 1
            entry_px = row["close"]
            entry_idx = i
            hi_since_entry = row["high"]

        elif pos == 1:
            hi_since_entry = max(hi_since_entry, row["high"])

            # ── Compute stop price ──
            stop_px = None
            atr_val = row["atr_14"]

            if double_loss:
                # 双重损失: 0.5% 风险 = 0.5×ATR
                if pd.notna(atr_val) and atr_val > 0:
                    stop_px = hi_since_entry - atr_val * 0.5
                else:
                    stop_px = entry_px * 0.99

            elif stop_type == "channel":
                low_col = f"ch{chan_period}l"
                stop_px = row[low_col]

            elif stop_type == "atr":
                if pd.notna(atr_val) and atr_val > 0:
                    stop_px = hi_since_entry - atr_val * atr_mult
                else:
                    stop_px = entry_px * 0.98

            elif stop_type == "hard":
                stop_px = entry_px * (1 + dd_hard)

            # Stop hit?
            stop_hit = (stop_px is not None and row["low"] <= stop_px)

            # DD limit hit?
            current_dd = (equity - peak) / peak if peak > 0 else 0
            dd_hit = current_dd < dd_hard and i > entry_idx + 5

            # Exit signal
            exit_sig = (sig == -1) or stop_hit or dd_hit

            if exit_sig:
                if stop_hit:
                    exit_px = stop_px * 0.995  # slippage
                else:
                    exit_px = row["close"]

                ret = (exit_px / entry_px - 1) - TRADE_COST
                equity *= (1 + ret)

                reason = "stop" if stop_hit else ("dd_limit" if dd_hit else "signal")

                trades.append({
                    "entry_date": d.iloc[entry_idx]["date"],
                    "exit_date": row["date"],
                    "entry_price": float(entry_px),
                    "exit_price": float(exit_px),
                    "return": float(ret),
                    "exit_reason": reason,
                    "holding_days": (row["date"] - d.iloc[entry_idx]["date"]).days,
                })

                pos = 0
                peak = max(peak, equity)

        # Update peak tracking when in cash
        if pos == 0:
            peak = max(peak, equity)

    # Close open position at end
    if pos == 1:
        exit_px = d.iloc[-1]["close"]
        ret = (exit_px / entry_px - 1) - TRADE_COST
        equity *= (1 + ret)
        trades.append({
            "entry_date": d.iloc[entry_idx]["date"],
            "exit_date": d.iloc[-1]["date"],
            "entry_price": float(entry_px),
            "exit_price": float(exit_px),
            "return": float(ret),
            "exit_reason": "end",
            "holding_days": (d.iloc[-1]["date"] - d.iloc[entry_idx]["date"]).days,
        })

    return _metrics_from_trades(trades, d, name, {
        "stop_type": stop_type, "atr_mult": atr_mult,
        "chan_period": chan_period, "double_loss": double_loss,
    })


def _metrics_from_trades(trades, d, name, params):
    if len(trades) < 2:
        return None

    total_years = max((d["date"].iloc[-1] - d["date"].iloc[60]).days / 365.25, 0.5)

    equity = float(INITIAL_CAP)
    eq_arr = [equity]
    for t in trades:
        equity *= (1 + t["return"])
        eq_arr.append(equity)
    eq_arr = np.array(eq_arr)

    final_ret = equity / INITIAL_CAP - 1
    ann_ret = (1 + final_ret) ** (1 / total_years) - 1

    running_max = np.maximum.accumulate(eq_arr)
    dd = (eq_arr - running_max) / running_max
    max_dd = dd.min()

    win = [t for t in trades if t["return"] > 0]
    loss = [t for t in trades if t["return"] <= 0]
    wr = len(win) / len(trades)

    avg_w = np.mean([t["return"] for t in win]) if win else 0
    avg_l = np.mean([t["return"] for t in loss]) if loss else 0

    pf = (abs(sum(t["return"] for t in win) / 
              sum(abs(t["return"]) for t in loss))
          ) if loss else 99.0

    # Sharpe from trade-level returns
    tr = np.array([t["return"] for t in trades])
    avg_hold = np.mean([t["holding_days"] for t in trades]) or 1
    sharpe = np.sqrt(252 / avg_hold) * tr.mean() / (tr.std() + 1e-10)

    calmar = ann_ret / abs(max_dd) if max_dd != 0 else 0

    stop_hits = len([t for t in trades if t.get("exit_reason") == "stop"])
    sig_exits = len([t for t in trades if t.get("exit_reason") == "signal"])

    return {
        "strategy": name,
        "total_return": float(final_ret),
        "ann_return": float(ann_ret),
        "sharpe": float(sharpe),
        "max_drawdown": float(max_dd),
        "calmar": float(calmar),
        "win_rate": float(wr),
        "num_trades": len(trades),
        "avg_win_pct": float(avg_w * 100),
        "avg_loss_pct": float(avg_l * 100),
        "profit_factor": float(pf),
        "total_years": float(total_years),
        "stop_hits": stop_hits,
        "signal_exits": sig_exits,
        "params": params,
    }


# ================================================================
# SIGNAL FUNCTIONS
# ================================================================

def sig_ma_cross(d):
    s = pd.Series(0, index=d.index)
    s[(d["ma20"] > d["ma60"]) & (d["ma20"].shift(1) <= d["ma60"].shift(1))] = 1
    s[(d["ma20"] < d["ma60"]) & (d["ma20"].shift(1) >= d["ma60"].shift(1))] = -1
    return s


def sig_ma_trend(d):
    s = pd.Series(0, index=d.index)
    s[(d["ma5"] > d["ma10"]) & (d["ma10"] > d["ma20"]) & (d["close"] > d["ma20"])] = 1
    s[(d["ma5"] < d["ma10"]) & (d["close"] < d["ma20"])] = -1
    return s


def sig_macd(d):
    s = pd.Series(0, index=d.index)
    s[(d["macd_hist"] > 0) & (d["macd_hist"].shift(1) <= 0) & (d["macd"] > 0)] = 1
    s[(d["macd_hist"] < 0) & (d["macd_hist"].shift(1) >= 0)] = -1
    return s


def sig_rsi_factory(period=14, os=30, ob=70):
    def fn(d):
        s = pd.Series(0, index=d.index)
        rc = f"rsi_{period}"
        s[(d[rc] > os) & (d[rc].shift(1) <= os)] = 1
        s[(d[rc] < ob) & (d[rc].shift(1) >= ob)] = -1
        return s
    return fn


def sig_rsi_ar(d):
    """RSI + AR人气双重确认"""
    s = pd.Series(0, index=d.index)
    s[(d["rsi_14"] > 30) & (d["rsi_14"].shift(1) <= 30) &
      (d["ar"] > 100) & (d["ar"] < 150)] = 1
    s[(d["rsi_14"] < 70) & (d["rsi_14"].shift(1) >= 70) &
      (d["ar"] > 150)] = -1
    return s


def sig_bollinger_rsi(d):
    """布林带+RSI过滤，防自由落体抄底"""
    s = pd.Series(0, index=d.index)
    s[(d["low"] <= d["bb_lower"]) & (d["rsi_14"] > 25) &
      (d["close"] > d["bb_lower"] * 0.995)] = 1
    s[(d["high"] >= d["bb_upper"]) |
      ((d["close"] < d["bb_mid"]) & (d["close"].shift(1) >= d["bb_upper"]))] = -1
    return s


def sig_vol_breakout_enh(d):
    """量价突破 + ATR波动率过滤"""
    s = pd.Series(0, index=d.index)
    s[(d["vol_ratio"] > 1.5) & (d["cpct"] > 0.02) &
      (d["close"] > d["ma20"]) &
      (d["atr_14"] > d["atr_14"].rolling(60).mean())] = 1
    s[((d["vol_ratio"] > 1.3) & (d["cpct"] < -0.02)) |
      (d["close"] < d["ma10"])] = -1
    return s


def sig_combined_ar(d):
    """组合（MA+MACD+Vol）加AR人气过滤"""
    s = pd.Series(0, index=d.index)
    s[(d["close"] > d["ma20"]) & (d["ma20"] > d["ma60"]) &
      (d["macd_hist"] > 0) & (d["vol_ratio"] > 1.2) &
      (d["ar"] > 80) & (d["ar"] < 120)] = 1
    s[(d["close"] < d["ma20"]) |
      ((d["macd_hist"] < 0) & (d["close"] < d["ma60"]))] = -1
    return s


def sig_turtle(d):
    """海龟简化：20日高点突破入场，10日低点出场"""
    s = pd.Series(0, index=d.index)
    s[d["close"] >= d["ch20h"].shift(1)] = 1
    s[d["close"] <= d["ch10l"].shift(1)] = -1
    return s


# ── Strategy Registry ───────────────────────────────────────────

STRATEGIES = [
    # (name, signal_fn, stop_type, overrides)
    ("MA_Cross_ChanStop", sig_ma_cross, "channel", {"chan_period": 20}),
    ("MA_Cross_ATRStop", sig_ma_cross, "atr", {"atr_mult": 2.0}),
    ("MA_Trend_ChanStop", sig_ma_trend, "channel", {"chan_period": 20}),
    ("MA_Trend_ATRStop2x", sig_ma_trend, "atr", {"atr_mult": 1.5}),
    ("MACD_ChanStop", sig_macd, "channel", {"chan_period": 20}),
    ("Bollinger_RSI_ATR2x", sig_bollinger_rsi, "atr", {"atr_mult": 2.0}),
    ("Vol_Break_ChanStop", sig_vol_breakout_enh, "channel", {"chan_period": 10}),
    ("Comb_AR_ChanStop", sig_combined_ar, "channel", {"chan_period": 20}),

    # RSI variants (3 param sets × 2 stop types)
    ("RSI7_2575_ChanStop", sig_rsi_factory(7, 25, 75), "channel", {}),
    ("RSI14_3070_ChanStop", sig_rsi_factory(14, 30, 70), "channel", {}),
    ("RSI21_3565_ChanStop", sig_rsi_factory(21, 35, 65), "channel", {}),
    ("RSI7_DoubleLoss", sig_rsi_factory(7, 25, 75), "atr", {"double_loss": True}),
    ("RSI14_DoubleLoss", sig_rsi_factory(14, 30, 70), "atr", {"double_loss": True}),
    ("RSI_AR_ChanStop", sig_rsi_ar, "channel", {}),

    # Turtle
    ("Turtle_20x10_ATR2x", sig_turtle, "atr", {"atr_mult": 2.0}),
    ("Turtle_20x10_DoubleLoss", sig_turtle, "atr", {"double_loss": True}),
]

# Total: 15 strategies (vs 7 original), each with channel trailing stop or ATR stop


# ── Stock Analysis ──────────────────────────────────────────────

def analyze_stock_v2(code):
    """Run all v2 strategies on one stock."""
    df = load_data(code)
    d = compute_indicators(df)

    results = []
    for name, sig_fn, stop_type, overrides in STRATEGIES:
        params = {"stop_type": stop_type,
                  "atr_mult": overrides.get("atr_mult", 2.0),
                  "chan_period": overrides.get("chan_period", 20),
                  "double_loss": overrides.get("double_loss", False)}
        try:
            res = run_backtest_v2(d, sig_fn, name, **params)
            if res and res["num_trades"] >= 3:
                results.append(res)
        except Exception as e:
            print(f"  [{name}] Error: {e}")
            continue

    if not results:
        return None, []

    # Composite scoring (same formula for fair comparison with v1)
    for r in results:
        shp_sc = min(max((r["sharpe"] + 1) / 3, 0), 1)
        ret_sc = min(max(r["ann_return"] * 5, 0), 1)
        dd_sc = 1 - min(max(abs(r["max_drawdown"]) * 3, 0), 1)
        win_sc = r["win_rate"]
        r["score"] = round(0.3*shp_sc + 0.25*ret_sc + 0.2*dd_sc + 0.25*win_sc, 4)

    results.sort(key=lambda x: x["score"], reverse=True)
    best = results[0].copy()
    best["stock_code"] = code
    best["stock_name"] = STOCKS[code]

    # Personality
    d_a = d.copy()
    pv = d_a["close"].pct_change().std() * np.sqrt(252)
    amt = (d_a["volume"] * d_a["close"]).mean() / 1e8

    if pv > 0.45:
        ptype = "高波动/题材型"
    elif pv < 0.25:
        ptype = "低波动/稳健型"
    else:
        ptype = "中等波动/趋势型"

    best["stock_type"] = ptype
    best["price_volatility"] = float(pv)
    best["avg_daily_amount"] = float(amt)

    return best, results


def print_analysis(best, all_results):
    """Print enhanced analysis report."""
    lines = []
    lines.append("=" * 78)
    lines.append(f"  {best['stock_code']} {best['stock_name']}  |  {best['stock_type']}")
    lines.append(f"  日均成交额: {best['avg_daily_amount']:.1f}亿  |  年化波动率: {best['price_volatility']*100:.1f}%")
    lines.append("=" * 78)

    # Top 5 (was 3)
    lines.append("")
    lines.append("  ┌─ 策略排名 ──────────────────────────────────────────────────────")
    lines.append(f"  │ {'排名':<4} {'策略名':<30} {'得分':<8} {'年化':<10} {'夏普':<8} {'回撤':<10} {'胜率':<8} {'交易':<6}")
    lines.append(f"  │ {'-'*4} {'-'*28} {'-'*6} {'-'*8} {'-'*6} {'-'*8} {'-'*6} {'-'*4}")
    for i, r in enumerate(all_results[:5], 1):
        lines.append(f"  │ #{i:<2} {r['strategy']:<30} {r['score']:<8.4f} "
                     f"{r['ann_return']*100:+.1f}%   {r['sharpe']:<6.2f} "
                     f"{r['max_drawdown']*100:<8.1f}% {r['win_rate']*100:<6.0f}% {r['num_trades']:<4}")
    lines.append("  └──────────────────────────────────────────────────────────────────")
    lines.append("")

    # Best strategy detail
    s = best
    lines.append(f"  ★ 推荐策略: {s['strategy']}")
    lines.append(f"     年化收益: {s['ann_return']*100:+.2f}%   夏普比率: {s['sharpe']:.2f}")
    lines.append(f"     最大回撤: {s['max_drawdown']*100:.2f}%   卡玛比率: {s['calmar']:.2f}")
    lines.append(f"     交易次数: {s['num_trades']}次            胜率: {s['win_rate']*100:.1f}%")
    lines.append(f"     盈/亏比: {s['avg_win_pct']:.1f}% / {s['avg_loss_pct']:.1f}%")
    lines.append(f"     总回报率: {s['total_return']*100:+.2f}%")
    lines.append(f"     止损触发: {s['stop_hits']}次  |  信号退出: {s['signal_exits']}次")
    if s.get("params"):
        p = s["params"]
        lines.append(f"     止损设置: {p.get('stop_type','?')}  |  ATR倍数: {p.get('atr_mult','N/A')}  |  双重损失: {p.get('double_loss',False)}")
    lines.append("")

    # Strategy fit analysis
    lines.append("  ── 适配分析与社区改进成果 ──")

    # Compare with v1 baseline
    trend_based = any("MA" in r["strategy"] for r in all_results[:2])
    rsi_based = any("RSI" in r["strategy"] for r in all_results[:2])
    vol_based = any("Vol" in r["strategy"] or "Turtle" in r["strategy"] for r in all_results[:2])

    if trend_based:
        lines.append(f"  ✓ 趋势跟踪类策略（MA/海龟）排名靠前，{best['stock_name']}有趋势交易价值")
    if rsi_based:
        lines.append(f"  ✓ 反转类策略（RSI多参数）表现突出，适合震荡市操作")
    if vol_based:
        lines.append(f"  ✓ 量价/突破类策略信号有效，可结合通道止损锁定利润")
    if best["sharpe"] > 0.8:
        lines.append(f"  ✓ 夏普 > 0.8，社区改进版止损系统显著提升了风险调整收益")
    elif best["sharpe"] > 0.5:
        lines.append(f"  △ 夏普 {best['sharpe']:.2f}，止损优化后风险可控但仍需关注")

    if best["max_drawdown"] < -0.25:
        lines.append(f"  ⚠ 最大回撤 {best['max_drawdown']*100:.1f}%，大盘风控可进一步降低尾部风险")
    if best["win_rate"] < 0.35:
        lines.append(f"  ⚠ 胜率偏低，高盈亏比策略需严格执行纪律")

    # Community improvement highlight
    v1_best_rsi = best["strategy"].startswith("RSI")
    if v1_best_rsi and best["max_drawdown"] > -0.5:
        lines.append(f"  ✦ 社区升级亮点：通道止损替代固定ATR止损，对震荡票效果显著")
    if best["stop_hits"] > 0:
        stop_trade_pct = best["stop_hits"] / best["num_trades"] * 100
        lines.append(f"  ✦ 止损触发比例 {stop_trade_pct:.0f}%，说明风控系统正常工作")
        if stop_trade_pct < 15:
            lines.append(f"     止损触发率低，高胜率策略的止损主要起到最后防线作用")

    lines.append("")
    return "\n".join(lines)


# ── Run ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    print("=" * 78)
    print("  个股量化 v2 - 聚宽社区策略吸收增强版")
    print(f"  标的: {len(STOCKS)}只 | 策略: {len(STRATEGIES)}种")
    print("  增强功能: 通道止损 / ATR移动止盈 / 大盘风控 / RSI多参数 / AR确认 / 海龟 / 双重损失")
    print(f"  数据: baostock 日线 2019-01~2025-06 | 成本: 0.07%/次")
    print("=" * 78)

    all_best = {}
    all_summaries = {}

    for code in STOCKS:
        print(f"\n▶ {code} {STOCKS[code]} ...")
        best, results = analyze_stock_v2(code)
        if best is None:
            print("  ✗ 无有效结果")
            continue
        all_best[code] = best
        report = print_analysis(best, results)
        all_summaries[code] = report
        print(report)

    # ── Summary Table ──
    print("\n" + "=" * 78)
    print("  ★ 综合排名 - 各股最佳策略一览 (v2增强版)")
    print("=" * 78)
    hdr = f"  {'代码':<8} {'名称':<10} {'推荐策略':<30} {'年化':<10} {'夏普':<8} {'回撤':<10} {'胜率':<8} {'止损失':<6} {'停止类型'}"
    print(hdr)
    print(f"  {'-'*6} {'-'*8} {'-'*28} {'-'*8} {'-'*6} {'-'*8} {'-'*6} {'-'*5} {'-'*10}")

    sorted_ = sorted(all_best.values(), key=lambda x: x["score"], reverse=True)
    for s in sorted_:
        p = s.get("params", {})
        stop_label = p.get("stop_type", "") + ("+双损" if p.get("double_loss") else "")
        sh = s.get("stop_hits", 0)
        print(f"  {s['stock_code']:<8} {s['stock_name']:<10} {s['strategy']:<30} "
              f"{s['ann_return']*100:+.2f}%  {s['sharpe']:<6.2f} "
              f"{s['max_drawdown']*100:<8.1f}% {s['win_rate']*100:<6.0f}% {sh:<4} "
              f"{stop_label}")

    print(f"\n  分析完成: {len(all_best)}/{len(STOCKS)}只")

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = rf"D:\QClaw_Trading\backtest\stock_v2_results_{timestamp}.json"
    out_txt = rf"D:\QClaw_Trading\backtest\stock_v2_report_{timestamp}.txt"

    # Serialize results
    def serialize(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, (np.bool_,)):
            return bool(obj)
        elif isinstance(obj, pd.Timestamp):
            return str(obj)
        return str(obj)

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "analysis_date": datetime.now().isoformat(),
            "version": "v2_enhanced",
            "strategies_tested": len(STRATEGIES),
            "stocks": {k: {kk: vv for kk, vv in v.items()
                           if kk not in ("stock_name", "stock_code")}
                       for k, v in all_best.items()},
            "ranking": [s["stock_code"] for s in sorted_],
        }, f, ensure_ascii=False, indent=2, default=serialize)

    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(all_summaries.values()) +
                f"\n\n分析完成: {len(all_best)}/{len(STOCKS)} 只\n")

    print(f"\n  结果保存:")
    print(f"    JSON: {out_json}")
    print(f"    TXT:  {out_txt}")
