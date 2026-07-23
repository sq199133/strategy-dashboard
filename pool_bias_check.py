import json, os, pandas as pd, numpy as np

DATA_DIR = r"D:\QClaw_Trading\data\history"
STOP_LOSS = 0.06; TAKE_PROFIT = 0.10; FEE = 0.0005; RF = 0.03

# 加载所有候选ETF
candidate_pool = []
for fname in os.listdir(DATA_DIR):
    if fname.endswith('.json') and fname[:2] in ['sh','sz']:
        code = fname[2:8]
        path = os.path.join(DATA_DIR, fname)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            records = data.get('records', [])
            if len(records) > 500:  # 至少2年数据
                first_date = records[0]['date']
                candidate_pool.append({'code':code,'start':first_date,'records':len(records)})
        except:
            pass

print(f"候选池总数: {len(candidate_pool)} 只ETF")
print()

# 按上市时间分组
early_etfs = [c for c in candidate_pool if c['start'] < '2010-01-01']
mid_etfs = [c for c in candidate_pool if '2010-01-01' <= c['start'] < '2015-01-01']
late_etfs = [c for c in candidate_pool if c['start'] >= '2015-01-01']

print(f"2006年前上市: {len(early_etfs)} 只")
print(f"2010-2015年上市: {len(mid_etfs)} 只")
print(f"2015年后上市: {len(late_etfs)} 只")
print()

# 核心问题：TOP3的159902/160723/161128是怎么选出来的？
print("=" * 70)
print("TOP3选择来源分析")
print("=" * 70)
print("""
根据之前记录，TOP3是从194只ETF中按布林带策略回测收益排名选出的：
- 159902: 年化+1155.6%（排名第一）
- 160723: 年化+529.5%（排名第二）
- 161128: 年化+484.8%（排名第三）

这是典型的"幸存者偏差"——
用历史数据选最好的标的，然后说"你看，这个策略年化24%"
但实际上：
- 这些标的在2006-2016年根本不存在（160723/161128）
- 或者表现很普通（159902在2011-2026年化仅+9%）
""")

# 验证：如果用随机选的ETF会怎样？
print("=" * 70)
print("随机标的池 vs TOP3 对比")
print("=" * 70)

def run_backtest_simple(etf_codes, start_date, end_date):
    """简化回测，返回年化收益"""
    etf_dfs = {}
    for code in etf_codes:
        for prefix in ['sz','sh']:
            path = os.path.join(DATA_DIR, f'{prefix}{code}.json')
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    df = pd.DataFrame(data['records'])
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date').reset_index(drop=True)
                    df['close'] = df['close'].astype(float)
                    df['ma20'] = df['close'].rolling(20).mean()
                    df['std20'] = df['close'].rolling(20).std()
                    df['bb_upper'] = df['ma20'] + 2*df['std20']
                    df['bb_lower'] = df['ma20'] - 2*df['std20']
                    etf_dfs[code] = df
                except:
                    pass
                break

    if not etf_dfs:
        return None

    all_dates = sorted(set().union(*[set(df['date']) for df in etf_dfs.values()]))
    trade_dates = [d for d in all_dates if pd.to_datetime(start_date) <= d <= pd.to_datetime(end_date)]

    close_map = {}
    for dt in trade_dates:
        cm = {}
        for code, df in etf_dfs.items():
            sub = df[df['date'] == dt]
            if not sub.empty:
                row = sub.iloc[0]
                if pd.notna(row.get('bb_upper', np.nan)):
                    cm[code] = {'close':row['close'],'bb_upper':row['bb_upper'],
                                'bb_lower':row['bb_lower'],'i':sub.index[0]}
        close_map[dt] = cm

    cash = 100000; position = None; nav_list = []
    for dt in trade_dates:
        today = close_map.get(dt, {})
        if position and position['code'] in today:
            nav_list.append(cash + position['shares']*today[position['code']]['close'])
        elif position:
            nav_list.append(None)
        else:
            nav_list.append(cash)

        if position and position['code'] in today:
            td = today[position['code']]
            close = td['close']; i = td['i']
            if i >= 25:
                sell = False
                if close < position['entry_price']*(1-STOP_LOSS):
                    sell = True
                elif close > position['entry_price']*(1+TAKE_PROFIT):
                    sell = True
                elif i>=2 and etf_dfs[position['code']].iloc[i-1]['close'] >= td['bb_lower'] and close < td['bb_lower']:
                    sell = True
                if sell:
                    cash += position['shares']*close*(1-FEE)
                    position = None

        if not position:
            for code in etf_codes:
                if code not in today: continue
                td = today[code]; i = td['i']
                if i < 26: continue
                close = td['close']
                if etf_dfs[code].iloc[i-1]['close'] <= td['bb_upper'] and close > td['bb_upper']:
                    shares = int(cash/close/(1+FEE))
                    if shares > 0:
                        cash -= shares*close*(1+FEE)
                        position = {'code':code,'shares':shares,'entry_price':close}
                        break

    nav_valid = [v for v in nav_list if v is not None]
    if not nav_valid:
        return None
    final = nav_valid[-1]
    years = (trade_dates[-1]-trade_dates[0]).days/365.25
    geo = ((final/100000)**(1/years)-1)*100 if years>0 else 0
    return geo

# 测试2017-2026区间（三只ETF都有数据）
print("\n2017-2026年回测对比:")
print(f"{'标的池':<20} {'年化收益':>10}")
print("-" * 35)

# TOP3
r_top3 = run_backtest_simple(['159902','160723','161128'], '2017-01-01', '2026-05-21')
print(f"{'TOP3(159902/160723/161128)':<20} {r_top3:>+9.2f}%")

# 随机选3只早期ETF
early_codes = [c['code'] for c in early_etfs[:5]]
if len(early_codes) >= 3:
    r_early = run_backtest_simple(early_codes[:3], '2017-01-01', '2026-05-21')
    if r_early:
        print(f"{'早期ETF样本(前3只)':<20} {r_early:>+9.2f}%")

# 单独测试159902
r_159902 = run_backtest_simple(['159902'], '2017-01-01', '2026-05-21')
print(f"{'仅159902':<20} {r_159902:>+9.2f}%")

# 单独测试160723
r_160723 = run_backtest_simple(['160723'], '2017-01-01', '2026-05-21')
print(f"{'仅160723':<20} {r_160723:>+9.2f}%")

# 单独测试161128
r_161128 = run_backtest_simple(['161128'], '2017-01-01', '2026-05-21')
print(f"{'仅161128':<20} {r_161128:>+9.2f}%")

print("\n" + "=" * 70)
print("最终结论")
print("=" * 70)
