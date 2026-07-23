import json, os, pandas as pd, numpy as np
from datetime import datetime

DATA_DIR = r"D:\QClaw_Trading\data\history"
TOP3 = [('159902','sz'), ('160723','sz'), ('161128','sz')]
INIT_CAP = 100000; STOP_LOSS = 0.06; TAKE_PROFIT = 0.10; FEE = 0.0005; RF = 0.03

# 加载ETF
etf_dfs = {}
for code, prefix in TOP3:
    path = os.path.join(DATA_DIR, f'{prefix}{code}.json')
    if os.path.exists(path):
        with open(path,'r',encoding='utf-8') as f:
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

all_dates = sorted(set().union(*[set(df['date']) for df in etf_dfs.values()]))
trade_dates = sorted([d for d in all_dates if any(d in set(df['date']) for df in etf_dfs.values())])

close_map = {}
for dt in trade_dates:
    cm = {}
    for code, df in etf_dfs.items():
        sub = df[df['date'] == dt]
        if not sub.empty:
            row = sub.iloc[0]
            if pd.notna(row['bb_upper']):
                cm[code] = {'close': row['close'], 'bb_upper': row['bb_upper'],
                            'bb_lower': row['bb_lower'], 'i': sub.index[0]}
    close_map[dt] = cm

def run_backtest(start_date=None, end_date=None):
    cash = INIT_CAP; position = None; nav_list = []; trade_dates_filtered = trade_dates
    if start_date: trade_dates_filtered = [d for d in trade_dates_filtered if d >= pd.to_datetime(start_date)]
    if end_date: trade_dates_filtered = [d for d in trade_dates_filtered if d <= pd.to_datetime(end_date)]

    for idx, dt in enumerate(trade_dates_filtered):
        today_data = close_map.get(dt, {})
        if position and position['code'] in today_data:
            nav_list.append(cash + position['shares'] * today_data[position['code']]['close'])
        elif position:
            nav_list.append(None)
        else:
            nav_list.append(cash)

        if position and position['code'] in today_data:
            td = today_data[position['code']]
            close = td['close']; i = td['i']
            if i >= 25:
                sell, reason = False, ''
                if close < position['entry_price']*(1-STOP_LOSS):
                    sell, reason = True, '止损'
                elif close > position['entry_price']*(1+TAKE_PROFIT):
                    sell, reason = True, '止盈'
                elif i>=2 and etf_dfs[position['code']].iloc[i-1]['close'] >= td['bb_lower'] and close < td['bb_lower']:
                    sell, reason = True, '信号卖出'
                if sell:
                    cash += position['shares']*close*(1-FEE)
                    position = None

        if not position:
            for code in ['159902','160723','161128']:
                if code not in today_data: continue
                td = today_data[code]; i = td['i']
                if i < 26: continue
                close = td['close']
                prev_row = etf_dfs[code].iloc[i-1]
                if prev_row['close'] <= td['bb_upper'] and close > td['bb_upper']:
                    shares = int(cash/close/(1+FEE))
                    if shares == 0: continue
                    cash -= shares*close*(1+FEE)
                    position = {'code':code,'shares':shares,'entry_price':close,'entry_date':dt}
                    break

    nav_valid = [v for v in nav_list if v is not None]
    final_nav = nav_valid[-1] if nav_valid else cash
    years = (trade_dates_filtered[-1]-trade_dates_filtered[0]).days/365.25
    geo_annual = ((final_nav/INIT_CAP)**(1/years)-1)*100 if years>0 and final_nav>0 else 0

    valid_pairs = [(v, nav_list[i+1]) for i,v in enumerate(nav_list[:-1]) if v is not None and nav_list[i+1] is not None]
    if valid_pairs:
        dr_arr = np.array([(b-a)/a for a,b in valid_pairs])
        annual_ret = float(np.mean(dr_arr)*252)
        annual_vol = float(np.std(dr_arr,ddof=1)*np.sqrt(252))
        sharpe = (annual_ret-RF)/annual_vol if annual_vol>0 else 0
        nav_arr = np.array(nav_valid)
        cummax = np.maximum.accumulate(nav_arr)
        max_dd = float(np.min((nav_arr-cummax)/cummax))*100
    else:
        sharpe=0; max_dd=0

    return {'final_nav':final_nav,'geo_annual':geo_annual,'sharpe':sharpe,'max_dd':max_dd,'years':years}

# 分段回测
print("=" * 70)
print("过拟合检验：滚动窗口回测")
print("=" * 70)

# 按年份分段
periods = [
    ("2006-2010", "2006-09-05", "2010-12-31"),
    ("2011-2015", "2011-01-01", "2015-12-31"),
    ("2016-2020", "2016-01-01", "2020-12-31"),
    ("2021-2026", "2021-01-01", "2026-05-21"),
]

print(f"\n{'区间':<12} {'年数':>6} {'年化收益':>10} {'夏普':>8} {'最大回撤':>10}")
print("-" * 70)
for name, start, end in periods:
    r = run_backtest(start, end)
    print(f"{name:<12} {r['years']:>5.1f}年 {r['geo_annual']:>+9.2f}% {r['sharpe']:>+8.2f} {r['max_dd']:>+9.2f}%")

# 样本外检验：用2017年前数据（仅159902）
print("\n" + "=" * 70)
print("样本外检验：2017年前（仅159902有数据，160723/161128未上市）")
print("=" * 70)
r_early = run_backtest("2006-09-05", "2016-12-31")
print(f"2006-2016年化: {r_early['geo_annual']:+.2f}% | 夏普: {r_early['sharpe']:+.2f} | 回撤: {r_early['max_dd']:+.2f}%")

# 样本内检验：2017年后（三只ETF齐全）
print("\n" + "=" * 70)
print("样本内检验：2017年后（三只ETF齐全）")
print("=" * 70)
r_late = run_backtest("2017-01-01", "2026-05-21")
print(f"2017-2026年化: {r_late['geo_annual']:+.2f}% | 夏普: {r_late['sharpe']:+.2f} | 回撤: {r_late['max_dd']:+.2f}%")

# 全周期
print("\n" + "=" * 70)
print("全周期（2006-2026，19.7年）")
print("=" * 70)
r_full = run_backtest()
print(f"年化: {r_full['geo_annual']:+.2f}% | 夏普: {r_full['sharpe']:+.2f} | 回撤: {r_full['max_dd']:+.2f}%")

print("\n" + "=" * 70)
print("过拟合风险分析")
print("=" * 70)
print(f"1. 样本外(2006-2016)年化: {r_early['geo_annual']:+.2f}%")
print(f"2. 样本内(2017-2026)年化: {r_late['geo_annual']:+.2f}%")
print(f"3. 差距: {abs(r_early['geo_annual']-r_late['geo_annual']):.2f}个百分点")
if abs(r_early['geo_annual']-r_late['geo_annual']) < 10:
    print("   → 样本内外表现接近，过拟合风险较低")
else:
    print("   → 样本内外差距较大，需警惕过拟合")
