import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import akshare as ak
from datetime import datetime
from collections import defaultdict

codes = ['161127', '512870', '161126']
for code in codes:
    try:
        df = ak.stock_zh_a_hist(symbol=code, start_date='20260101', end_date='20260628', adjust='qfq')
        if df is None or df.empty:
            print(f'{code}: no data')
            continue
        df.columns = [c.strip() for c in df.columns]
        # Keep relevant columns
        df_sub = df[['日期', '开盘', '收盘', '最高', '最低', '成交量']].copy()
        
        # Aggregate to weekly: use Friday as week end
        def to_iso_week_Friday(date_str):
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            y, w, _ = dt.isocalendar()
            # Find the Friday of this ISO week
            # dt.weekday(): Monday=0, Sunday=6
            # Friday=4
            days_to_friday = (4 - dt.weekday()) % 7
            if days_to_friday == 0 and dt.weekday() != 4:
                days_to_friday = 7
            friday = dt + timedelta(days=days_to_friday)
            return f'{y}-W{w:02d}', friday.strftime('%Y-%m-%d')
        
        from datetime import timedelta
        weeks = defaultdict(lambda: {'dates': [], 'opens': [], 'closes': [], 'highs': [], 'lows': [], 'vols': []})
        for _, row in df_sub.iterrows():
            wk, de = to_iso_week_Friday(row['日期'])
            ww = weeks[wk]
            ww['dates'].append(row['日期'])
            ww['opens'].append(float(row['开盘']))
            ww['closes'].append(float(row['收盘']))
            ww['highs'].append(float(row['最高']))
            ww['lows'].append(float(row['最低']))
            ww['vols'].append(float(row['成交量']))
        
        wk_list = sorted(weeks.items(), key=lambda x: x[0])
        wk2026 = [(k, v) for k, v in wk_list if k.startswith('2026')]
        
        print(f'\n=== {code} AKShare Weekly (2026) ===')
        for k, v in wk2026[-12:]:
            de = v['dates'][-1]
            print(f"  {k} (ends {de}): close={v['closes'][-1]:.4f}  last_5days={v['dates']}")
        
        if len(wk2026) >= 9:
            i = len(wk2026) - 1
            now_c = wk2026[i][1]['closes'][-1]
            w1_c  = wk2026[i-1][1]['closes'][-1]
            w3_c  = wk2026[i-3][1]['closes'][-1]
            w8_c  = wk2026[i-8][1]['closes'][-1]
            mom1w = now_c / w1_c - 1
            mom3w = now_c / w3_c - 1
            mom8w = now_c / w8_c - 1
            score = 0.4*mom1w + 0.4*mom3w + 0.2*mom8w
            print(f'\n  mom1w = {mom1w*100:+.2f}%  mom3w = {mom3w*100:+.2f}%  mom8w = {mom8w*100:+.2f}%  score = {score*100:.2f}%')
    except Exception as e:
        print(f'{code}: ERROR {e}')
