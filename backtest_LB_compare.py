import sys, json, os, requests, glob
from datetime import datetime, timedelta

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'

MA_S, MA_L = 5, 21
MAX_DEV = 15
MIN_MOM_1W = -0.01

# 跳过异常周（ETF拆分导致数据异常）
SKIP_WEEKS = {'2024-W01', '2025-W01'}

def load_pool():
    with open(POOL_FILE, encoding='utf-8') as f:
        d = json.load(f)
    return [e['code'] for e in d.get('etfs', d) if e.get('enabled', True)]

def load_history(code):
    for pat in (code, f'sh{code}', f'sz{code}'):
        hits = glob.glob(os.path.join(HISTORY_DIR, f'{pat}.json'))
        if not hits:
            hits = glob.glob(os.path.join(HISTORY_DIR, f'*{code}*.json'))
        if hits:
            try:
                with open(hits[0], encoding='utf-8') as f:
                    d = json.load(f)
                recs = d.get('records', []) if isinstance(d, dict) else d
                weeks = {}
                for r in recs:
                    if isinstance(r, dict):
                        ds, cl = r['date'], float(r.get('close', 0))
                    else:
                        ds, cl = str(r[0]), float(r[2])
                    try:
                        dt = datetime.strptime(ds, '%Y-%m-%d')
                        w = f'{dt.year}-W{dt.isocalendar()[1]:02d}'
                        if w not in weeks or ds > weeks[w][0]:
                            weeks[w] = (ds, cl)
                    except: pass
                sw = sorted(weeks.items())
                return [cl for w, cl in sw], [w for w, cl in sw]
            except: continue
    return None, None

def backtest(lb, label):
    """用指定的 LB 值回测"""
    codes = load_pool()
    print(f'\n{"="*60}')
    print(f'  回测方案 {label}: LB={lb} (本周/{-lb}周前-1)')
    print(f'{"="*60}')
    
    # 扫描所有ETF，建立周度信号矩阵
    all_weekly = {}  # week -> list of (code, mom, dev, price)
    
    for code in codes:
        cs, ws = load_history(code)
        if not cs or len(cs) < MA_L + 2:
            continue
        
        for i in range(MA_L, len(cs)):
            w = ws[i]
            if w in SKIP_WEEKS:
                continue
            price = cs[i]
            ma_s = sum(cs[i-MA_S+1:i+1]) / MA_S
            ma_l = sum(cs[i-MA_L+1:i+1]) / MA_L
            dev = price / ma_l - 1
            mom = cs[i] / cs[i-lb] - 1 if i >= lb else None
            
            if mom is None: continue
            if mom <= 0: continue
            if not (price > ma_s > ma_l): continue
            if dev > MAX_DEV / 100.0: continue
            
            # G3过滤
            g3_pass = True
            if i >= 1:
                mom1w = cs[i] / cs[i-1] - 1
                if mom1w < MIN_MOM_1W:
                    g3_pass = False
            if mom <= 0:
                g3_pass = False
            
            if g3_pass:
                if w not in all_weekly:
                    all_weekly[w] = []
                all_weekly[w].append((code, mom, dev, price))
    
    if not all_weekly:
        print('  无信号数据')
        return
    
    # 按动量排序，每周选Top3
    sorted_weeks = sorted(all_weekly.keys())
    portfolio_value = 10000.0
    cash = portfolio_value
    positions = {}  # code -> {shares, cost}
    equity_curve = []
    last_week = None
    
    for w in sorted_weeks:
        signals = sorted(all_weekly[w], key=lambda x: x[1], reverse=True)
        top3 = signals[:3]
        top_codes = set(x[0] for x in top3)
        
        # 更新持仓市值（用本周价格）
        week_prices = {}
        for code, mom, dev, price in signals:
            week_prices[code] = price
        
        pos_value = 0
        for code in list(positions.keys()):
            if code in week_prices:
                pos_value += positions[code]['shares'] * week_prices[code]
        equity_curve.append((w, cash + pos_value))
        
        # 调仓：卖出不在top3的
        for code in list(positions.keys()):
            if code not in top_codes:
                if code in week_prices:
                    proceeds = positions[code]['shares'] * week_prices[code]
                    cash += proceeds
                del positions[code]
        
        # 买入top3（等权）
        target_value = (cash + pos_value) / 3.0
        for code, mom, dev, price in top3:
            if code not in positions:
                shares = target_value // price
                if shares > 0:
                    cost = shares * price
                    cash -= cost
                    positions[code] = {'shares': shares, 'cost': cost}
        
        last_week = w
    
    if not equity_curve:
        print('  无权益曲线')
        return
    
    # 计算指标
    starts = [v for w, v in equity_curve]
    end_val = starts[-1]
    total_ret = end_val / starts[0] - 1
    n_weeks = len(starts)
    n_years = n_weeks / 52.0
    cagr = (end_val / starts[0]) ** (1/n_years) - 1 if n_years > 0 else 0
    
    # 最大回撤
    peak = starts[0]
    max_dd = 0
    for v in starts:
        if v > peak: peak = v
        dd = peak / v - 1
        if dd > max_dd: max_dd = dd
    
    # 夏普
    weekly_rets = [(starts[i]/starts[i-1]-1) for i in range(1, len(starts))]
    if weekly_rets:
        avg = sum(weekly_rets)/len(weekly_rets)
        std = (sum((r-avg)**2 for r in weekly_rets)/len(weekly_rets))**0.5
        sharpe = (avg/std)*(52**0.5) if std > 0 else 0
    else:
        sharpe = 0
    
    print(f'  期末权益: {end_val:,.0f}')
    print(f'  总收益:   {total_ret:+.1%}')
    print(f'  年化:     {cagr:+.1%}')
    print(f'  最大回撤: {max_dd:+.1%}')
    print(f'  夏普:     {sharpe:.2f}')
    print(f'  周数:     {n_weeks}')
    
    return {'cagr': cagr, 'dd': max_dd, 'sharpe': sharpe, 'total': total_ret}

# ===== 主程序 =====
print('开始回测，对比两种动量定义...')
print('A方案: LB=3, 本周/上上周-1 (跨度2周)')
print('B方案: LB=4, 本周/三周前-1 (跨度3周)')

rA = backtest(3, 'A')
rB = backtest(4, 'B')

print(f'\n{"="*60}')
print('  对比结果')
print(f'{"="*60}')
if rA and rB:
    print(f'  A方案(LB=3): 年化={rA["cagr"]:+.1%}, 夏普={rA["sharpe"]:.2f}, 回撤={rA["dd"]:+.1%}')
    print(f'  B方案(LB=4): 年化={rB["cagr"]:+.1%}, 夏普={rB["sharpe"]:.2f}, 回撤={rB["dd"]:+.1%}')
    winner = 'A' if rA['sharpe'] > rB['sharpe'] else 'B'
    print(f'\n  >>> {winner}方案更优 (夏普 {max(rA["sharpe"], rB["sharpe"]):.2f})')
