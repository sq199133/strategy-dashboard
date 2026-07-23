#!/usr/bin/env python3
"""检查周五（2026-05-15）各ETF的买卖信号"""
import json, os

DATA_DIR = r"D:\QClaw_Trading\data\history"

candidates = {
    '布林带突破': [
        ("159902","中小100ETF华夏"),("161128","标普信息科技LOF"),("160723","嘉实原油LOF"),
        ("163208","全球油气能源LOF"),("161130","纳斯达克100LOF"),("501018","南方原油LOF"),
        ("162719","石油LOF"),("159928","消费ETF汇添富"),("162415","美国消费LOF"),
        ("512770","战略新兴ETF华夏"),("159985","豆粕ETF华夏"),("159996","家电ETF国泰"),
        ("159819","人工智能ETF易方达"),("512950","央企改革ETF华夏"),("159852","软件ETF嘉实"),
    ],
    '趋势突破': [
        ("159902","中小100ETF华夏"),("161129","原油LOF易方达"),("160723","嘉实原油LOF"),
        ("161128","标普信息科技LOF"),("161130","纳斯达克100LOF"),("159928","消费ETF汇添富"),
        ("160216","国泰商品LOF"),("162719","石油LOF"),("512770","战略新兴ETF华夏"),
        ("160719","嘉实黄金LOF"),("162415","美国消费LOF"),("515580","科技100ETF华泰柏瑞"),
        ("512040","价值100ETF富国"),("159852","软件ETF嘉实"),
    ],
    '均线交叉': [
        ("160723","嘉实原油LOF"),("560280","工程机械ETF广发"),("588220","科创100ETF鹏华"),
        ("563300","中证2000ETF华泰柏瑞"),("159667","工业母机ETF国泰"),("159687","亚太精选ETF"),
    ]
}

def load_etf(code):
    for prefix in ['sh', 'sz']:
        path = os.path.join(DATA_DIR, f"{prefix}{code}.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'records' in data:
                df = __import__('pandas').DataFrame(data['records'])
                df['date'] = __import__('pandas').to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)
                for col in ['close', 'high', 'low']:
                    df[col] = df[col].astype(float)
                return df
    return None

def calc(df):
    df = df.copy()
    df['ma20'] = df['close'].rolling(20).mean()
    df['std20'] = df['close'].rolling(20).std()
    df['bb_u'] = df['ma20'] + 2 * df['std20']
    df['bb_l'] = df['ma20'] - 2 * df['std20']
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20l'] = df['close'].rolling(20).mean()
    df['high20'] = df['high'].rolling(20).max()
    df['low20'] = df['low'].rolling(20).min()
    return df

def check_signals(code, name, strategy):
    df = load_etf(code)
    if df is None or len(df) < 26:
        return None, f"数据不足({len(df) if df else 0}条)"

    df = calc(df)
    i = len(df) - 1  # 最新一根K线
    
    latest_date = str(df['date'].iloc[i].date())
    c = float(df['close'].iloc[i])
    pc = float(df['close'].iloc[i-1])
    
    result = {
        'code': code, 'name': name, 'strategy': strategy,
        'date': latest_date, 'close': c,
        'bb_u': round(float(df['bb_u'].iloc[i]), 4),
        'bb_l': round(float(df['bb_l'].iloc[i]), 4),
        'high20': round(float(df['high20'].iloc[i]), 4),
        'low20': round(float(df['low20'].iloc[i]), 4),
        'ma5': round(float(df['ma5'].iloc[i]), 4),
        'ma20': round(float(df['ma20l'].iloc[i]), 4),
        'buy_signal': False, 'sell_signal': False,
        'buy_reason': '', 'sell_reason': ''
    }
    
    if strategy == '布林带突破':
        bb_u = float(df['bb_u'].iloc[i])
        bb_u_prev = float(df['bb_u'].iloc[i-1])
        bb_l = float(df['bb_l'].iloc[i])
        bb_l_prev = float(df['bb_l'].iloc[i-1])
        
        # 买入：前日收<=上轨，当日突破
        if pc <= bb_u_prev and c > bb_u_prev:
            result['buy_signal'] = True
            result['buy_reason'] = f"突破布林上轨({bb_u_prev:.4f})"
        # 卖出：前日收>=下轨，当日跌破
        if pc >= bb_l_prev and c < bb_l:
            result['sell_signal'] = True
            result['sell_reason'] = f"跌破布林下轨({bb_l:.4f})"
    
    elif strategy == '趋势突破':
        high20 = float(df['high20'].iloc[i])
        high20_prev = float(df['high20'].iloc[i-1])
        low20 = float(df['low20'].iloc[i])
        low20_prev = float(df['low20'].iloc[i-1])
        
        if pc <= high20_prev and c > high20_prev:
            result['buy_signal'] = True
            result['buy_reason'] = f"突破20日高点({high20_prev:.4f})"
        if pc >= low20_prev and c < low20:
            result['sell_signal'] = True
            result['sell_reason'] = f"跌破20日低点({low20:.4f})"
    
    elif strategy == '均线交叉':
        ma5 = float(df['ma5'].iloc[i])
        ma5_prev = float(df['ma5'].iloc[i-1])
        ma20 = float(df['ma20l'].iloc[i])
        ma20_prev = float(df['ma20l'].iloc[i-1])
        
        if ma5_prev <= ma20_prev and ma5 > ma20:
            result['buy_signal'] = True
            result['buy_reason'] = f"MA5金叉MA20(MA5={ma5:.4f}>MA20={ma20:.4f})"
        if ma5_prev >= ma20_prev and ma5 < ma20:
            result['sell_signal'] = True
            result['sell_reason'] = f"MA5死叉MA20(MA5={ma5:.4f}<MA20={ma20:.4f})"
    
    return result, None

import sys
sys.stdout.reconfigure(encoding='utf-8')

print(f"检查日期: 2026-05-15（周五）\n")
print(f"{'策略':<10} {'代码':<8} {'名称':<16} {'最新价':>7} {'指标值':>30} {'信号'}")
print("-"*90)

all_buy = []
all_sell = []

for strat_name, items in candidates.items():
    print(f"\n=== 【{strat_name}】===")
    for code, name in items:
        r, err = check_signals(code, name, strat_name)
        if err:
            print(f"  {code} {name:<16} ⚠️ {err}")
            continue
        
        if r['buy_signal']:
            print(f"  {code} {name:<16} {r['close']:>7.3f}  → 🚀 买入: {r['buy_reason']}")
            all_buy.append(r)
        elif r['sell_signal']:
            print(f"  {code} {name:<16} {r['close']:>7.3f}  → ⚠️ 卖出: {r['sell_reason']}")
            all_sell.append(r)
        else:
            print(f"  {code} {name:<16} {r['close']:>7.3f}  → 无信号")

print(f"\n{'='*70}")
print(f"📊 周五信号汇总:")
print(f"  买入信号: {len(all_buy)}个")
for r in all_buy:
    print(f"    🚀 [{r['strategy']}] {r['code']} {r['name']} @{r['close']:.3f} — {r['buy_reason']}")
print(f"  卖出信号: {len(all_sell)}个")
for r in all_sell:
    print(f"    ⚠️ [{r['strategy']}] {r['code']} {r['name']} @{r['close']:.3f} — {r['sell_reason']}")