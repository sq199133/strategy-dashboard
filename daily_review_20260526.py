import json, os, pandas as pd, numpy as np
from datetime import datetime, timedelta

DATA_DIR = r"D:\QClaw_Trading\data\history"
TOP3 = ['159902', '160723', '161128']
STOP_LOSS = 0.06; TAKE_PROFIT = 0.10

print("=" * 70)
print("ETF波段策略 - 每日复盘")
print(f"日期: 2026-05-26 (周二)")
print("=" * 70)

# 加载数据
etf_data = {}
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
            etf_data[code] = df
            break

# 检查最新数据日期
print("\n数据最新日期检查:")
for code, df in etf_data.items():
    last_date = df.iloc[-1]['date'].strftime('%Y-%m-%d')
    last_close = df.iloc[-1]['close']
    print(f"  {code}: {last_date} 收盘{last_close:.3f}")

# 如果最新数据是2026-05-21，说明需要更新数据
# 检查今天（2026-05-26）是否是交易日
today = pd.to_datetime('2026-05-26')
is_trade_day = today.weekday() < 5  # 周一到周五

print(f"\n今日2026-05-26: {'交易日' if is_trade_day else '非交易日'}")

# 计算布林带
for code, df in etf_data.items():
    df['ma20'] = df['close'].rolling(20).mean()
    df['std20'] = df['close'].rolling(20).std()
    df['bb_upper'] = df['ma20'] + 2*df['std20']
    df['bb_lower'] = df['ma20'] - 2*df['std20']

print("\n" + "=" * 70)
print("今日行情与信号检查")
print("=" * 70)

signals = []
for code, df in etf_data.items():
    last = df.iloc[-1]
    prev = df.iloc[-2]

    close = last['close']
    bb_upper = last['bb_upper']
    bb_lower = last['bb_lower']
    ma20 = last['ma20']
    prev_close = prev['close']

    # 信号判断
    signal_type = ""
    if pd.notna(bb_upper) and pd.notna(prev_close):
        if prev_close <= bb_upper and close > bb_upper:
            signal_type = "★ 买入信号"
        elif close < prev_close * (1 - STOP_LOSS):
            signal_type = "▼ 止损卖出"
        elif close > prev_close * (1 + TAKE_PROFIT):
            signal_type = "▲ 止盈卖出"
        elif pd.notna(bb_lower) and prev_close >= bb_lower and close < bb_lower:
            signal_type = "▼ 下轨卖出"
        else:
            dist = (bb_upper - close) / close * 100 if pd.notna(bb_upper) else 0
            signal_type = f"持有中 (距上轨{dist:+.1f}%)" if pd.notna(bb_upper) else "数据不足"

    signals.append({
        'code': code,
        'close': close,
        'ma20': ma20,
        'bb_upper': bb_upper,
        'bb_lower': bb_lower,
        'signal': signal_type
    })

    print(f"\n{code}")
    print(f"  收盘价: {close:.3f}")
    if pd.notna(ma20):
        print(f"  MA20: {ma20:.3f}")
        print(f"  上轨: {bb_upper:.3f}  下轨: {bb_lower:.3f}")
    print(f"  信号: {signal_type}")

# 读取虚拟盘状态
state_path = r"D:\QClaw_Trading\data\virtual_portfolio_state.json"
if os.path.exists(state_path):
    with open(state_path, 'r', encoding='utf-8') as f:
        state = json.load(f)

    print("\n" + "=" * 70)
    print("虚拟盘状态")
    print("=" * 70)
    print(f"总资金: {state.get('total_capital', 50000):.2f} 元")
    print(f"策略: {state.get('strategy', '布林带突破')}")
    print(f"状态: {state.get('status', 'active')}")

    positions = state.get('positions', [])
    if positions:
        print("\n当前持仓:")
        for pos in positions:
            print(f"  {pos['code']} {pos.get('name', '')}")
            print(f"    买入价: {pos['entry_price']:.3f}  当前价: {pos.get('current_price', pos['entry_price']):.3f}")
            pnl = (pos.get('current_price', pos['entry_price']) - pos['entry_price']) / pos['entry_price'] * 100
            print(f"    盈亏: {pnl:+.2f}%")
    else:
        print("\n当前持仓: 空仓")
else:
    print("\n未找到虚拟盘状态文件")

print("\n" + "=" * 70)
print("操作建议")
print("=" * 70)

has_buy = any('买入' in s['signal'] for s in signals)
has_sell = any('卖出' in s['signal'] for s in signals)

if has_buy:
    print("✓ 有买入信号，建议买入")
elif has_sell:
    print("✓ 有卖出信号，建议卖出")
else:
    print("✗ 无交易信号，继续持有/等待")

print(f"\n复盘完成 @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
