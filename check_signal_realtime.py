import json, os, pandas as pd, numpy as np
import urllib.request

DATA_DIR = r"D:\QClaw_Trading\data\history"
TOP3 = ['159902', '160723', '161128']

def get_realtime_quote(code):
    secid = f'0.{code}'
    url = f'https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f58'
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        if data and 'data' in data and data['data']:
            return {'close': data['data'].get('f43', 0) / 100}
    except:
        pass
    return None

print("=" * 70)
print("布林带突破信号检查（实时数据）")
print("=" * 70)

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

            # 获取实时价格
            realtime = get_realtime_quote(code)
            if realtime and realtime['close']:
                # 用实时价格替换最后一根K线
                df.loc[df.index[-1], 'close'] = realtime['close']

            # 计算布林带
            df['ma20'] = df['close'].rolling(20).mean()
            df['std20'] = df['close'].rolling(20).std()
            df['bb_upper'] = df['ma20'] + 2*df['std20']
            df['bb_lower'] = df['ma20'] - 2*df['std20']

            last = df.iloc[-1]
            prev = df.iloc[-2]

            close = last['close']
            bb_upper = last['bb_upper']
            bb_lower = last['bb_lower']
            prev_close = prev['close']

            # 信号判断
            signal = ""
            if prev_close <= bb_upper and close > bb_upper:
                signal = "★ 买入信号！突破上轨"
            elif close < prev_close * 0.94:
                signal = "▼ 触发止损（-6%）"
            elif close > prev_close * 1.10:
                signal = "▲ 触发止盈（+10%）"
            elif prev_close >= bb_lower and close < bb_lower:
                signal = "▼ 信号卖出（跌破下轨）"
            else:
                dist_to_upper = (bb_upper - close) / close * 100
                signal = f"在通道内，距上轨{dist_to_upper:+.1f}%"

            print(f"\n{code}")
            print(f"  收盘价: {close:.3f}")
            print(f"  上轨: {bb_upper:.3f}  下轨: {bb_lower:.3f}")
            print(f"  MA20: {last['ma20']:.3f}")
            print(f"  信号: {signal}")

            break

print("\n" + "=" * 70)
print("结论")
print("=" * 70)
