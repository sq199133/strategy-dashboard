"""
MACD卖出规则对比回测
对比6种卖出规则在MA20确认持仓的情况下的表现
"""

import json
import requests
from datetime import datetime, timedelta

# 获取数据
def get_kline(secid, days=2000):
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={secid},day,,,{days},qfq"
    resp = requests.get(url, timeout=15)
    data = resp.json()
    klines = data.get('data', {}).get(secid, {}).get('qfqday', [])
    return klines

def parse_klines(klines):
    result = []
    for k in klines:
        result.append({
            'date': k[0],
            'open': float(k[1]),
            'close': float(k[2]),
            'high': float(k[3]),
            'low': float(k[4]),
            'vol': float(k[5])
        })
    return result

def calc_ma(prices, n):
    ma = []
    for i in range(len(prices)):
        if i < n - 1:
            ma.append(None)
        else:
            ma.append(sum(prices[i-n+1:i+1]) / n)
    return ma

def calc_ema(prices, n):
    k = 2 / (n + 1)
    ema = []
    for i in range(len(prices)):
        if i < n - 1:
            ema.append(None)
        elif i == n - 1:
            ema.append(sum(prices[:n]) / n)
        else:
            ema.append(prices[i] * k + ema[i-1] * (1 - k))
    return ema

def calc_macd(prices):
    ema12 = calc_ema(prices, 12)
    ema26 = calc_ema(prices, 26)
    dif = [ema12[i] - ema26[i] if ema12[i] and ema26[i] else None for i in range(len(prices))]
    dea = calc_ema([d for d in dif if d is not None], 9)
    # 对齐dea到dif的长度
    dea_aligned = [None] * (len(dif) - len(dea)) + dea
    hist = []
    hist_idx = 0
    for i in range(len(dif)):
        if dif[i] is not None and dea_aligned[i] is not None:
            hist.append((dif[i] - dea_aligned[i]) * 2)
            hist_idx += 1
        else:
            hist.append(None)
    return {'dif': dif, 'dea': dea_aligned, 'hist': hist}

def run_backtest(data, sell_rule):
    """
    sell_rule: 
    1 = only MA20 break
    2 = MACD dead cross
    3 = MACD hist turns green
    4 = MACD top divergence
    5 = MACD dead cross AND hist turns green
    6 = MACD dead cross OR hist turns green
    """
    capital = 100000
    position = 0
    avg_cost = 0
    trades = []
    equity_curve = []
    peak = capital
    max_dd = 0
    
    for i in range(65, len(data)):
        closes = [d['close'] for d in data[:i+1]]
        prices = closes  # alias
        price = prices[-1]
        
        ma20 = calc_ma(closes, 20)
        ma20_cur = ma20[-1]
        ma20_prev = ma20[-2]
        
        macd = calc_macd(closes)
        dif = macd['dif']
        dea = macd['dea']
        hist = macd['hist']
        
        # Skip if insufficient data
        if None in [ma20_cur, dif[-2], dea[-2], hist[-2]]:
            equity_curve.append(capital + position * price)
            continue
        
        # Current state
        price_above_ma20 = price > ma20_cur
        dif_cur = dif[-2]
        dea_cur = dea[-2]
        hist_cur = hist[-2]
        hist_prev = hist[-3] if len(hist) > 2 else 0
        
        # Buy: MA20 above, MA20 rising, MACD golden cross or hist positive
        golden_cross = dif[-3] <= dea[-3] and dif_cur > dea_cur
        
        if position == 0:
            if (price_above_ma20 and 
                ma20_cur >= ma20_prev and  # MA20 not falling
                (golden_cross or hist_cur > 0)):
                shares = int(capital * 0.6 / price)
                if shares > 0:
                    avg_cost = price
                    position = shares
                    capital = capital - shares * price
                    trades.append(('BUY', data[i]['date'], price, shares))
        
        # Sell logic
        elif position > 0:
            should_sell = False
            reason = ""
            
            # Common: price breaks MA20
            if not price_above_ma20:
                should_sell = True
                reason = "MA20跌破"
            
            # Check different MACD rules (only if price still above MA20)
            else:
                dead_cross = dif[-3] >= dea[-3] and dif_cur < dea_cur
                hist_turns_green = hist_prev > 0 and hist_cur <= 0
                
                # Check for top divergence
                top_div = False
                if len(closes) > 20:
                    recent_highs = [closes[j] for j in range(len(closes)-20, len(closes))]
                    max_price = max(recent_highs)
                    recent_difs = [dif[j] for j in range(len(dif)-20, len(dif)-5) if dif[j] is not None]
                    max_dif = max(recent_difs) if recent_difs else 0
                    if price >= max_price * 0.98 and dif_cur < max_dif * 0.9:
                        top_div = True
                
                if sell_rule == 1:
                    pass  # Only MA20, already handled above
                elif sell_rule == 2:
                    if dead_cross:
                        should_sell = True
                        reason = "MACD死叉"
                elif sell_rule == 3:
                    if hist_turns_green:
                        should_sell = True
                        reason = "红柱转绿"
                elif sell_rule == 4:
                    if top_div:
                        should_sell = True
                        reason = "MACD顶背离"
                elif sell_rule == 5:
                    if dead_cross and hist_turns_green:
                        should_sell = True
                        reason = "MACD死叉+红柱转绿"
                elif sell_rule == 6:
                    if dead_cross or hist_turns_green:
                        should_sell = True
                        reason = "MACD死叉OR红柱转绿"
            
            if should_sell:
                capital = capital + position * price
                pnl_pct = (price - avg_cost) / avg_cost * 100
                trades.append(('SELL', data[i]['date'], price, position, pnl_pct, reason))
                position = 0
                avg_cost = 0
        
        # Equity tracking
        equity = capital + position * price
        equity_curve.append(equity)
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100
        if dd > max_dd:
            max_dd = dd
    
    # Force close at end
    if position > 0:
        price = data[-1]['close']
        capital = capital + position * price
        trades.append(('SELL', data[-1]['date'], price, position, (price - avg_cost) / avg_cost * 100, 'END'))
    
    final_value = capital
    total_return = (final_value - 100000) / 100000 * 100
    years = len(data) / 252
    cagr = (final_value / 100000) ** (1/years) - 1 if years > 0 else 0
    
    return {
        'final_value': final_value,
        'total_return': total_return,
        'cagr': cagr * 100,
        'max_dd': max_dd,
        'trades': len([t for t in trades if t[0] == 'BUY']),
        'equity_curve': equity_curve
    }

def main():
    print("="*70)
    print("MACD卖出规则对比回测 | 沪深300ETF | 2018-2026")
    print("="*70)
    
    # Get data
    print("\n正在获取数据...")
    klines = get_kline('sh510300', 2000)
    data = parse_klines(klines)
    # Filter from 2018
    data = [d for d in data if d['date'] >= '2018-01-01']
    print(f"数据: {len(data)}条 ({data[0]['date']} ~ {data[-1]['date']})")
    
    # Run backtests
    rules = [
        (1, "仅MA20跌破"),
        (2, "MACD死叉"),
        (3, "MACD红柱转绿"),
        (4, "MACD顶背离"),
        (5, "MACD死叉+红柱转绿(AND)"),
        (6, "MACD死叉OR红柱转绿(OR)"),
    ]
    
    results = []
    for rule_id, rule_name in rules:
        r = run_backtest(data, rule_id)
        results.append((rule_id, rule_name, r))
        print(f"  {rule_name}: 收益{r['total_return']:.1f}% 年化{r['cagr']:.1f}% 回撤{r['max_dd']:.1f}% 交易{r['trades']}次")
    
    # Buy & Hold benchmark
    bh_return = (data[-1]['close'] / data[0]['close'] - 1) * 100
    print(f"\n  买入持有: 收益{bh_return:.1f}%")
    
    print("\n" + "="*70)
    print("结果汇总")
    print("="*70)
    
    # Sort by total return
    results.sort(key=lambda x: x[2]['total_return'], reverse=True)
    
    print(f"\n{'排名':<4} {'规则':<25} {'总收益':<10} {'年化':<8} {'回撤':<8} {'交易次数':<8}")
    print("-"*70)
    for i, (rid, name, r) in enumerate(results, 1):
        print(f"{i:<4} {name:<25} {r['total_return']:>7.1f}% {r['cagr']:>6.1f}% {r['max_dd']:>6.1f}% {r['trades']:>6}次")
    
    # Save results
    output = {
        'date_range': f"{data[0]['date']} ~ {data[-1]['date']}",
        'results': [{'rule_id': r[0], 'rule_name': r[1], **r[2]} for r in results],
        'buyhold': bh_return
    }
    
    with open('D:/QClaw_Trading/data/macd_sell_comparison.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print("\n[OK] 结果已保存到 macd_sell_comparison.json")
    
    # Analysis
    print("\n" + "="*70)
    print("分析结论")
    print("="*70)
    
    best = results[0]
    print(f"\n1. 最高收益: {best[1]}，总收益 {best[2]['total_return']:.1f}%，年化 {best[2]['cagr']:.1f}%")
    print(f"2. 最低回撤: {min(results, key=lambda x:x[2]['max_dd'])[1]}，回撤 {min(results, key=lambda x:x[2]['max_dd'])[2]['max_dd']:.1f}%")
    print(f"3. 最少交易: {min(results, key=lambda x:x[2]['trades'])[1]}，{min(results, key=lambda x:x[2]['trades'])[2]['trades']}次")

if __name__ == '__main__':
    main()
