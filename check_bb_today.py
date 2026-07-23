import json, os, pandas as pd

DATA_DIR = r"D:\QClaw_Trading\data\history"
TOP3 = [('159902','sz'), ('160723','sz'), ('161128','sz')]

today_close = {'159902': 5.105, '160723': 2.272, '161128': 6.603}
yesterday_close = {'159902': 5.000, '160723': 2.299, '161128': 6.491}

for code, prefix in TOP3:
    path = os.path.join(DATA_DIR, f'{prefix}{code}.json')
    if not os.path.exists(path):
        print(f"{code}: 历史文件不存在")
        continue
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

    # 用昨日数据（含5/21收盘）
    last = df.iloc[-1]
    prev = df.iloc[-2]

    print(f"\n{'='*50}")
    print(f"{code} | 最新日期: {last['date'].strftime('%Y-%m-%d')} | 昨收: {yesterday_close[code]:.3f}")
    print(f"  MA20: {last['ma20']:.4f} | STD20: {last['std20']:.4f}")
    print(f"  布林上轨: {last['bb_upper']:.4f} | 布林下轨: {last['bb_lower']:.4f}")

    # 信号判断（用昨收和昨布林带指标判断今日是否触发信号）
    p_close = yesterday_close[code]
    p_upper = prev['bb_upper'] if pd.notna(prev['bb_upper']) else None
    p_lower = prev['bb_lower'] if pd.notna(prev['bb_lower']) else None
    t_close = today_close[code]

    if p_upper is None or p_lower is None:
        print(f"  -> 数据不足，无法计算布林带")
        continue

    print(f"  昨收:{p_close:.3f} vs 昨上轨:{p_upper:.3f} vs 昨下轨:{p_lower:.3f}")
    print(f"  今收:{t_close:.3f}")

    buy_triggered = (p_close <= p_upper and t_close > p_upper)
    sell_triggered = (p_close >= p_lower and t_close < p_lower)

    if buy_triggered:
        print(f"  -> *** BUY信号触发 ***")
    elif sell_triggered:
        print(f"  -> *** SELL信号触发 ***")
    else:
        print(f"  -> 无信号")
        if t_close > p_upper:
            print(f"     (今收已在上轨上方，无买入机会)")
        elif t_close < p_lower:
            print(f"     (今收已在下轨下方，等待)")
        else:
            print(f"     (仍在布林带内震荡)")
