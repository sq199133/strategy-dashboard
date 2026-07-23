import json, os, pandas as pd
DATA_DIR = r"D:\QClaw_Trading\data\history"
TOP3 = ['159902','160723','161128']
for code in TOP3:
    for prefix in ['sh','sz']:
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
            row = df.iloc[-1]
            prev = df.iloc[-2]
            signal = '无信号'
            if pd.notna(row['bb_upper']) and pd.notna(prev['bb_upper']):
                if prev['close'] <= prev['bb_upper'] and row['close'] > prev['bb_upper']:
                    signal = 'BUY信号'
                elif prev['close'] >= prev['bb_lower'] and row['close'] < prev['bb_lower']:
                    signal = 'SELL信号'
            print(f"{code} | {row['date'].strftime('%Y-%m-%d')} 收:{row['close']:.3f} | 前日收:{prev['close']:.3f} 上轨:{prev['bb_upper']:.3f} 下轨:{prev['bb_lower']:.3f} | {signal}")
            break
