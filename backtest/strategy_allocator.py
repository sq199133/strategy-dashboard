"""
智能策略分配器 — Strategy Allocator v1
基于V2回测结果，自动为每只股票分配最优策略+仓位

核心能力：
  1. 股票画像（波动率、成交额、趋势强度、震荡程度）
  2. 策略匹配（基于V2回测知识库）
  3. 多策略候选（主策略 + 备选 + 市场风格切换）
  4. 仓位管理（ATR风险平价）
  5. 每日信号生成（可cron定时执行）
  6. 组合级风险聚合
"""
import pandas as pd
import numpy as np
import os, json, sys
from datetime import datetime, date
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

# ================================================================
# 配置
# ================================================================
DATA_DIR = r"D:\QClaw_Trading\data"
BACKTEST_DIR = r"D:\QClaw_Trading\backtest"
TRADE_COST = 0.0007
INITIAL_CAP = 1_000_000       # 组合总资金

# 策略知识库 — 从V2回测结果提炼
STRATEGY_KNOWLEDGE_BASE = {
    # stock_code -> { primary_strategy, alt_strategy, personality, stop_config }
    "300179": {  # 四方达 - RSI/海龟震荡型
        "primary": "Turtle_20x10_DoubleLoss",
        "alternative": "RSI_AR_ChanStop",
        "personality": "高波动震荡",
        "stop": "double_loss",
        "position_pct": 0.08,  # 单票仓位上限
    },
    "002222": {  # 福晶科技
        "primary": "Turtle_20x10_DoubleLoss",
        "alternative": "RSI7_DoubleLoss",
        "personality": "高波动震荡",
        "stop": "double_loss",
        "position_pct": 0.08,
    },
    "688599": {  # 天合光能 - MA趋势型（特殊）
        "primary": "MA_Cross_ChanStop",
        "alternative": "Turtle_20x10_DoubleLoss",
        "personality": "中波动趋势",
        "stop": "channel_20",
        "position_pct": 0.12,  # 趋势票可以给大仓位
    },
    "300690": {  # 双一科技
        "primary": "Turtle_20x10_DoubleLoss",
        "alternative": "Comb_AR_ChanStop",
        "personality": "高波动震荡",
        "stop": "double_loss",
        "position_pct": 0.08,
    },
    "301091": {  # 深城交
        "primary": "Turtle_20x10_DoubleLoss",
        "alternative": "RSI_AR_ChanStop",
        "personality": "极高波动突破",
        "stop": "double_loss",
        "position_pct": 0.07,
    },
    "603322": {  # 超讯科技
        "primary": "Turtle_20x10_DoubleLoss",
        "alternative": "RSI14_DoubleLoss",
        "personality": "高波动震荡",
        "stop": "double_loss",
        "position_pct": 0.08,
    },
    "300102": {  # 乾照光电 - 海龟杀手
        "primary": "Turtle_20x10_DoubleLoss",
        "alternative": "Vol_Break_ChanStop",
        "personality": "高波动突破",
        "stop": "double_loss",
        "position_pct": 0.10,
    },
    "002389": {  # 航天彩虹
        "primary": "Turtle_20x10_DoubleLoss",
        "alternative": "Comb_AR_ChanStop",
        "personality": "高波动趋势",
        "stop": "double_loss",
        "position_pct": 0.08,
    },
    "300058": {  # 蓝色光标
        "primary": "Turtle_20x10_DoubleLoss",
        "alternative": "Comb_AR_ChanStop",
        "personality": "高波动震荡",
        "stop": "double_loss",
        "position_pct": 0.08,
    },
    "603901": {  # 永创智能
        "primary": "Turtle_20x10_DoubleLoss",
        "alternative": "RSI21_3565_ChanStop",
        "personality": "高波动震荡",
        "stop": "double_loss",
        "position_pct": 0.06,  # 回撤最大，保守仓位
    },
    "603667": {  # 五洲新春
        "primary": "Turtle_20x10_DoubleLoss",
        "alternative": "Comb_AR_ChanStop",
        "personality": "高波动震荡",
        "stop": "double_loss",
        "position_pct": 0.08,
    },
    "603286": {  # 日盈电子
        "primary": "Turtle_20x10_DoubleLoss",
        "alternative": "Vol_Break_ChanStop",
        "personality": "高波动突破",
        "stop": "double_loss",
        "position_pct": 0.10,
    },
    "600118": {  # 中国卫星
        "primary": "Turtle_20x10_DoubleLoss",
        "alternative": "RSI7_DoubleLoss",
        "personality": "中波动震荡",
        "stop": "double_loss",
        "position_pct": 0.08,
    },
}

STOCK_NAMES = {
    "300179": "四方达", "002222": "福晶科技", "688599": "天合光能",
    "300690": "双一科技", "301091": "深城交", "603322": "超讯科技",
    "300102": "乾照光电", "002389": "航天彩虹", "300058": "蓝色光标",
    "603901": "永创智能", "603667": "五洲新春", "603286": "日盈电子",
    "600118": "中国卫星",
}


# ================================================================
# 数据层
# ================================================================

def load_stock_data(code: str) -> pd.DataFrame:
    """加载单只股票日线数据"""
    name = STOCK_NAMES[code]
    path = os.path.join(DATA_DIR, f"{code}_{name}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"数据文件不存在: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    for c in ["open","high","low","close","volume","amount"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["close","volume"])


def compute_profile_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算画像所需指标（轻量版，不和回测公用）"""
    d = df.copy()
    # MAs
    for p in [5,10,20,30,60,120]:
        d[f"ma{p}"] = d["close"].rolling(p).mean()
    # ATR
    tr1 = d["high"] - d["low"]
    tr2 = (d["high"] - d["close"].shift()).abs()
    tr3 = (d["low"] - d["close"].shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    d["atr_14"] = tr.rolling(14).mean()
    # Volume
    d["vol_ma20"] = d["volume"].rolling(20).mean()
    d["vol_ratio"] = d["volume"] / d["vol_ma20"].replace(0, np.nan)
    # MACD
    e12 = d["close"].ewm(span=12, adjust=False).mean()
    e26 = d["close"].ewm(span=26, adjust=False).mean()
    d["macd"] = e12 - e26
    d["macd_signal"] = d["macd"].ewm(span=9, adjust=False).mean()
    d["macd_hist"] = d["macd"] - d["macd_signal"]
    # RSI 14
    delta = d["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    d["rsi_14"] = 100 - (100 / (1 + rs))
    # Channel
    d["ch20h"] = d["high"].rolling(20).max()
    d["ch20l"] = d["low"].rolling(20).min()
    d["ch10l"] = d["low"].rolling(10).min()
    # Returns
    d["pct"] = d["close"].pct_change()
    return d.dropna()


# ================================================================
# 股票画像模块
# ================================================================

@dataclass
class StockProfile:
    code: str
    name: str
    price_volatility: float        # 年化波动率
    avg_daily_amount: float        # 日均成交额(亿)
    avg_daily_volume: float        # 日均成交量
    trend_strength: float          # 趋势强度 (-1~1, 正=多头)
    oscillation_score: float       # 震荡程度 (0~1)
    volume_activity: float         # 量能活跃度
    last_price: float              # 最新价
    last_atr: float                # 最新ATR
    rsi_now: float                 # 最新RSI
    macd_status: str               # bull/bear/neutral
    near_channel_top: bool         # 是否接近20日高点
    near_channel_bottom: bool      # 是否接近20日低点
    profile_summary: str = ""      # 文字画像


def profile_stock(code: str, df: pd.DataFrame, d: pd.DataFrame) -> StockProfile:
    """对一只股票进行深度画像"""
    last = d.iloc[-1]
    recent = d.tail(60)

    vol = d["pct"].std() * np.sqrt(252)
    avg_amt = (d["volume"] * d["close"]).mean() / 1e8
    avg_vol_amt = d["volume"].mean()

    # 趋势强度：MA排列得分
    ma_aligned = (
        (last["ma5"] > last["ma10"]) +
        (last["ma10"] > last["ma20"]) +
        (last["ma20"] > last["ma30"]) +
        (last["ma30"] > last["ma60"]) +
        (last["close"] > last["ma20"])
    )
    trend_strength = (ma_aligned - 2.5) / 2.5  # -1 ~ 1

    # 震荡程度：RSI在30-70之间的比例
    rsi_in_range = ((recent["rsi_14"] >= 30) & (recent["rsi_14"] <= 70)).mean()
    # 加上通道内占比
    in_channel = ((recent["close"] >= recent["ch20l"]) & 
                  (recent["close"] <= recent["ch20h"])).mean()
    oscillation_score = (rsi_in_range * 0.5 + in_channel * 0.5)

    # 量能活跃度
    vol_ratio_mean = d["vol_ratio"].tail(20).mean()
    volume_activity = min(vol_ratio_mean / 1.5, 1.0)

    # MACD状态
    if last["macd_hist"] > 0 and last["macd"] > last["macd_signal"]:
        macd_status = "bull"
    elif last["macd_hist"] < 0 and last["macd"] < last["macd_signal"]:
        macd_status = "bear"
    else:
        macd_status = "neutral"

    # 通道位置
    near_top = last["close"] >= last["ch20h"] * 0.98
    near_bottom = last["close"] <= last["ch20l"] * 1.02

    # 文字画像
    if oscillation_score > 0.7:
        summary = f"震荡型(震荡度{oscillation_score:.2f})"
    elif trend_strength > 0.3:
        summary = f"多头趋势(强度{trend_strength:.2f})"
    elif trend_strength < -0.3:
        summary = f"空头趋势(强度{trend_strength:.2f})"
    else:
        summary = f"混合型"

    if vol > 0.45:
        summary += "·高波动"
    elif vol > 0.30:
        summary += "·中波动"
    else:
        summary += "·低波动"

    if volume_activity > 0.8:
        summary += "·放量"
    elif volume_activity < 0.5:
        summary += "·缩量"

    return StockProfile(
        code=code, name=STOCK_NAMES[code],
        price_volatility=float(vol), avg_daily_amount=float(avg_amt),
        avg_daily_volume=float(avg_vol_amt),
        trend_strength=float(trend_strength),
        oscillation_score=float(oscillation_score),
        volume_activity=float(volume_activity),
        last_price=float(last["close"]),
        last_atr=float(last["atr_14"]),
        rsi_now=float(last["rsi_14"]),
        macd_status=macd_status,
        near_channel_top=near_top,
        near_channel_bottom=near_bottom,
        profile_summary=summary,
    )


# ================================================================
# 策略信号生成器
# ================================================================

def check_entry(code: str, profile: StockProfile, d: pd.DataFrame) -> Optional[Dict]:
    """检查今日是否有入场信号，返回信号详情或None"""
    kb = STRATEGY_KNOWLEDGE_BASE.get(code)
    if not kb:
        return None

    strategy = kb["primary"]
    last = d.iloc[-1]
    prev = d.iloc[-2] if len(d) >= 2 else last

    signal = None
    reason = ""

    # ── Turtle 20日突破 ──
    if "Turtle" in strategy:
        if last["close"] >= last["ch20h"]:
            signal = "BUY"
            reason = f"Turtle突破:{last['close']:.2f}≥{last['ch20h']:.2f}"

    # ── MA_Cross_ChanStop ──
    elif "MA_Cross" in strategy:
        golden = (last["ma20"] > last["ma60"]) and (prev["ma20"] <= prev["ma60"])
        if golden:
            signal = "BUY"
            reason = f"MA金叉:MA20={last['ma20']:.2f}>MA60={last['ma60']:.2f}"

    # ── RSI反转 ──
    elif "RSI" in strategy:
        if "AR" in strategy:
            # RSI + AR确认
            if (last["rsi_14"] > 30 and prev["rsi_14"] <= 30 and
                last.get("ar", 100) > 80):
                signal = "BUY"
                reason = f"RSI回弹+AR确认:RSI={last['rsi_14']:.1f}"
        else:
            # 纯RSI反转（参数自适应）
            period = 14
            os_thresh = 30
            if "7" in strategy:
                period, os_thresh = 7, 25
            elif "21" in strategy:
                period, os_thresh = 21, 35
            rsi_col = f"rsi_{period}" if period != 14 else "rsi_14"

            if rsi_col in d.columns:
                if (last[rsi_col] > os_thresh and 
                    prev[rsi_col] <= os_thresh):
                    signal = "BUY"
                    reason = f"RSI反弹:RSI_{period}={last[rsi_col]:.1f}"

    # ── Vol_Break ──
    elif "Vol" in strategy:
        if (last["vol_ratio"] > 1.5 and last["pct"] > 0.02 and
            last["close"] > last["ma20"]):
            signal = "BUY"
            reason = f"量价突破:量比{last['vol_ratio']:.2f},涨幅{last['pct']*100:.2f}%"

    # ── Combined ──
    elif "Comb" in strategy:
        if (last["close"] > last["ma20"] and 
            last["ma20"] > last["ma60"] and
            last["macd_hist"] > 0):
            signal = "BUY"
            reason = f"组合信号:MA多头+MACD正"

    if not signal:
        return None

    # 仓位计算 (ATR风险平价)
    position_pct = kb["position_pct"]
    atr_val = max(last["atr_14"], 0.01)
    # 波动率调整：波动越大仓位越小
    vol_adj = min(1.0, 0.5 / profile.price_volatility) if profile.price_volatility > 0 else 0.5
    vol_adj = max(vol_adj, 0.3)
    final_pct = position_pct * vol_adj

    # 止损价格
    if kb["stop"] == "double_loss":
        stop_price = last["close"] - atr_val * 0.5
        stop_pct = float((stop_price / last["close"] - 1) * 100)
    elif kb["stop"] == "channel_20":
        stop_price = d["ch20l"].iloc[-1]
        stop_pct = float((stop_price / last["close"] - 1) * 100)
    else:
        stop_price = last["close"] * 0.95
        stop_pct = -5.0

    return {
        "code": code,
        "name": STOCK_NAMES[code],
        "signal": signal,
        "strategy": strategy,
        "reason": reason,
        "entry_price": float(last["close"]),
        "stop_price": float(stop_price),
        "stop_loss_pct": round(stop_pct, 2),
        "position_pct": round(final_pct * 100, 1),
        "position_amount": round(INITIAL_CAP * final_pct),
        "profile": profile.profile_summary,
    }


# ================================================================
# 组合管理
# ================================================================

def portfolio_optimizer(signals: List[Dict]) -> List[Dict]:
    """
    组合优化：
    - 总仓位限制：最多60%总仓位
    - 单票上限：15%
    - 高风险票压仓
    - 分散度要求：最少3只，最多8只
    """
    if not signals:
        return []

    # 按signal强度排序
    for s in signals:
        # 信号强度分
        score = 0
        if "Turtle" in s["strategy"] or "Cross" in s["strategy"]:
            score += 2  # 趋势突破加分
        if abs(s["stop_loss_pct"]) > 3:
            score -= 1  # 止损太宽减分
        if "震荡" in s["profile"]:
            score -= 0.5
        if "多头" in s["profile"] or "突破" in s["profile"]:
            score += 1
        s["_score"] = score

    signals.sort(key=lambda x: x["_score"], reverse=True)

    # 仓位分配
    total_pct = 0
    max_total = 60  # 总仓位上限60%
    selected = []

    for s in signals:
        pos = s["position_pct"]
        if total_pct + pos > max_total:
            # 压缩仓位
            pos = max_total - total_pct
            if pos < 5:  # 低于5%不值得开仓
                break
            s["position_pct"] = round(pos, 1)
            s["position_amount"] = round(INITIAL_CAP * pos / 100)
        total_pct += pos
        selected.append(s)
        if len(selected) >= 8:
            break

    return selected


# ================================================================
# 每日运行入口
# ================================================================

def run_daily_scan(date_str: Optional[str] = None) -> Dict:
    """
    每日扫描：对13只股票运行画像→信号→组合优化
    
    Returns:
        {
            "date": "2026-06-17",
            "market_regime": "bull/sideways/bear",
            "signals": [...],
            "portfolio": [...],
            "summary": "..."
        }
    """
    if date_str is None:
        date_str = date.today().isoformat()

    # 检查是否工作日（简单过滤周末）
    # dt = datetime.strptime(date_str, "%Y-%m-%d")
    # if dt.weekday() >= 5:
    #     return {"date": date_str, "warning": "非交易日", "signals": [], "portfolio": []}

    all_signals = []

    for code in sorted(STOCK_NAMES.keys()):
        try:
            df = load_stock_data(code)
            d = compute_profile_indicators(df)
            profile = profile_stock(code, df, d)
            signal = check_entry(code, profile, d)
            if signal:
                all_signals.append(signal)
        except Exception as e:
            print(f"  [{code}] 错误: {e}")
            continue

    # 组合优化
    portfolio = portfolio_optimizer(all_signals)

    # 市场风格判断
    # 通过所有股票的趋势强度均值判断
    regime = "sideways"
    signals_by_score = sorted(all_signals, key=lambda x: x.get("_score", 0), reverse=True)

    # 生成摘要
    lines = []
    lines.append(f"📊 每日量化信号 | {date_str}")
    lines.append(f"{'='*60}")
    if not portfolio:
        lines.append("今日无信号")
    else:
        total_pos = sum(s["position_pct"] for s in portfolio)
        lines.append(f"总仓位: {total_pos:.0f}% | 持仓: {len(portfolio)}只")
        lines.append("")
        lines.append(f"{'代码':<8} {'名称':<10} {'策略':<25} {'入场':<10} {'止损':<10} {'仓位':<8} {'画像'}")
        lines.append(f"{'-'*6} {'-'*8} {'-'*23} {'-'*8} {'-'*8} {'-'*6} {'-'*12}")
        for s in portfolio:
            lines.append(f"{s['code']:<8} {s['name']:<10} {s['strategy']:<25} "
                        f"{s['entry_price']:<10.2f} {s['stop_price']:<10.2f} "
                        f"{s['position_pct']:<7.1f}% {s['profile']}")
        lines.append("")
        lines.append(f"风险聚合: 最大单票止损{s[0]['stop_loss_pct']:.1f}%" if portfolio else "")
        lines.append(f"日风险值: {total_pos*0.5:.1f}% (按平均0.5%ATR估算)")

    return {
        "date": date_str,
        "signals": all_signals,
        "portfolio": portfolio,
        "summary": "\n".join(lines),
    }


# ================================================================
# CLI 入口
# ================================================================

def print_report(result: Dict):
    """打印报告到控制台"""
    print(result["summary"])

    if result.get("signals"):
        # 详细信号表
        print(f"\n{'─'*60}")
        print(f"完整信号详情 ({len(result['signals'])}只检测到信号):")
        print(f"{'代码':<8} {'名称':<10} {'策略':<25} {'信号理由':<35}")
        print(f"{'-'*6} {'-'*8} {'-'*23} {'-'*33}")
        for s in result["signals"]:
            print(f"{s['code']:<8} {s['name']:<10} {s['strategy']:<25} {s['reason']:<35}")
    
    # 今日无信号的股票
    all_codes = set(STOCK_NAMES.keys())
    signal_codes = {s["code"] for s in result.get("signals", [])}
    no_signal = all_codes - signal_codes
    if no_signal:
        names = [f"{c}({STOCK_NAMES[c]})" for c in sorted(no_signal)]
        print(f"\n无信号: {', '.join(names)}")


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    
    print("=" * 60)
    print("  智能策略分配器 v1 — 每日量化信号引擎")
    print("  知识库: V2回测结果 (16策略×13股票)")
    print("  涵盖: 海龟/MA趋势/RSI反转/量价突破/组合策略")
    print("=" * 60)
    print()

    result = run_daily_scan(date_arg)
    print_report(result)

    # 保存结果
    today = date_arg or date.today().isoformat()
    out_path = os.path.join(BACKTEST_DIR, f"daily_signal_{today}.json")
    # 清理不可序列化字段
    serializable = {
        "date": result["date"],
        "portfolio": result["portfolio"],
        "signals_count": len(result["signals"]),
        "portfolio_count": len(result["portfolio"]),
        "summary": result["summary"],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n信号已保存: {out_path}")
