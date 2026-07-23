# -*- coding: utf-8 -*-
"""
回测对比：赛道去重 vs 无去重
v4.6.2 - 放宽数据要求
只要有足够ETF（>100只）有数据的日期就进行回测
"""

import json
import os
from datetime import datetime
from collections import defaultdict
import numpy as np

# ============ 核心参数 ============
MA_S = 5
MA_L = 21
ATR_RATIO = 0.85
DEV_LIMIT = 0.15
VOL_RATIO_LIMIT = 1.5
SCORE_W1, SCORE_W3, SCORE_W8 = 0.4, 0.4, 0.2
C_BONUS = 0.02
B1_BONUS = 0.00

# 止损参数
COST_STOP = 0.92
HIGH_STOP = 0.90

ETF_POOL_PATH = r"D:\QClaw_Trading\data\etf_pool_V1_full.json"
HISTORY_DIR = r"D:\QClaw_Trading\data\history_long_v2"
OUTPUT_DIR = r"D:\QClaw_Trading\review"

def load_etf_pool():
    with open(ETF_POOL_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    code_to_cat = {}
    for item in data['data']:
        code = item['code']
        cat = item.get('category', '').strip() or "未分类"
        code_to_cat[code] = cat
    
    return code_to_cat

def load_history_data(code_to_cat):
    all_data = {}
    
    files = [f for f in os.listdir(HISTORY_DIR) if f.endswith('.json')]
    
    for fname in files:
        code = fname.replace('.json', '')
        if code not in code_to_cat:
            continue
            
        fpath = os.path.join(HISTORY_DIR, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            records = data.get('records', [])
            if len(records) < 50:
                continue
            
            for r in records:
                r['code'] = code
            
            all_data[code] = records
                
        except Exception as e:
            continue
    
    print(f"加载 {len(all_data)} 只ETF")
    return all_data

def calc_ma(prices, window):
    if len(prices) < window:
        return None
    return np.mean(prices[-window:])

def calc_atr(highs, lows, closes, window):
    if len(closes) < window + 1:
        return None
    
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], 
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1]))
        trs.append(tr)
    
    if len(trs) < window:
        return None
    
    return np.mean(trs[-window:])

def detect_c_pattern(records, idx):
    if idx < 5:
        return False
    
    r = records[idx]
    prev = records[idx-1]
    
    upper_shadow = r['high'] - max(r['close'], r['open'])
    body = abs(r['close'] - r['open'])
    
    cond1 = upper_shadow / r['open'] >= 0.025
    cond2 = body / r['open'] < 0.02
    cond3 = r['close'] > prev['close']
    
    return cond1 and cond2 and cond3

def detect_b1_pattern(records, idx):
    if idx < 3:
        return False
    
    r = records[idx]
    prev1 = records[idx-1]
    prev2 = records[idx-2]
    
    cond1 = r['close'] > r['open'] and prev1['close'] > prev1['open'] and prev2['close'] > prev2['open']
    cond2 = r['close'] > prev1['close'] and prev1['close'] > prev2['close']
    
    return cond1 and cond2

def calc_signals(records, idx):
    """计算信号"""
    if idx < MA_L + 10:
        return None
    
    closes = [r['close'] for r in records[:idx+1]]
    highs = [r['high'] for r in records[:idx+1]]
    lows = [r['low'] for r in records[:idx+1]]
    vols = [r['vol'] for r in records[:idx+1]]
    current = records[idx]
    
    # MA
    ma5 = calc_ma(closes, MA_S)
    ma21 = calc_ma(closes, MA_L)
    
    if ma5 is None or ma21 is None:
        return None
    
    # 趋势过滤
    if not (current['close'] > ma5 > ma21):
        return None
    
    # ATR过滤
    atr14 = calc_atr(highs, lows, closes, 14)
    atr21 = calc_atr(highs, lows, closes, 21)
    
    if atr14 is not None and atr21 is not None:
        if atr14 / atr21 >= ATR_RATIO:
            return None
    
    # 偏离度
    dev = (current['close'] - ma21) / ma21
    if abs(dev) > DEV_LIMIT:
        return None
    
    # 量比
    avg_vol = np.mean(vols[-4:-1])
    vol_ratio = current['vol'] / avg_vol if avg_vol > 0 else 1.0
    if vol_ratio > VOL_RATIO_LIMIT:
        return None
    
    # 动量
    mom1w = (closes[-1] - closes[-2]) / closes[-2] if closes[-2] > 0 else 0
    mom3w = (closes[-1] - closes[-4]) / closes[-4] if len(closes) >= 4 and closes[-4] > 0 else 0
    mom8w = (closes[-1] - closes[-9]) / closes[-9] if len(closes) >= 9 and closes[-9] > 0 else 0
    
    score = SCORE_W1 * mom1w + SCORE_W3 * mom3w + SCORE_W8 * mom8w
    
    c_pattern = detect_c_pattern(records, idx)
    b1_pattern = detect_b1_pattern(records, idx)
    
    adj_score = score
    if c_pattern:
        adj_score += C_BONUS
    if b1_pattern:
        adj_score += B1_BONUS
    
    return {
        'code': current.get('code', ''),
        'close': current['close'],
        'open': current['open'],
        'score': score,
        'adj_score': adj_score,
        'date': current['date']
    }

def select_targets_dedup(signals, code_to_cat, top_n=3):
    if not signals:
        return []
    
    sorted_signals = sorted(signals, key=lambda x: x['adj_score'], reverse=True)
    
    selected = []
    seen_cats = set()
    
    for sig in sorted_signals:
        code = sig['code']
        cat = code_to_cat.get(code, '未分类')
        
        if cat not in seen_cats:
            selected.append(sig)
            seen_cats.add(cat)
        
        if len(selected) >= top_n:
            break
    
    return selected

def select_targets_no_dedup(signals, top_n=3):
    if not signals:
        return []
    
    sorted_signals = sorted(signals, key=lambda x: x['adj_score'], reverse=True)
    return sorted_signals[:top_n]

def run_backtest(all_data, code_to_cat, use_dedup=True):
    print(f"\n{'='*60}")
    print(f"回测: {'有去重' if use_dedup else '无去重'}")
    print(f"{'='*60}")
    
    # 统计每个日期有多少ETF有数据
    date_etf_count = defaultdict(int)
    date_to_price = {}
    
    for code, records in all_data.items():
        for r in records:
            date = r['date']
            date_etf_count[date] += 1
            if date not in date_to_price:
                date_to_price[date] = {}
            date_to_price[date][code] = {'close': r['close'], 'open': r['open']}
    
    # 筛选至少有100只ETF有数据的日期
    valid_dates = sorted([d for d, count in date_etf_count.items() 
                         if count >= 100 and d >= '2014-01-01' and d <= '2026-06-30'])
    
    print(f"有效调仓日期: {len(valid_dates)} 个")
    if valid_dates:
        print(f"周期: {valid_dates[0]} 到 {valid_dates[-1]}")
    
    # 初始化
    cash = 1.0
    portfolio = {}
    equity_curve = []
    trades = []
    
    for i, date in enumerate(valid_dates):
        current_prices = date_to_price.get(date, {})
        
        # 计算净值
        portfolio_value = cash
        for code, pos in portfolio.items():
            if code in current_prices:
                portfolio_value += pos['shares'] * current_prices[code]['open']
        
        equity_curve.append({'date': date, 'value': portfolio_value})
        
        # 止损检查
        to_sell = []
        for code, pos in list(portfolio.items()):
            if code in current_prices:
                close_price = current_prices[code]['close']
                
                if close_price > pos['high_price']:
                    pos['high_price'] = close_price
                
                if close_price <= pos['buy_price'] * COST_STOP:
                    to_sell.append((code, 'cost_stop'))
                elif close_price <= pos['high_price'] * HIGH_STOP:
                    to_sell.append((code, 'high_stop'))
        
        for code, reason in to_sell:
            pos = portfolio[code]
            if i + 1 < len(valid_dates):
                next_date = valid_dates[i + 1]
                next_prices = date_to_price.get(next_date, {})
                sell_price = next_prices.get(code, {}).get('open', pos['buy_price'])
            else:
                sell_price = current_prices.get(code, {}).get('close', pos['buy_price'])
            
            sell_value = pos['shares'] * sell_price
            cash += sell_value
            
            profit_rate = (sell_price - pos['buy_price']) / pos['buy_price']
            trades.append({
                'type': 'sell', 'code': code, 'date': date,
                'reason': reason, 'profit_rate': profit_rate
            })
            
            del portfolio[code]
        
        # 计算信号
        signals = []
        for code, records in all_data.items():
            idx = None
            for j, r in enumerate(records):
                if r['date'] == date:
                    idx = j
                    break
            
            if idx is not None:
                sig = calc_signals(records, idx)
                if sig:
                    signals.append(sig)
        
        # 选择目标
        if use_dedup:
            targets = select_targets_dedup(signals, code_to_cat, top_n=3)
        else:
            targets = select_targets_no_dedup(signals, top_n=3)
        
        target_codes = {t['code'] for t in targets}
        
        # 卖出不在目标中的
        for code in list(portfolio.keys()):
            if code not in target_codes:
                pos = portfolio[code]
                if i + 1 < len(valid_dates):
                    next_date = valid_dates[i + 1]
                    next_prices = date_to_price.get(next_date, {})
                    sell_price = next_prices.get(code, {}).get('open', pos['buy_price'])
                else:
                    sell_price = current_prices.get(code, {}).get('close', pos['buy_price'])
                
                cash += pos['shares'] * sell_price
                
                profit_rate = (sell_price - pos['buy_price']) / pos['buy_price']
                trades.append({
                    'type': 'sell', 'code': code, 'date': date,
                    'reason': 'rebalance', 'profit_rate': profit_rate
                })
                
                del portfolio[code]
        
        # 买入
        if targets and i + 1 < len(valid_dates):
            next_date = valid_dates[i + 1]
            next_prices = date_to_price.get(next_date, {})
            
            n_to_buy = len([t for t in targets if t['code'] not in portfolio])
            
            if n_to_buy > 0:
                total_assets = cash + sum(
                    portfolio[c]['shares'] * next_prices.get(c, {}).get('open', 0) 
                    for c in portfolio
                )
                target_value = total_assets / 3
                
                for target in targets:
                    code = target['code']
                    if code not in portfolio and code in next_prices:
                        buy_price = next_prices[code]['open']
                        shares = min(cash * 0.95, target_value) / buy_price
                        
                        if shares > 0:
                            cost = shares * buy_price
                            cash -= cost
                            
                            portfolio[code] = {
                                'buy_price': buy_price,
                                'high_price': buy_price,
                                'shares': shares
                            }
                            
                            trades.append({
                                'type': 'buy', 'code': code, 
                                'date': next_date, 'price': buy_price
                            })
    
    # 最终净值
    if valid_dates:
        last_date = valid_dates[-1]
        last_prices = date_to_price.get(last_date, {})
        
        final_value = cash
        for code, pos in portfolio.items():
            if code in last_prices:
                final_value += pos['shares'] * last_prices[code]['close']
            else:
                final_value += pos['shares'] * pos['buy_price']
    else:
        final_value = cash
    
    equity_curve.append({'date': valid_dates[-1] if valid_dates else '2026-06-30', 
                         'value': final_value})
    
    # 统计
    total_return = final_value - 1.0
    
    max_value = 1.0
    max_dd = 0
    for eq in equity_curve:
        if eq['value'] > max_value:
            max_value = eq['value']
        dd = (eq['value'] - max_value) / max_value
        if dd < max_dd:
            max_dd = dd
    
    if len(equity_curve) > 1:
        start_date = equity_curve[0]['date']
        end_date = equity_curve[-1]['date']
        days = (datetime.strptime(end_date, '%Y-%m-%d') - 
                datetime.strptime(start_date, '%Y-%m-%d')).days
        years = max(days / 365.25, 0.1)
        ann_return = total_return / years
    else:
        ann_return = 0
        years = 1
    
    if len(equity_curve) > 10:
        values = [eq['value'] for eq in equity_curve]
        returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values))]
        if returns and np.std(returns) > 0:
            mean_ret = np.mean(returns)
            std_ret = np.std(returns)
            sharpe = mean_ret / std_ret * np.sqrt(52)
        else:
            sharpe = 0
    else:
        sharpe = 0
    
    sell_trades = [t for t in trades if t['type'] == 'sell']
    win_trades = [t for t in sell_trades if t.get('profit_rate', 0) > 0]
    win_rate = len(win_trades) / len(sell_trades) if sell_trades else 0
    
    yearly = {}
    for eq in equity_curve:
        year = eq['date'][:4]
        if year not in yearly:
            yearly[year] = []
        yearly[year].append(eq['value'])
    
    yearly_stats = {}
    prev_year_value = 1.0
    for year in sorted(yearly.keys()):
        values = yearly[year]
        if values:
            year_return = (values[-1] / prev_year_value) - 1
            yearly_stats[year] = round(year_return, 4)
            prev_year_value = values[-1]
    
    return {
        'ann_return': round(ann_return, 4),
        'total_return': round(total_return, 4),
        'dd_max': round(max_dd, 4),
        'sharpe': round(sharpe, 4),
        'n_trades': len(trades),
        'win_rate': round(win_rate, 4),
        'yearly': yearly_stats,
        'final_value': round(final_value, 4),
        'n_rebalance_dates': len(valid_dates)
    }

def main():
    print("="*60)
    print("回测对比：赛道去重 vs 无去重 (v4.6.2)")
    print("="*60)
    
    code_to_cat = load_etf_pool()
    all_data = load_history_data(code_to_cat)
    
    result_with_dedup = run_backtest(all_data, code_to_cat, use_dedup=True)
    result_without_dedup = run_backtest(all_data, code_to_cat, use_dedup=False)
    
    result = {
        'with_dedup': result_with_dedup,
        'without_dedup': result_without_dedup,
        'config': {
            'MA_S': MA_S, 'MA_L': MA_L,
            'ATR_RATIO': ATR_RATIO, 'DEV_LIMIT': DEV_LIMIT,
            'VOL_RATIO_LIMIT': VOL_RATIO_LIMIT,
            'SCORE_W': [SCORE_W1, SCORE_W3, SCORE_W8],
            'C_BONUS': C_BONUS, 'B1_BONUS': B1_BONUS,
            'COST_STOP': COST_STOP, 'HIGH_STOP': HIGH_STOP
        },
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_file = os.path.join(OUTPUT_DIR, 
                               f"dedup_compare_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存: {output_file}")
    
    # 输出关键数字
    print("\n" + "="*60)
    print("关键数字对比")
    print("="*60)
    print(f"{'指标':<20} {'有去重':>15} {'无去重':>15} {'差异':>15}")
    print("-"*60)
    print(f"{'年化收益':<20} {result_with_dedup['ann_return']:>14.2%} {result_without_dedup['ann_return']:>14.2%} {result_with_dedup['ann_return']-result_without_dedup['ann_return']:>14.2%}")
    print(f"{'总收益':<20} {result_with_dedup['total_return']:>14.2%} {result_without_dedup['total_return']:>14.2%} {result_with_dedup['total_return']-result_without_dedup['total_return']:>14.2%}")
    print(f"{'最大回撤':<20} {result_with_dedup['dd_max']:>14.2%} {result_without_dedup['dd_max']:>14.2%} {result_with_dedup['dd_max']-result_without_dedup['dd_max']:>14.2%}")
    print(f"{'夏普比率':<20} {result_with_dedup['sharpe']:>15.3f} {result_without_dedup['sharpe']:>15.3f} {result_with_dedup['sharpe']-result_without_dedup['sharpe']:>15.3f}")
    print(f"{'交易次数':<20} {result_with_dedup['n_trades']:>15d} {result_without_dedup['n_trades']:>15d} {result_with_dedup['n_trades']-result_without_dedup['n_trades']:>15d}")
    print(f"{'胜率':<20} {result_with_dedup['win_rate']:>14.2%} {result_without_dedup['win_rate']:>14.2%} {result_with_dedup['win_rate']-result_without_dedup['win_rate']:>14.2%}")

if __name__ == '__main__':
    main()
