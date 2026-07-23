#!/usr/bin/env python3
"""
ETF虚拟盘 - 全量批量回测筛选 v4
- 全量标的池（etf_pool_V1_full.json）
- 三策略独立起始期回测
- 筛选条件：年化>=10% 且 胜率>=45%
- 分类输出三策略候选池
"""

import json, os, pandas as pd, numpy as np
from datetime import datetime

DATA_DIR = r"D:\QClaw_Trading\data\history"
POOL_FILE = r"D:\QClaw_Trading\data\etf_pool_V1_full.json"
INITIAL_PER_ETF = 16667.0
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

def backtest(code, name, strat_name):
    df = load_etf(code)
    if df is None or len(df) < 26:
        return None
    
    df = calc(df)
    
    cash = INITIAL_PER_ETF
    shares = 0
    entry = 0
    trades = []
    
    for i in range(25, len(df)):
        c = float(df['close'].iloc[i])
        
        # 卖出检查
        if shares > 0:
            should_sell = False
            reason = ''
            if c < entry * (1 - STOP_LOSS):
                should_sell, reason = True, '止损'
            elif c > entry * (1 + TAKE_PROFIT):
                should_sell, reason = True, '止盈'
            elif strat_name == '布林带突破':
                if float(df['close'].iloc[i-1]) >= float(df['bb_l'].iloc[i-1]) and c < float(df['bb_l'].iloc[i]):
                    should_sell, reason = True, '信号卖出'
            elif strat_name == '趋势突破':
                if float(df['close'].iloc[i-1]) >= float(df['low20'].iloc[i-1]) and c < float(df['low20'].iloc[i]):
                    should_sell, reason = True, '信号卖出'
            elif strat_name == '均线交叉':
                if float(df['ma5'].iloc[i-1]) >= float(df['ma20l'].iloc[i-1]) and float(df['ma5'].iloc[i]) < float(df['ma20l'].iloc[i]):
                    should_sell, reason = True, '信号卖出'
            
            if should_sell:
                ret = (c / entry - 1) * 100
                cash += shares * c
                trades.append(ret)
                shares = 0
        
        # 买入检查
        if shares == 0:
            buy = False
            if strat_name == '布林带突破':
                buy = float(df['close'].iloc[i-1]) <= float(df['bb_u'].iloc[i-1]) and c > float(df['bb_u'].iloc[i-1])
            elif strat_name == '趋势突破':
                buy = float(df['close'].iloc[i-1]) <= float(df['high20'].iloc[i-1]) and c > float(df['high20'].iloc[i-1])
            elif strat_name == '均线交叉':
                buy = float(df['ma5'].iloc[i-1]) <= float(df['ma20l'].iloc[i-1]) and float(df['ma5'].iloc[i]) > float(df['ma20l'].iloc[i])
            
            if buy and c > 0:
                shares = int(cash / c * 0.995)
                entry = c
                cash -= shares * c
        
        # 每日权益
        total = cash + shares * c
    
    completed = [t for t in trades if t is not None]
    if len(completed) < 3:
        return None
    
    start_date = str(df['date'].iloc[25].date())
    end_date = str(df['date'].iloc[-1].date())
    days = (df['date'].iloc[-1] - df['date'].iloc[25]).days
    final_val = cash + shares * float(df['close'].iloc[-1])
    
    return {
        'code': code, 'name': name,
        'start_date': start_date, 'end_date': end_date,
        'backtest_days': days,
        'final_value': round(final_val, 2),
        'total_return_pct': round((final_val / INITIAL_PER_ETF - 1) * 100, 2),
        'annual_return_pct': round((final_val / INITIAL_PER_ETF - 1) * 365 / max(days, 1) * 100, 2),
        'trade_count': len(completed),
        'win_count': sum(1 for t in completed if t > 0),
        'win_rate': round(sum(1 for t in completed if t > 0) / len(completed) * 100, 1),
        'avg_return': round(sum(completed) / len(completed), 2),
        'max_win': round(max(completed), 2),
        'max_loss': round(min(completed), 2),
    }

# 主程序
with open(POOL_FILE, 'r', encoding='utf-8') as f:
    pool = json.load(f)

etfs = pool.get('data', pool)
total_etfs = len(etfs)
print(f"开始全量回测: {total_etfs}只ETF × 3策略\n")

results = {'布林带突破': [], '趋势突破': [], '均线交叉': []}
total_runs = total_etfs * 3
count = 0

for etf in etfs:
    code = etf['code']
    name = etf.get('name', code)
    
    for strat_name in results:
        count += 1
        r = backtest(code, name, strat_name)
        if r:
            results[strat_name].append(r)
    
    if count % 30 == 0:
        print(f"  已完成 {count}/{total_runs} ({count*100//total_runs}%)...")

print(f"\n原始结果统计:")
for s, rs in results.items():
    print(f"  {s}: {len(rs)}只ETF有效回测")

# 筛选：年化>=10% 且 胜率>=45%
MIN_ANNUAL = 10
MIN_WIN_RATE = 45

for strat_name in results:
    rs = results[strat_name]
    filtered = [r for r in rs if r['annual_return_pct'] >= MIN_ANNUAL and r['win_rate'] >= MIN_WIN_RATE]
    results[strat_name] = filtered

print(f"\n筛选后(年化>={MIN_ANNUAL}% 且 胜率>={MIN_WIN_RATE}%):")
for s, rs in results.items():
    print(f"  {s}: {len(rs)}只ETF")

# 输出
output = {}
for strat_name, rs in results.items():
    # 按年化降序
    rs.sort(key=lambda x: x['annual_return_pct'], reverse=True)
    
    output[strat_name] = {
        'count': len(rs),
        'etfs': [{'code': r['code'], 'name': r['name'],
                  'annual_return': r['annual_return_pct'],
                  'win_rate': r['win_rate'],
                  'total_return': r['total_return_pct'],
                  'trade_count': r['trade_count'],
                  'max_loss': r['max_loss'],
                  'start_date': r['start_date'],
                  'end_date': r['end_date'],
                  'backtest_days': r['backtest_days']} for r in rs]
    }

# 保存
with open(r"D:\QClaw_Trading\data\candidate_pool_v4.json", 'w', encoding='utf-8') as f:
    json.dump({
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'criteria': f'年化>={MIN_ANNUAL}% 且 胜率>={MIN_WIN_RATE}%',
        'initial_per_etf': INITIAL_PER_ETF,
        'results': output
    }, f, ensure_ascii=False, indent=2)

print(f"\n{'='*70}")
print(f"三策略候选池（按年化降序）")
print(f"{'='*70}")

for strat_name, data in output.items():
    rs = data['etfs']
    print(f"\n=== 【{strat_name}】{len(rs)}只 ===")
    if not rs:
        print("  无符合条件ETF")
        continue
    
    # 显示前15只 + 汇总统计
    print(f"{'代码':<8} {'名称':<18} {'年化':>7} {'胜率':>5} {'总收益':>8} {'交易':>4} {'最大亏':>6} {'数据区间'}")
    print("-"*80)
    for r in rs[:20]:
        print(f"  {r['code']:<8} {r['name']:<18} {r['annual_return']:>+6.1f}% {r['win_rate']:>5.0f}% {r['total_return']:>+7.1f}% {r['trade_count']:>4}次 {r['max_loss']:>+5.1f}%  {r['start_date']}~{r['end_date']}")
    if len(rs) > 20:
        print(f"  ... 还有{len(rs)-20}只")

# 汇总
print(f"\n{'='*70}")
print(f"📊 汇总")
print(f"{'策略':<12} {'候选数':>6} {'平均年化':>8} {'平均胜率':>7}")
print("-"*40)
for strat_name, data in output.items():
    rs = data['etfs']
    if rs:
        avg_ann = sum(r['annual_return'] for r in rs) / len(rs)
        avg_wr = sum(r['win_rate'] for r in rs) / len(rs)
        print(f"  {strat_name:<12} {len(rs):>6} {avg_ann:>+7.1f}% {avg_wr:>6.0f}%")

print(f"\n✅ 已保存: candidate_pool_v4.json")