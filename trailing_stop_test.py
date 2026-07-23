import json, os, pandas as pd, numpy as np

DATA_DIR = r"D:\QClaw_Trading\data\history"
TOP3 = [('159902','sz'), ('160723','sz'), ('161128','sz')]
INIT_CAP = 100000; FEE = 0.0005; RF = 0.03

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

def run_backtest(sl, tp, trailing_pct=None):
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
                entry = position['entry_price']
                cur_high = position.get('high_since_entry', entry)
                cur_high = max(cur_high, close)

                # 更新持仓最高价
                position['high_since_entry'] = cur_high

                sell, reason = False, ''
                # 止损
                if close < entry*(1-sl):
                    sell, reason = True, '止损'
                # 追踪止损
                elif trailing_pct and cur_high > entry:
                    trail_level = cur_high*(1-trailing_pct)
                    if close < trail_level:
                        sell, reason = True, '追踪止'
                # 固定止盈
                elif trailing_pct is None and close > entry*(1+tp):
                    sell, reason = True, '止盈'
                # 信号卖出
                elif i>=2 and etf_dfs[position['code']].iloc[i-1]['close'] >= td['bb_lower'] and close < td['bb_lower']:
                    sell, reason = True, '信号卖出'
                if sell:
                    cash += position['shares']*close*(1-FEE)
                    trades.append({'ret':(close/entry-1)*100,'action':reason})
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
                    position = {'code':code,'shares':shares,'entry_price':close,
                                'entry_date':dt,'high_since_entry':close}
                    break

    nav_valid = [v for v in nav_list if v is not None]
    final_nav = nav_valid[-1] if nav_valid else cash
    years = (trade_dates[-1]-trade_dates[0]).days/365.25
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
        sharpe=0; max_dd=0; annual_ret=0
    closed = [t for t in trades if t['action']!='买入']
    wins = [t for t in closed if t['ret']>0]
    win_rate = len(wins)/len(closed)*100 if closed else 0
    reasons = {}
    for t in closed: reasons[t['action']] = reasons.get(t['action'],0)+1
    return {'final_nav':final_nav,'geo_annual':geo_annual,'sharpe':sharpe,
            'max_dd':max_dd,'win_rate':win_rate,'n_trades':len(closed),
            'reasons':reasons}

# 基准对比
baseline = run_backtest(0.06, 0.12)
print(f"===== 基准: 止损6% / 固定止盈12% =====")
print(f"  年化: {baseline['geo_annual']:+.2f}% | 夏普: {baseline['sharpe']:+.2f} | 最大回撤: {baseline['max_dd']:+.2f}% | 胜率: {baseline['win_rate']:.1f}% | 交易: {baseline['n_trades']}次")
print(f"  卖出原因: {baseline['reasons']}")
print()

# 追踪止损测试
trailing_list = [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]
print(f"{'追踪止损':>8} {'年化':>8} {'夏普':>6} {'最大回撤':>9} {'胜率':>7} {'交易数':>6} | {'卖出分布'}")
print("-"*80)
for trail in trailing_list:
    r = run_backtest(0.06, 0.12, trailing_pct=trail)
    reasons_str = '/'.join([f"{k[:3]}:{v}" for k,v in sorted(r['reasons'].items())])
    print(f"  {trail*100:>5.0f}% {r['geo_annual']:>+7.2f}% {r['sharpe']:>+6.2f} {r['max_dd']:>+8.2f}% {r['win_rate']:>6.1f}% {r['n_trades']:>5d}  | {reasons_str}")

print()
# 对比：无止盈 + 纯追踪止损
print("===== 纯追踪止损（无固定止盈）=====")
for trail in [0.08, 0.10, 0.12, 0.15]:
    r = run_backtest(0.06, 999, trailing_pct=trail)
    reasons_str = '/'.join([f"{k[:3]}:{v}" for k,v in sorted(r['reasons'].items())])
    print(f"  SL6% + 追踪{trail*100:.0f}%: 年化{r['geo_annual']:+.2f}% | 夏普{r['sharpe']:+.2f} | 回撤{r['max_dd']:+.2f}% | {reasons_str}")
