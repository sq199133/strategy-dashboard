#!/usr/bin/env python3
"""基于2026-05-15数据，检查所有候选ETF的买入信号，决定周一买什么"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = r"D:\QClaw_Trading\data\history"

with open(r'D:\QClaw_Trading\virtual_portfolio_v2.json', 'r', encoding='utf-8') as f:
    portfolio = json.load(f)

def load_etf(code):
    for prefix in ['sh', 'sz']:
        path = os.path.join(DATA_DIR, f"{prefix}{code}.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f2:
                data = json.load(f2)
            if 'records' in data:
                df = __import__('pandas').DataFrame(data['records'])
                df['date'] = __import__('pandas').to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)
                for col in ['close', 'high', 'low']:
                    df[col] = df[col].astype(float)
                return df
    return None

def calc(df):
    df = df.copy()
    df['ma20'] = df['close'].rolling(20).mean()
    df['std20'] = df['close'].rolling(20).std()
    df['bb_u'] = df['ma20'] + 2 * df['std20']
    df['bb_l'] = df['ma20'] - 2 * df['std20']
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20l'] = df['close'].rolling(20).mean()
    df['high20'] = df['high'].rolling(20).max()
    df['low20'] = df['low'].rolling(20).min()
    return df

def check_buy(code, name, strat_name):
    df = load_etf(code)
    if df is None or len(df) < 26:
        return None
    
    df = calc(df)
    i = len(df) - 1
    
    latest_date = str(df['date'].iloc[i].date())
    c = float(df['close'].iloc[i])
    pc = float(df['close'].iloc[i-1])
    
    signal = False
    reason = ''
    
    if strat_name == '布林带突破':
        bb_u_prev = float(df['bb_u'].iloc[i-1])
        if pc <= bb_u_prev and c > bb_u_prev:
            signal = True
            reason = f"突破布林上轨(prev={bb_u_prev:.4f}, now={c:.4f})"
    elif strat_name == '趋势突破':
        high20_prev = float(df['high20'].iloc[i-1])
        if pc <= high20_prev and c > high20_prev:
            signal = True
            reason = f"突破20日高点(prev={high20_prev:.4f}, now={c:.4f})"
    elif strat_name == '均线交叉':
        ma5 = float(df['ma5'].iloc[i])
        ma20l = float(df['ma20l'].iloc[i])
        ma5_prev = float(df['ma5'].iloc[i-1])
        ma20l_prev = float(df['ma20l'].iloc[i-1])
        if ma5_prev <= ma20l_prev and ma5 > ma20l:
            signal = True
            reason = f"MA5金叉MA20(MA5={ma5:.4f} > MA20={ma20l:.4f})"
    
    if signal:
        return {
            'code': code, 'name': name, 'strategy': strat_name,
            'date': latest_date, 'close': c,
            'reason': reason
        }
    return None

print("="*70)
print("📊 基于2026-05-15（周五）数据的周一买入信号检测")
print("="*70)

all_signals = []

for strat_name, strat in portfolio['strategies'].items():
    held_codes = {p['code'] for p in strat['positions']}
    slots = 3 - len(strat['positions'])
    
    print(f"\n{'─'*70}")
    print(f"📂 【{strat_name}】已持仓: {len(strat['positions'])}只 | 空位: {slots}个 | 剩余现金: {strat['current_cash']:,.0f}元")
    print(f"{'代码':<8} {'名称':<16} {'周五收盘':>8} {'买入信号':<45} {'操作'}")
    print("-"*90)
    
    strat_signals = []
    for c in strat['candidates']:
        if c['code'] in held_codes:
            continue
        r = check_buy(c['code'], c['name'], strat_name)
        if r:
            strat_signals.append(r)
    
    # 优先年化高的
    strat_signals.sort(key=lambda x: c['annual_return'] if (c := next((c2 for c2 in strat['candidates'] if c2['code'] == x['code']), {})) else 0, reverse=True)
    
    # 按年化重排signal
    for sig in strat_signals:
        c2 = next((c3 for c3 in strat['candidates'] if c3['code'] == sig['code']), {})
        sig['annual_return'] = c2.get('annual_return', 0)
    strat_signals.sort(key=lambda x: x['annual_return'], reverse=True)
    
    if strat_signals:
        for sig in strat_signals:
            if slots > 0:
                print(f"  {sig['code']:<8} {sig['name']:<16} {sig['close']:>8.3f} → 🚀 {sig['reason']}")
                all_signals.append(sig)
                slots -= 1
            else:
                print(f"  {sig['code']:<8} {sig['name']:<16} {sig['close']:>8.3f} → ⏸  已满仓位")
    else:
        print(f"  （无买入信号）")

print(f"\n{'='*70}")
print(f"📋 周一（2026-05-18）操作汇总")
print(f"{'='*70}")
if all_signals:
    for sig in all_signals:
        shares = int(5556 / sig['close'] * 0.995)
        cost = shares * sig['close']
        print(f"  🚀 买入: {sig['strategy']} | {sig['code']} {sig['name']} | @{sig['close']:.3f} | {shares}股 | 成本约{cost:,.0f}元")
else:
    print("  无操作")
print()
for strat_name, strat in portfolio['strategies'].items():
    held = [f"{p['code']}({p['name']})" for p in strat['positions']]
    print(f"  {strat_name}: {' | '.join(held) if held else '空仓'}")