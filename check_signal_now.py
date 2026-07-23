import json, os, pandas as pd, numpy as np
from datetime import datetime

DATA_DIR = r"D:\QClaw_Trading\data\history"
TOP3 = ['159902', '160723', '161128']

print("=" * 70)
print("布林带突破信号检查 -", datetime.now().strftime("%Y-%m-%d %H:%M"))
print("=" * 70)

results = []

for code in TOP3:
    for prefix in ['sz', 'sh']:
        path = os.path.join(DATA_DIR, f'{prefix}{code}.json')
        if os.path.exists(path):
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

            # 最近5天数据
            recent = df.tail(5)[['date','close','ma20','bb_upper','bb_lower']].copy()
            recent['close'] = recent['close'].round(3)
            recent['ma20'] = recent['ma20'].round(3)
            recent['bb_upper'] = recent['bb_upper'].round(3)
            recent['bb_lower'] = recent['bb_lower'].round(3)

            last_date = df.iloc[-1]['date']
            last_close = df.iloc[-1]['close']
            last_bb_upper = df.iloc[-1]['bb_upper']
            last_bb_lower = df.iloc[-1]['bb_lower']
            prev_close = df.iloc[-2]['close']

            # 信号判断
            signal = ""
            if prev_close <= last_bb_upper and last_close > last_bb_upper:
                signal = "★ 买入信号！突破上轨"
            elif last_close < prev_close * 0.94:
                signal = "▼ 触发止损（-6%）"
            elif last_close > prev_close * 1.10:
                signal = "▲ 触发止盈（+10%）"
            elif prev_close >= last_bb_lower and last_close < last_bb_lower:
                signal = "▼ 信号卖出（跌破下轨）"
            else:
                dist_to_upper = (last_bb_upper - last_close) / last_close * 100
                signal = f"距上轨{dist_to_upper:+.1f}%"

            results.append({
                'code': code,
                'last_date': last_date.strftime('%Y-%m-%d'),
                'close': last_close,
                'bb_upper': last_bb_upper,
                'bb_lower': last_bb_lower,
                'signal': signal,
                'recent': recent
            })
            break

print(f"\n{'代码':<8} {'最新日期':<12} {'收盘价':>8} {'上轨':>8} {'下轨':>8} {'信号'}")
print("-" * 70)
for r in results:
    print(f"{r['code']:<8} {r['last_date']:<12} {r['close']:>8.3f} {r['bb_upper']:>8.3f} {r['bb_lower']:>8.3f} {r['signal']}")

print("\n" + "=" * 70)
print("最近5日行情")
print("=" * 70)
for r in results:
    print(f"\n{r['code']}（{r['last_date']}）")
    print(r['recent'].to_string(index=False))

print("\n" + "=" * 70)
print("结论")
print("=" * 70)
has_signal = any('买入' in r['signal'] for r in results)
if has_signal:
    print("✓ 有买入信号")
else:
    print("✗ 无买入信号，继续等待")
