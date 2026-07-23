import sys, json, os, requests, glob
from datetime import datetime, timedelta

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'

MA_S, MA_L = 5, 21
MAX_DEV = 15
MIN_MOM_1W = -0.01
SKIP_WEEKS = {'2024-W01', '2025-W01'}

def load_pool():
    # 文件含NaN，先替换再解析
    with open(POOL_FILE, encoding='utf-8') as f:
        raw = f.read()
    raw = raw.replace('NaN', 'null')
    d = json.loads(raw)
    return [e['code'] for e in d['data']]

def load_history(code):
    for pat in (code, f'sh{code}', f'sz{code}'):
        hits = glob.glob(os.path.join(HISTORY_DIR, f'{pat}.json'))
        if not hits:
            hits = glob.glob(os.path.join(HISTORY_DIR, f'*{code}*.json'))
        if hits:
            try:
                with open(hits[0], encoding='utf-8') as f:
                    raw = f.read()
                raw = raw.replace('NaN', 'null')
                d = json.loads(raw)
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
                # sw = [(w, (ds, close)), ...]
                closes = [close for w, (ds, close) in sw]
                week_ids = [w for w, _ in sw]
                return closes, week_ids
            except Exception as e:
                continue
    return None, None

def backtest(lb, label):
    codes = load_pool()
    print(f'\n{"="*60}')
    print(f'  回测方案 {label}: LB={lb} (本周/{-lb}周前-1, 跨度{lb-1}周)')
    print(f'{"="*60}')

    all_weekly = {}

    for code in codes:
        cs, ws = load_history(code)
        if not cs or len(cs) < MA_L + lb:
            continue

        for i in range(MA_L, len(cs)):
            w = ws[i]
            if w in SKIP_WEEKS:
                continue
            price = cs[i]
            ma_s = sum(cs[i-MA_S+1:i+1]) / MA_S
            ma_l = sum(cs[i-MA_L+1:i+1]) / MA_L
            dev = price / ma_l - 1
            mom = cs[i] / cs[i-lb] - 1

            if mom <= 0: continue
            if not (price > ma_s > ma_l): continue
            if dev > MAX_DEV / 100.0: continue

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
        print('  [WARN] 无信号数据')
        return None

    sorted_weeks = sorted(all_weekly.keys())
    cash = 10000.0
    positions = {}
    equity_curve = []

    for w in sorted_weeks:
        signals = sorted(all_weekly[w], key=lambda x: x[1], reverse=True)
        top3 = signals[:3]
        top_codes = set(x[0] for x in top3)

        week_prices = {x[0]: x[3] for x in signals}

        pos_value = 0
        for code in list(positions.keys()):
            if code in week_prices:
                pos_value += positions[code]['shares'] * week_prices[code]
        equity_curve.append((w, cash + pos_value))

        for code in list(positions.keys()):
            if code not in top_codes:
                if code in week_prices:
                    cash += positions[code]['shares'] * week_prices[code]
                del positions[code]

        target_value = (cash + pos_value) / 3.0
        for code, mom, dev, price in top3:
            if code not in positions:
                shares = int(target_value / price)
                if shares > 0:
                    cost = shares * price
                    cash -= cost
                    positions[code] = {'shares': shares, 'cost': cost}

    starts = [v for w, v in equity_curve]
    if not starts:
        return None

    end_val = starts[-1]
    total_ret = end_val / starts[0] - 1
    n_weeks = len(starts)
    n_years = n_weeks / 52.0
    cagr = (end_val / starts[0]) ** (1/n_years) - 1 if n_years > 0 else 0

    peak = starts[0]
    max_dd = 0
    for v in starts:
        if v > peak: peak = v
        dd = v / peak - 1
        if abs(dd) > abs(max_dd): max_dd = dd

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
    print(f'  信号周数: {n_weeks}')

    return {'cagr': cagr, 'dd': max_dd, 'sharpe': sharpe, 'total': total_ret}

print('开始回测，对比两种动量定义...')
print('A方案: LB=3, 本周/上上周-1 (跨度2周)')
print('B方案: LB=4, 本周/三周前-1 (跨度3周)')

rA = backtest(3, 'A')
rB = backtest(4, 'B')

print(f'\n{"="*60}')
print('  对比结果')
print(f'{"="*60}')
if rA and rB:
    print(f'  A方案(LB=3):  年化={rA["cagr"]:+.1%}, 夏普={rA["sharpe"]:.2f}, 回撤={rA["dd"]:+.1%}')
    print(f'  B方案(LB=4):  年化={rB["cagr"]:+.1%}, 夏普={rB["sharpe"]:.2f}, 回撤={rB["dd"]:+.1%}')
    winner = 'A' if rA['sharpe'] > rB['sharpe'] else 'B'
    print(f'\n  >>> {winner}方案更优 (夏普 {max(rA["sharpe"], rB["sharpe"]):.2f})')
