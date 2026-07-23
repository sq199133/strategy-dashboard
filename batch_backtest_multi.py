#!/usr/bin/env python3
"""
ETF虚拟盘 - 多策略并行批量回测
对每个ETF跑三策略全量对比，筛选各策略最优ETF
"""

import json, os, pandas as pd, numpy as np
from datetime import datetime

DATA_DIR = r"D:\QClaw_Trading\data\history"
POOL_FILE = r"D:\QClaw_Trading\data\etf_pool_V1_full.json"
INITIAL_CAPITAL = 16666.67  # 三策略各分1/3
STOP_LOSS = 0.08
TAKE_PROFIT = 0.15

def load_etf(code):
    for prefix in ['sh', 'sz']:
        path = os.path.join(DATA_DIR, f"{prefix}{code}.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'records' in data:
                df = pd.DataFrame(data['records'])
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)
                df['close'] = df['close'].astype(float)
                df['high'] = df['high'].astype(float)
                df['low'] = df['low'].astype(float)
                return df
    return None

def calc(df):
    df = df.copy()
    df['ma20'] = df['close'].rolling(20).mean()
    df['std20'] = df['close'].rolling(20).std()
    df['bb_u'] = df['ma20'] + 2*df['std20']
    df['bb_l'] = df['ma20'] - 2*df['std20']
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20l'] = df['close'].rolling(20).mean()
    df['high20'] = df['high'].rolling(20).max()
    df['low20'] = df['low'].rolling(20).min()
    return df

def bt(df, sig):
    """回测单个策略，返回统计数据"""
    if df is None or len(df) < 30: return None
    df = calc(df)
    cash, shares, entry = INITIAL_CAPITAL, 0, 0.0
    completed = []
    
    for i in range(25, len(df)):
        c = float(df['close'].iloc[i])
        pc = float(df['close'].iloc[i-1])
        pu, pl = float(df['bb_u'].iloc[i-1]), float(df['bb_l'].iloc[i-1])
        pcu, pcl = float(df['bb_u'].iloc[i]), float(df['bb_l'].iloc[i])
        ma5, pma5 = float(df['ma5'].iloc[i]), float(df['ma5'].iloc[i-1])
        ma20l, pma20l = float(df['ma20l'].iloc[i]), float(df['ma20l'].iloc[i-1])
        h20, ph20 = float(df['high20'].iloc[i]), float(df['high20'].iloc[i-1])
        l20, pl20 = float(df['low20'].iloc[i]), float(df['low20'].iloc[i-1])
        
        if shares == 0:
            # 买入检测
            if sig == '布林带突破':
                if pc <= pu and c > pu:
                    shares = int(cash / c * 0.995)
                    entry = c; cash -= shares * c
            elif sig == '趋势突破':
                if pc <= ph20 and c > ph20:
                    shares = int(cash / c * 0.995)
                    entry = c; cash -= shares * c
            elif sig == '均线交叉':
                if pma5 <= pma20l and ma5 > ma20l:
                    shares = int(cash / c * 0.995)
                    entry = c; cash -= shares * c
        else:
            # 卖出检测
            stop = entry * (1 - STOP_LOSS)
            tp = entry * (1 + TAKE_PROFIT)
            if sig == '布林带突破':
                if c < stop or c > tp or (pc >= pcl and c < pcl):
                    r = (c/entry-1)*100; cash += shares*c
                    completed.append(r); shares = 0; entry = 0.0
            elif sig == '趋势突破':
                if c < stop or c > tp or (pc >= pl20 and c < l20):
                    r = (c/entry-1)*100; cash += shares*c
                    completed.append(r); shares = 0; entry = 0.0
            elif sig == '均线交叉':
                if c < stop or c > tp or (pma5 >= pma20l and ma5 < ma20l):
                    r = (c/entry-1)*100; cash += shares*c
                    completed.append(r); shares = 0; entry = 0.0
    
    final = cash + shares * float(df['close'].iloc[-1])
    wins = [x for x in completed if x > 0]
    return {
        'total_return': round((final/INITIAL_CAPITAL-1)*100, 2),
        'final_value': round(final, 2),
        'trade_count': len(completed),
        'win_rate': round(len(wins)/len(completed)*100, 1) if completed else 0,
        'avg_return': round(np.mean(completed), 2) if completed else 0,
        'max_win': round(max(completed), 2) if completed else 0,
        'max_loss': round(min(completed), 2) if completed else 0,
    }

# 三策略各选ETF
strategies = ['布林带突破', '趋势突破', '均线交叉']
strat_files = {s: [] for s in strategies}

with open(POOL_FILE, 'r', encoding='utf-8') as f:
    pool = json.load(f)

print("开始批量回测...")
results_all = []
for item in pool['data']:
    code = item['code']
    name = item.get('name', code)
    cat = item.get('category', '未知')
    df = load_etf(code)
    if df is None: continue
    
    row = {'code': code, 'name': name, 'category': cat}
    for s in strategies:
        r = bt(df, s)
        row[s] = r
        if r and r['trade_count'] >= 3 and r['win_rate'] >= 50 and r['total_return'] > 0:
            row['s_result'] = r
            strat_files[s].append(row.copy())
    
    results_all.append(row)
    
    best_s, best_r = '', -999
    for s in strategies:
        if row.get(s) and row[s]['total_return'] > best_r:
            best_r = row[s]['total_return']; best_s = s
    print(f"  {code} {name}: {best_s} {best_r:+.1f}%")

# 各策略取最优（交易>=3, 胜>=50%, 去重类别）
selected = {}
for s in strategies:
    candidates = strat_files[s]
    candidates.sort(key=lambda x: x[s]['total_return'], reverse=True)
    
    chosen = []
    cats_used = set()
    for c in candidates:
        cat = c['category'] or '其他'
        if cat not in cats_used and len(chosen) < 3:
            chosen.append(c)
            cats_used.add(cat)
    
    selected[s] = chosen

print("\n三策略精选结果：")
for s, etfs in selected.items():
    print(f"\n【{s}】")
    for e in etfs:
        r = e[s]
        print(f"  {e['code']} {e['name']} | 收益{r['total_return']:+.1f}% | 胜率{r['win_rate']:.0f}% | 交易{r['trade_count']}次")

# 保存结果
output = {
    'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'strategy_selected': {s: [
        {'code': e['code'], 'name': e['name'], 'category': e['category'], **e[s]}
        for e in etfs
    ] for s, etfs in selected.items()},
    'all_results': results_all
}
with open(r"D:\QClaw_Trading\data\multi_strategy_candidates.json", 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print("\n结果已保存到 multi_strategy_candidates.json")