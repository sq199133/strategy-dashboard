import json, os, pandas as pd, numpy as np
from itertools import product

DATA_DIR = r"D:\QClaw_Trading\data\history"
TOP3 = [('159902','sz'), ('160723','sz'), ('161128','sz')]
INIT_CAP = 100000; FEE = 0.0005; RF = 0.03

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

def run_backtest(sl, tp):
    cash = INIT_CAP; position = None; trades = []; nav_list = []
    for idx, dt in enumerate(trade_dates):
        today_data = close_map.get(dt, {})
        pos_close = None
        if position and position['code'] in today_data:
            pos_close = today_data[position['code']]['close']
        if position and pos_close is not None:
            nav_list.append(cash + position['shares'] * pos_close)
        elif position:
            nav_list.append(None)
        else:
            nav_list.append(cash)
        if position and position['code'] in today_data:
            td = today_data[position['code']]
            close = td['close']; i = td['i']
            if i >= 25:
                sell, reason = False, ''
                if close < position['entry_price']*(1-sl):
                    sell, reason = True, '止损'
                elif close > position['entry_price']*(1+tp):
                    sell, reason = True, '止盈'
                elif i>=2 and etf_dfs[position['code']].iloc[i-1]['close'] >= td['bb_lower'] and close < td['bb_lower']:
                    sell, reason = True, '信号卖出'
                if sell:
                    cash += position['shares']*close*(1-FEE)
                    trades.append({'ret':(close/position['entry_price']-1)*100,'action':reason})
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
    # 最终净值
    nav_valid = [v for v in nav_list if v is not None]
    final_nav = nav_valid[-1] if nav_valid else cash
    # 年化收益
    years = (trade_dates[-1]-trade_dates[0]).days/365.25
    geo_annual = ((final_nav/INIT_CAP)**(1/years)-1)*100 if years>0 and final_nav>0 else 0
    # 夏普
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
    closed = [t for t in trades if t['action']!='买入']
    wins = [t for t in closed if t['ret']>0]
    win_rate = len(wins)/len(closed)*100 if closed else 0
    return {'final_nav':final_nav,'geo_annual':geo_annual,'sharpe':sharpe,
            'max_dd':max_dd,'win_rate':win_rate,'n_trades':len(closed)}

# 网格搜索
sl_list = [0.05, 0.06, 0.07, 0.08, 0.10, 0.12]
tp_list = [0.10, 0.12, 0.15, 0.18, 0.20, 0.25, 0.30]
print(f"{'止损':>6} {'止盈':>6} {'最终净值':>12} {'年化':>8} {'夏普':>6} {'最大回撤':>9} {'胜率':>7} {'交易数':>6}")
print("-"*70)

results = []
for sl in sl_list:
    for tp in tp_list:
        r = run_backtest(sl, tp)
        r['sl'] = sl; r['tp'] = tp
        results.append(r)
        print(f"{sl*100:>5.0f}% {tp*100:>5.0f}% {r['final_nav']:>12,.0f} {r['geo_annual']:>+7.2f}% {r['sharpe']:>+6.2f} {r['max_dd']:>+8.2f}% {r['win_rate']:>6.1f}% {r['n_trades']:>5d}")

# Top10 by Sharpe
print("\n===== Top10 by 夏普比率 =====")
top = sorted(results, key=lambda x: x['sharpe'], reverse=True)[:10]
print(f"{'止损':>6} {'止盈':>6} {'年化':>8} {'夏普':>6} {'最大回撤':>9} {'胜率':>7} {'交易数':>6}")
for r in top:
    print(f"{r['sl']*100:>5.0f}% {r['tp']*100:>5.0f}% {r['geo_annual']:>+7.2f}% {r['sharpe']:>+6.2f} {r['max_dd']:>+8.2f}% {r['win_rate']:>6.1f}% {r['n_trades']:>5d}")

# Top10 by Calmar
print("\n===== Top10 by Calmar比率 =====")
for r in sorted(results, key=lambda x: x['geo_annual']/abs(x['max_dd']) if x['max_dd']!=0 else 0, reverse=True)[:10]:
    calmar = r['geo_annual']/abs(r['max_dd']) if r['max_dd']!=0 else 0
    print(f"{r['sl']*100:>5.0f}% {r['tp']*100:>5.0f}% {r['geo_annual']:>+7.2f}% {r['sharpe']:>+6.2f} {r['max_dd']:>+8.2f}% {calmar:>+6.2f} {r['win_rate']:>6.1f}%")
