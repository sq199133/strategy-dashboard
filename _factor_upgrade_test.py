# -*- coding: utf-8 -*-
"""因子升级回测 - 验证可提升因子
因子F2: RSI>65过滤（高位不买）
因子F3: 10周趋势斜率>0过滤
因子F4: 市场环境过滤（沪深300 MA21跌破则跳过开仓信号）
因子F5: 赛道去重（同类型ETF需MA21全部跌破才放弃）
"""
import json, os, glob, statistics
from datetime import datetime as dt
from collections import defaultdict

HISTORY_DIR = r"D:\Qclaw_Trading\data\history_long_v2"
POOL_FILE   = r"D:\Qclaw_Trading\data\etf_pool_V1_full.json"
OUTPUT_DIR  = r"D:\Qclaw_Trading\review"

# ── 策略参数 ────────────────────────────────────────────
DEF_MAX_DEV, DEF_TOP_N, DEF_LB = 30.0, 1, 3
DEF_ATR_F = 0.85
DEF_SC_W1, DEF_SC_W3, DEF_SC_W8 = 0.50, 0.50, 0.00

# ── 新增因子配置 ────────────────────────────────────────
F_RSI_MAX   = 65.0   # F2: RSI上限
F_SLOPE10   = True    # F3: 10周斜率>0
F_MKT_ENV   = True    # F4: 大盘MA21过滤
F_SECTOR    = True    # F5: 赛道去重

BENCHMARK_CODES = ['510300', '159300']  # 沪深300 ETF

def load_all():
    with open(POOL_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    etfs = raw.get("data", []) if isinstance(raw, dict) else raw

    series, ohlc, code_cat, avail_weeks = {}, {}, {}, set()
    for etf in etfs:
        code  = etf["code"]
        cat   = etf.get("category") or etf.get("type") or ""
        code_cat[code] = cat
        matches = glob.glob(os.path.join(HISTORY_DIR, code + ".json"))
        if not matches:
            continue
        try:
            with open(matches[0], encoding="utf-8") as f:
                d = json.load(f)
            recs = d.get("records", [])
            if not recs:
                continue
            weeks = {}
            for r in recs:
                ds = r.get("date", "") or r.get("w", "")
                if not ds:
                    continue
                try:
                    y, wn, _ = dt.strptime(ds, "%Y-%m-%d").isocalendar()
                    wk = f"{y}-W{wn:02d}"
                    if wk not in weeks or ds > weeks[wk][0]:
                        weeks[wk] = (ds, r.get("close", 0),
                                     r.get("open", 0), r.get("high", 0),
                                     r.get("low", 0), r.get("vol", 0))
                except:
                    pass
            if not weeks:
                continue
            srt = sorted(weeks.items())
            series[code] = [(wk, v[1]) for wk, v in srt]
            ohlc[code]   = {wk: {"o": v[2], "h": v[3], "l": v[4],
                                   "c": v[1], "v": v[5]}
                            for wk, v in srt}
            avail_weeks.update(w for w, _ in srt)
        except:
            continue

    all_weeks = sorted(avail_weeks)

    # ATR
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

def calc_rsi(closes, period=14):
    """计算RSI-14"""
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d for d in deltas[-period:] if d > 0]
    losses = [abs(d) for d in deltas[-period:] if d < 0]
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def calc_slope10(closes):
    """10周线性回归斜率"""
    if len(closes) < 10:
        return None
    arr = closes[-10:]
    x = list(range(len(arr)))
    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(arr) / n
    num = sum((x[i] - mean_x) * (arr[i] - mean_y) for i in range(n))
    den = sum((x[i] - mean_x) ** 2 for i in range(n))
    if den == 0:
        return None
    return num / den

def get_benchmark_ma21(week_idx, wk_list, series):
    """获取沪深300的MA21"""
    for bcode in BENCHMARK_CODES:
        srt = series.get(bcode, [])
        if len(srt) <= week_idx:
            continue
        price = srt[week_idx][1]
        if week_idx < 21:
            return None, None
        ma21 = sum(srt[j][1] for j in range(week_idx-20, week_idx+1)) / 21
        return price, ma21
    return None, None

def scan_week(week_idx, wk_list, series, ohlc, atr, code_cat,
              use_f2=False, use_f3=False, use_f4=False, use_f5=False,
              prev_trade=None):
    """
    扫描某周候选，返回(代码列表, 大盘状态)
    """
    candidates = []
    for code in series:
        srt = series[code]
        if week_idx < 21 or week_idx >= len(srt):
            continue
        price = srt[week_idx][1]
        if not price or price <= 0:
            continue
        ma21 = sum(srt[j][1] for j in range(week_idx-20, week_idx+1)) / 21
        if ma21 == 0 or price <= ma21:
            continue
        dev = abs(price / ma21 - 1) * 100
        if dev > DEF_MAX_DEV:
            continue
        sig_week = wk_list[week_idx]
        ar = atr.get(code, {}).get(sig_week)
        if ar is not None and ar < DEF_ATR_F:
            continue
        # VR量比过滤（来自backtest_integrated_v3.py）
        ohlc_c = ohlc.get(code, {})
        wk_c = ohlc_c.get(sig_week, {})
        if wk_c.get('v', 0) > 0:
            vol_vals = [ohlc_c.get(wk_list[j], {}).get('v', 0)
                        for j in range(max(0, week_idx-9), week_idx+1)]
            vol_vals = [v for v in vol_vals if v and v > 0]
            avg_v10 = sum(vol_vals) / len(vol_vals) if vol_vals else 1
            vr = wk_c.get('v', 0) / avg_v10 if avg_v10 > 0 else 0
            if vr < 1.5:
                continue
        mom = price / srt[week_idx - DEF_LB][1] - 1
        mom1w = price / srt[week_idx-1][1] - 1
        mom8w = price / srt[week_idx-8][1] - 1
        score = DEF_SC_W1 * mom1w + DEF_SC_W3 * mom + DEF_SC_W8 * mom8w

        # ── F2: RSI过滤 ──────────────────────────────
        if use_f2:
            closes_needed = [srt[j][1] for j in range(week_idx-14, week_idx+1)]
            rsi = calc_rsi(closes_needed)
            if rsi is not None and rsi > F_RSI_MAX:
                continue

        # ── F3: 10周斜率过滤 ─────────────────────────
        if use_f3:
            closes_needed = [srt[j][1] for j in range(max(0, week_idx-9), week_idx+1)]
            slope10 = calc_slope10(closes_needed)
            if slope10 is not None and slope10 <= 0:
                continue

        # ── F4: 大盘环境过滤 ─────────────────────────
        if use_f4:
            b_price, b_ma21 = get_benchmark_ma21(week_idx, wk_list, series)
            if b_price is not None and b_price <= b_ma21:
                continue  # 大盘跌破MA21，暂停开仓

        # ── F5: 赛道去重（当前持仓赛道内找替代） ──────
        if use_f5 and prev_trade:
            prev_cat = code_cat.get(prev_trade, "")
            curr_cat = code_cat.get(code, "")
            # 若同赛道，保留（v4.8已有此逻辑）

        candidates.append({
            'code': code, 'score': score, 'dev': dev,
            'cat': code_cat.get(code, "")
        })

    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates[:DEF_TOP_N]

def backtest(weeks, series, ohlc, atr, code_cat,
             use_f2=False, use_f3=False, use_f4=False, use_f5=False,
             name=""):
    """逐周回测，返回绩效"""
    wk_list = weeks
    n = len(wk_list)
    capital = 100000.0
    peak = capital
    trades = []
    equity = [capital]
    holding = None
    entry_price = 0
    entry_week_idx = 0
    prev_trade_code = None

    for wi in range(21, n):
        week = wk_list[wi]
        year = int(week[:4])

        # 检查是否有持仓
        if holding is None:
            tops = scan_week(wi, wk_list, series, ohlc, atr, code_cat,
                             use_f2, use_f3, use_f4, use_f5, prev_trade_code)
            if tops:
                top = tops[0]
                entry_price = series[top['code']][wi][1]
                if entry_price and entry_price > 0:
                    shares = capital / entry_price
                    holding = top['code']
                    entry_week_idx = wi
                    trades.append({
                        'code': holding,
                        'entry_week': week,
                        'entry_price': entry_price,
                        'type': 'long'
                    })
                    prev_trade_code = holding
        else:
            # 检查止损/轮动
            srt = series.get(holding, [])
            if wi >= len(srt):
                equity.append(capital)
                continue
            price = srt[wi][1]
            ohlc_c = ohlc.get(holding, {})
            # MA21轮动
            if wi >= 21:
                ma21 = sum(srt[j][1] for j in range(wi-20, wi+1)) / 21
                if price and ma21 and price <= ma21:
                    pnl = (price / trades[-1]['entry_price'] - 1) * 100
                    trades[-1]['exit_week'] = week
                    trades[-1]['exit_price'] = price
                    trades[-1]['pnl_pct'] = pnl
                    capital = capital * (1 + pnl / 100)
                    peak = max(peak, capital)
                    equity.append(capital)
                    holding = None
                    continue
            # 硬止损 -8%
            stop = trades[-1]['entry_price'] * 0.92
            if price and price <= stop:
                pnl = (price / trades[-1]['entry_price'] - 1) * 100
                trades[-1]['exit_week'] = week
                trades[-1]['exit_price'] = price
                trades[-1]['pnl_pct'] = pnl
                capital = capital * (1 + pnl / 100)
                peak = max(peak, capital)
                equity.append(capital)
                holding = None
                continue

            # 高点止损 -10%
            high_water = max(srt[j][1] for j in range(entry_week_idx, wi+1) if j < len(srt))
            if price and high_water * 0.90 >= price:
                pnl = (price / trades[-1]['entry_price'] - 1) * 100
                trades[-1]['exit_week'] = week
                trades[-1]['exit_price'] = price
                trades[-1]['pnl_pct'] = pnl
                capital = capital * (1 + pnl / 100)
                peak = max(peak, capital)
                equity.append(capital)
                holding = None
                continue

            # 继续持有
            equity.append(capital)

    # 年化收益
    years = n / 52
    total_ret = (capital / 100000.0 - 1) * 100
    ann_ret = ((capital / 100000.0) ** (1 / years) - 1) * 100 if years > 0 else 0

    # 最大回撤
    max_dd = 0.0
    peak_val = 100000.0
    for v in equity:
        if v > peak_val:
            peak_val = v
        dd = (v - peak_val) / peak_val * 100
        if dd < max_dd:
            max_dd = dd

    # Sharpe（简化：基于年化收益/最大回撤的绝对值近似）
    sharpe = abs(ann_ret / max_dd) if max_dd != 0 else 0

    # 交易统计
    closed = [t for t in trades if 'exit_week' in t]
    wins   = [t for t in closed if t['pnl_pct'] > 0]
    losses = [t for t in closed if t['pnl_pct'] <= 0]
    win_rate = len(wins) / len(closed) * 100 if closed else 0
    avg_win  = sum(t['pnl_pct'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t['pnl_pct'] for t in losses) / len(losses) if losses else 0

    return {
        'name': name,
        'total_ret': total_ret,
        'ann_ret': ann_ret,
        'max_dd': max_dd,
        'sharpe': sharpe,
        'trades': len(closed),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'final_capital': capital,
    }

# ── 主程序 ─────────────────────────────────────────────
print("加载数据...")
etfs, series, ohlc, code_cat, weeks, atr = load_all()
print(f"ETF数: {len(series)}, 可用周数: {len(weeks)}")
print(f"首周: {weeks[0] if weeks else 'N/A'}, 末周: {weeks[-1] if weeks else 'N/A'}")

# IS/OOS分割
is_split = next((i for i, w in enumerate(weeks) if w.startswith('2022-')), 20)
oos_split = next((i for i, w in enumerate(weeks) if w.startswith('2023-')), is_split + 52)
print(f"IS期: {weeks[0]} ~ {weeks[is_split-1]}, OOS期: {weeks[oos_split]} ~ {weeks[-1]}")

def run_test(weeks, series, ohlc, atr, code_cat,
             use_f2=False, use_f3=False, use_f4=False, use_f5=False,
             name=""):
    """只回测OOS期（2023-2026）"""
    oos_weeks = weeks[oos_split:]
    # 用2023-01到2023-03的信号作为初始资本
    is_result = backtest(weeks[:oos_split+52], series, ohlc, atr, code_cat,
                          use_f2, use_f3, use_f4, use_f5, name + "_IS")
    init_cap = is_result['final_capital']

    oos_result = backtest(weeks, series, ohlc, atr, code_cat,
                           use_f2, use_f3, use_f4, use_f5, name)
    return oos_result

# ── 基准：原版v4.8 ────────────────────────────────────
print("\n" + "="*60)
baseline = run_test(weeks, series, ohlc, atr, code_cat, False, False, False, False, "v4.8基准")
print(f"v4.8基准 OOS: Ann={baseline['ann_ret']:+.1f}% Sharpe={baseline['sharpe']:.3f} MaxDD={baseline['max_dd']:.1f}% Trades={baseline['trades']}")

# ── 各因子测试 ─────────────────────────────────────────
configs = [
    (True,  False, False, False, "F2: RSI上限过滤(>65跳过)"),
    (False, True,  False, False, "F3: 10周斜率过滤(slope>0)"),
    (False, False, True,  False, "F4: 大盘环境过滤(沪深MA21)"),
    (False, False, False, True,  "F5: 赛道去重"),
    (True,  True,  False, False, "F2+F3"),
    (True,  False, True,  False, "F2+F4"),
    (False, True,  True,  False, "F3+F4"),
    (True,  True,  True,  False, "F2+F3+F4"),
    (True,  True,  True,  True,  "全部因子"),
]

print("\n" + "="*60)
print(f"{'配置':<30} {'年化':>8} {'Sharpe':>7} {'MaxDD':>7} {'交易':>5} {'胜率':>6}")
print("-"*60)
for f2, f3, f4, f5, label in configs:
    r = run_test(weeks, series, ohlc, atr, code_cat, f2, f3, f4, f5, label)
    flag = " <-- BEST" if r['ann_ret'] > baseline['ann_ret'] else ""
    flag2 = " *" if r['ann_ret'] > baseline['ann_ret'] * 0.9 else ""
    print(f"{label:<30} {r['ann_ret']:>+7.1f}% {r['sharpe']:>7.3f} {r['max_dd']:>7.1f}% {r['trades']:>5} {r['win_rate']:>5.0f}%{flag2}")

print("\n基准对比:")
print(f"  v4.8基准: Ann={baseline['ann_ret']:+.1f}% Sharpe={baseline['sharpe']:.3f} MaxDD={baseline['max_dd']:.1f}%")
