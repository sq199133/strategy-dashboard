import sys, json, glob
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
POOL_FILE   = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'

MA_S, MA_L = 5, 21
MAX_DEV = 15
MIN_MOM_1W = -0.01
SKIP_WEEKS = {'2024-W01', '2025-W01'}

# ── 加载标的池 ──────────────────────────────────────────────
def load_pool():
    with open(POOL_FILE, encoding='utf-8') as f:
        raw = f.read().replace('NaN', 'null')
    d = json.loads(raw)
    return [e['code'] for e in d['data']]

# ── 加载周线收盘价 ─────────────────────────────────────────
def load_weeks(code):
    for pat in (code, f'sh{code}', f'sz{code}'):
        hits = glob.glob(fr'{HISTORY_DIR}\{pat}.json')
        if not hits:
            hits = glob.glob(fr'{HISTORY_DIR}\*{code}*.json')
        if hits:
            try:
                with open(hits[0], encoding='utf-8') as f:
                    raw = f.read().replace('NaN', 'null')
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
                    except:
                        pass
                sw = sorted(weeks.items())   # [(w, (ds, close)), ...]
                closes = [close for w, (ds, close) in sw]
                weekids = [w for w, _ in sw]
                return closes, weekids
            except:
                continue
    return None, None

# ── 回测核心 ───────────────────────────────────────────────
def backtest(lb, label):
    codes = load_pool()
    print(f'\n{"="*60}')
    print(f'  {label}: LB={lb}  (mom = 本周/{-lb}周前 - 1，跨度{lb-1}周)')
    print(f'{"="*60}')

    # 构建每周的信号列表:  week -> [(code, mom, price), ...]
    weekly = {}
    for code in codes:
        cs, ws = load_weeks(code)
        if not cs or len(cs) < MA_L + lb:
            continue
        for i in range(MA_L, len(cs)):
            w = ws[i]
            if w in SKIP_WEEKS:
                continue
            price = cs[i]
            ma_s  = sum(cs[i-MA_S+1:i+1]) / MA_S
            ma_l  = sum(cs[i-MA_L+1:i+1]) / MA_L
            dev   = price / ma_l - 1
            mom   = cs[i] / cs[i-lb] - 1

            if mom <= 0:          continue
            if not (price > ma_s > ma_l): continue
            if dev > MAX_DEV/100: continue

            # G3
            g3 = True
            if i >= 1:
                if cs[i]/cs[i-1]-1 < MIN_MOM_1W: g3 = False
            if mom <= 0: g3 = False
            if not g3: continue

            weekly.setdefault(w, []).append((code, mom, price))

    if not weekly:
        print('  [WARN] 无信号')
        return None

    # ── 按周回测 ──────────────────────────────────────────
    sorted_weeks = sorted(weekly.keys())
    cash     = 10000.0
    positions = {}          # code -> {'shares': N, 'cost': total_cost}
    equity    = []         # [(week, value)]

    for w in sorted_weeks:
        signals = sorted(weekly[w], key=lambda x: x[1], reverse=True)
        top3    = signals[:3]
        held     = set(positions.keys())
        target   = set(x[0] for x in top3)

        # 本周价格映射
        px = {x[0]: x[2] for x in signals}

        # 记录当前权益
        pos_val = sum(positions[c]['shares'] * px[c] for c in positions if c in px)
        equity.append((w, cash + pos_val))

        # 卖出不在 target 的持仓
        for c in list(positions.keys()):
            if c not in target and c in px:
                cash += positions[c]['shares'] * px[c]
                del positions[c]

        # 买入 target 中未持有的（等权分配）
        new_cash = cash + pos_val   # 调仓前总市值
        for c, mom, price in top3:
            if c not in positions:
                alloc = new_cash / 3.0
                shares = int(alloc / price)
                if shares > 0:
                    cost = shares * price
                    cash -= cost
                    positions[c] = {'shares': shares, 'cost': cost}

    if not equity:
        return None

    vals = [v for w, v in equity]
    total_ret = vals[-1] / vals[0] - 1
    years = len(vals) / 52.0
    cagr  = (vals[-1]/vals[0]) ** (1/years) - 1 if years > 0 and vals[-1] > 0 else -9.99

    # 最大回撤
    peak = vals[0]
    max_dd = 0
    for v in vals:
        if v > peak: peak = v
        dd = (peak - v) / peak
        if dd > max_dd: max_dd = dd

    # 夏普
    rets = [(vals[i]/vals[i-1]-1) for i in range(1, len(vals))]
    if rets:
        avg  = sum(rets)/len(rets)
        std  = (sum((r-avg)**2 for r in rets)/len(rets))**0.5
        sharpe = (avg/std)*(52**0.5) if std > 0 else 0
    else:
        sharpe = 0

    print(f'  期末:   {vals[-1]:,.0f}')
    print(f'  总收益: {total_ret:+.1%}')
    print(f'  年化:   {cagr:+.1%}')
    print(f'  最大回撤: {max_dd:+.1%}')
    print(f'  夏普:   {sharpe:.2f}')
    print(f'  周数:   {len(vals)}')
    return {'cagr': cagr, 'dd': max_dd, 'sharpe': sharpe}

print('回测开始...')
rA = backtest(3, 'A方案: LB=3  (本周/上上周, 跨度2周)')
rB = backtest(4, 'B方案: LB=4  (本周/三周前, 跨度3周)')

print(f'\n{"="*60}')
print('  对比')
print(f'{"="*60}')
if rA and rB:
    print(f'  A(LB=3):  年化={rA["cagr"]:+.1%}  夏普={rA["sharpe"]:.2f}  回撤={rA["dd"]:+.1%}')
    print(f'  B(LB=4):  年化={rB["cagr"]:+.1%}  夏普={rB["sharpe"]:.2f}  回撤={rB["dd"]:+.1%}')
    w = 'A' if rA['sharpe'] > rB['sharpe'] else 'B'
    print(f'\n  >>> {w}方案更优')
