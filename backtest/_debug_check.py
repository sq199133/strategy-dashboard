import pandas as pd, os
d = r'D:\QClaw_Trading\data'
files = [f for f in os.listdir(d) if f.endswith('.csv')]
files.sort()
for f in files[-5:]:
    df = pd.read_csv(os.path.join(d,f), encoding='utf-8-sig')
    print(f'{f:35s}  rows={len(df):>6}  last_date={df["date"].iloc[-1]}  close={df["close"].iloc[-1]:>8.2f}')
print('---')
for code, name in [('300102','乾照光电'),('688599','天合光能'),('600118','中国卫星')]:
    path = os.path.join(d, f'{code}_{name}.csv')
    df = pd.read_csv(path, encoding='utf-8-sig')
    for c in ['close','high']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df['ch20h'] = df['high'].rolling(20).max()
    last = df.iloc[-1]
    print(f'{name}: close={last["close"]:.2f} ch20h={last["ch20h"]:.2f}  signal={last["close"] >= last["ch20h"]}')
