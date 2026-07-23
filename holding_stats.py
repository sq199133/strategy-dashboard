import json, os, pandas as pd
from datetime import datetime

DATA_DIR = r"D:\QClaw_Trading\data\history"
TOP3 = [('159902','sz'), ('160723','sz'), ('161128','sz')]
INIT_CAP = 100000; STOP_LOSS = 0.08; TAKE_PROFIT = 0.15; FEE = 0.0005

# 加载所有ETF
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

# 合并交易日历
all_dates = sorted(set().union(*[set(df['date']) for df in etf_dfs.values()]))
trade_dates = sorted([d for d in all_dates if any(d in set(df['date']) for df in etf_dfs.values())])
print(f"合并交易日历: {len(trade_dates)}天 ({trade_dates[0].strftime('%Y-%m-%d')} ~ {trade_dates[-1].strftime('%Y-%m-%d')})")

# 构建每日数据映射
close_map = {}
for dt in trade_dates:
    cm = {}
    for code, df in etf_dfs.items():
        sub = df[df['date'] == dt]
        if not sub.empty:
            row = sub.iloc[0]
            if pd.notna(row['bb_upper']):
                cm[code] = {'close': row['close'], 'bb_upper': row['bb_upper'], 'bb_lower': row['bb_lower'], 'i': sub.index[0]}
    close_map[dt] = cm

# 模拟回测，收集每笔交易的持仓天数
cash = INIT_CAP; position = None; trades = []
total_in_market_days = 0
in_market_dates = set()

for idx, dt in enumerate(trade_dates):
    today_data = close_map.get(dt, {})
    pos_close = None
    if position and position['code'] in today_data:
        pos_close = today_data[position['code']]['close']

    # 卖出检查
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
                # 记录持仓天数
                entry_dt = position['entry_date']
                holding_days = (dt - entry_dt).days
                trades.append({'entry': str(entry_dt.date()), 'exit': str(dt.date()),
                                'days': holding_days, 'reason': reason, 'code': position['code']})
                for d in trade_dates[trade_dates.index(entry_dt):idx+1]:
                    in_market_dates.add(d)
                cash += position['shares']*close*(1-FEE)
                position = None

    # 买入检查
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
                position = {'code': code, 'shares': shares, 'entry_price': close, 'entry_date': dt}
                break

# 汇总统计
if trades:
    days_list = [t['days'] for t in trades]
    import numpy as np
    print(f"\n===== 持仓时间统计 =====")
    print(f"  总交易次数   : {len(trades)} 次")
    print(f"  平均持仓天数 : {np.mean(days_list):.1f} 天")
    print(f"  中位数       : {np.median(days_list):.0f} 天")
    print(f"  最短         : {min(days_list)} 天")
    print(f"  最长         : {max(days_list)} 天")
    print(f"  < 10天       : {sum(1 for d in days_list if d < 10)} 次 ({sum(1 for d in days_list if d < 10)/len(days_list)*100:.1f}%)")
    print(f"  10~30天      : {sum(1 for d in days_list if 10 <= d < 30)} 次 ({sum(1 for d in days_list if 10 <= d < 30)/len(days_list)*100:.1f}%)")
    print(f"  30~60天      : {sum(1 for d in days_list if 30 <= d < 60)} 次 ({sum(1 for d in days_list if 30 <= d < 60)/len(days_list)*100:.1f}%)")
    print(f"  60~120天     : {sum(1 for d in days_list if 60 <= d < 120)} 次 ({sum(1 for d in days_list if 60 <= d < 120)/len(days_list)*100:.1f}%)")
    print(f"  >= 120天     : {sum(1 for d in days_list if d >= 120)} 次 ({sum(1 for d in days_list if d >= 120)/len(days_list)*100:.1f}%)")

    # 持仓时间占比
    total_days = (trade_dates[-1] - trade_dates[0]).days + 1
    in_market_days = len(in_market_dates)
    print(f"\n  持仓天数占比 : {in_market_days}/{total_days} = {in_market_days/total_days*100:.1f}%")
    print(f"  (注：仅计交易日)")

    # 卖出原因分布
    reasons = {}
    for t in trades:
        reasons[t['reason']] = reasons.get(t['reason'], 0) + 1
    print(f"\n  卖出原因分布:")
    for r, cnt in sorted(reasons.items(), key=lambda x:-x[1]):
        print(f"    {r}: {cnt}次 ({cnt/len(trades)*100:.1f}%)")

    print(f"\n最近5笔交易:")
    for t in trades[-5:]:
        print(f"  {t['entry']} -> {t['exit']} ({t['days']}天) [{t['code']}] {t['reason']}")
