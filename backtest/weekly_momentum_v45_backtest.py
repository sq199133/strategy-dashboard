#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周线动量策略 v4.5 规范回测 (v2 - 修复全局周序列)
====================================================
修复内容:
- 构建全局周序列 (所有ETF的周取并集, 排序)
- 用周字符串查找指标, 不用索引
- 支持不同ETF有不同数据起始时间
- 回测窗口: 从有足够ETF(>=TOP_N)的最早周开始

策略逻辑 (严格对齐 weekly_scan_v4.py):
- 评分: 40%*mom1w + 40%*mom3w + 20%*mom8w
- 过滤: score>0, close>MA5, MA5>MA21, dev<=15%, atr_ratio>=0.85
- 持仓: 等权TOP3, 每周调仓
- 止损: 成本-8% 或 高点回撤-10% (用下周open执行)
"""

import json, os, sys, glob, statistics
from datetime import datetime as dt_mod
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# =====================================================================
# 参数
# =====================================================================
HISTORY_DIR = r'D:\QClaw_Trading\data\history_long_v2'
POOL_FILE   = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'

MA_S       = 5
MA_L       = 21
MAX_DEV    = 15
TOP_N      = 3
ATR_THRESH = 0.85

SCORE_W1 = 0.4
SCORE_W3 = 0.4
SCORE_W8 = 0.2

BACKTEST_START = '2011-W01'   # 候选起始, 实际从有足够数据的第一周开始
BACKTEST_END   = '2026-W30'

INITIAL_CASH = 1_000_000.0

STOP_COST_PCT = -0.08   # 成本 -8%
STOP_HWM_PCT = -0.10   # 高点 -10%

# =====================================================================
# 数据加载
# =====================================================================
def load_pool():
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        d = json.load(f)
    return d.get('data', d.get('etfs', []))

def load_weekly_data(code):
    """加载本地周线文件, 返回 list of dict (按周排序)"""
    search_dir = HISTORY_DIR
    # 尝试多种文件名
    patterns = [
        f'{code}.json',
        f'sh{code}.json',
        f'sz{code}.json',
    ]
    found = []
    for pat in patterns:
        found = glob.glob(os.path.join(search_dir, pat))
        if found:
            break
    # 如果还找不到, 模糊搜索
    if not found:
        found = glob.glob(os.path.join(search_dir, f'*{code}*.json'))
    if not found:
        return None

    fp = found[0]
    try:
        with open(fp, 'r', encoding='utf-8') as f:
            raw = f.read().replace('NaN', 'null')
        d = json.loads(raw)
        recs = d.get('records', []) if isinstance(d, dict) else d
        weeks = []
        for r in recs:
            if isinstance(r, dict):
                w = r.get('w', '')
                dt = r.get('date', '')
                if not w or not dt:
                    continue
                weeks.append({
                    'week':     w,
                    'date_end': dt,
                    'close':    float(r.get('close', 0)),
                    'open':     float(r.get('open', 0)),
                    'high':     float(r.get('high', 0)),
                    'low':      float(r.get('low', 0)),
                })
        weeks.sort(key=lambda x: x['week'])
        return weeks
    except Exception as e:
        return None

# =====================================================================
# 指标计算 (对齐 weekly_scan_v4.py calc())
# =====================================================================
def compute_indicators(weeks):
    """
    计算周线指标
    返回: week_to_ind (dict: week_str -> indicator_dict)
          week_list   (list: 按时间排序的周字符串, 对应indicators)
          indicators  (list: 与week_list对齐的指标dict, None表示该周无指标)
    """
    n = len(weeks)
    if n < MA_L + 1:
        return {}, [], []

    closes = [w['close'] for w in weeks]
    highs  = [w['high']  for w in weeks]
    lows   = [w['low']   for w in weeks]
    week_strs = [w['week'] for w in weeks]

    # 预计算 ATR ratio
    atr_ratios = {}
    for i in range(21, n):
        trs = []
        for j in range(i - 20, i + 1):
            h = highs[j]
            l = lows[j]
            pc = closes[j - 1]
            tr = max(h - l, abs(h - pc), abs(l - pc))
            trs.append(tr)
        fast = sum(trs[-14:]) / 14.0
        slow = sum(trs) / 21.0
        if slow > 0:
            atr_ratios[i] = fast / slow

    # 计算指标 (i >= MA_L)
    indicators = [None] * n
    for i in range(MA_L, n):
        ma5  = sum(closes[i-MA_S+1:i+1]) / MA_S
        ma21 = sum(closes[i-MA_L+1:i+1]) / MA_L

        mom1w = (closes[i] / closes[i-1] - 1) if i >= 1 else None
        mom3w = (closes[i] / closes[i-3] - 1) if i >= 3 else None
        mom8w = (closes[i] / closes[i-7] - 1) if i >= 7 else None

        if mom1w is not None and mom3w is not None and mom8w is not None:
            score = SCORE_W1 * mom1w + SCORE_W3 * mom3w + SCORE_W8 * mom8w
        else:
            score = mom3w

        dev = (closes[i] / ma21 - 1) if ma21 > 0 else None
        atr_r = atr_ratios.get(i, None) if ATR_THRESH else None

        indicators[i] = {
            'week':      week_strs[i],
            'date_end':  weeks[i]['date_end'],
            'close':     closes[i],
            'open':      weeks[i]['open'],
            'high':      weeks[i]['high'],
            'low':       weeks[i]['low'],
            'ma5':       ma5,
            'ma21':      ma21,
            'mom1w':     mom1w,
            'mom3w':     mom3w,
            'mom8w':     mom8w,
            'score':     score,
            'dev':       dev,
            'atr_ratio': atr_r,
        }

    # 构建 week -> indicator 映射
    week_to_ind = {}
    for i, ind in enumerate(indicators):
        if ind is not None:
            week_to_ind[week_strs[i]] = ind

    return week_to_ind, week_strs, indicators

def check_filters(ind):
    """对齐 weekly_scan_v4.py check()"""
    if ind is None:
        return False
    c1 = ind['score'] is not None and ind['score'] > 0
    c2 = ind['close'] > ind['ma5'] and ind['ma5'] > ind['ma21']
    c3 = ind['dev'] is not None and ind['dev'] <= MAX_DEV / 100.0
    c4 = True
    if ATR_THRESH is not None:
        ar = ind.get('atr_ratio')
        c4 = ar is None or ar >= ATR_THRESH
    return c1 and c2 and c3 and c4

# =====================================================================
# 主回测
# =====================================================================
def main():
    print('=' * 62)
    print('  周线动量策略 v4.5 规范回测 v2')
    print(f'  评分: w1={SCORE_W1} w3={SCORE_W3} w8={SCORE_W8}')
    print(f'  过滤: MA5>MA21, close>MA5, dev<={MAX_DEV}%, ATR>={ATR_THRESH}')
    print(f'  持仓: 等权TOP{TOP_N}, 止损: 成本{STOP_COST_PCT:.0%} 或 高点{STOP_HWM_PCT:.0%}')
    print('=' * 62)
    print()

    # 1. 加载ETF池
    etfs = load_pool()
    print(f'ETF池: {len(etfs)} 只')

    # 2. 加载数据并计算指标
    all_week_to_ind = {}  # code -> {week: ind}
    all_weeks_list  = {}  # code -> list of week strings
    all_weeks_dict  = {}  # code -> {week: weekly_bar}
    code_info = {}

    loaded = 0
    skipped = 0
    for etf in etfs:
        code = etf['code']
        name = etf.get('name', code)
        cat  = etf.get('category', '')
        code_info[code] = {'name': name, 'cat': cat}

        weeks = load_weekly_data(code)
        if weeks is None or len(weeks) < MA_L + 2:
            skipped += 1
            continue

        week_to_ind, week_strs, indicators = compute_indicators(weeks)
        if not week_to_ind:
            skipped += 1
            continue

        all_week_to_ind[code] = week_to_ind
        all_weeks_list[code]  = week_strs
        # 构建 week -> bar 映射 (用于执行价格)
        wd = {}
        for w in weeks:
            wd[w['week']] = w
        all_weeks_dict[code] = wd
        loaded += 1

    print(f'  加载成功: {loaded}/{len(etfs)}, 缺失: {skipped}')
    print()

    if loaded == 0:
        print('无可用数据, 退出')
        return

    # 3. 构建全局周序列
    #    收集所有ETF的所有周, 排序去重
    master_week_set = set()
    for code in all_week_to_ind:
        master_week_set.update(all_weeks_list[code])
    master_weeks = sorted(master_week_set)

    # 过滤评估窗口
    eval_weeks = [w for w in master_weeks if BACKTEST_START <= w <= BACKTEST_END]

    # 找到有足够ETF参与的起始周
    # 要求: 至少有TOP_N只ETF在该周有有效指标
    min_data_weeks = []
    for w in eval_weeks:
        n_valid = sum(1 for code in all_week_to_ind if w in all_week_to_ind[code])
        if n_valid >= TOP_N:
            min_data_weeks.append(w)
        else:
            pass  # 跳过ETF数量不足的周

    if not min_data_weeks:
        print('没有足够ETF数据的周')
        return

    # 实际使用评估窗口
    eval_start = min_data_weeks[0]
    eval_end   = min_data_weeks[-1]
    print(f'  实际评估窗口: {eval_start} ~ {eval_end}')
    print(f'  评估周数: {len(min_data_weeks)}')
    print()

    # 4. 回测主循环
    #    逻辑: 每周五收盘后扫描 -> 下周开盘执行
    #    实现: 对周i生成信号, 在周i+1执行
    cash = INITIAL_CASH
    portfolio = {}  # code -> {'shares', 'buy_price', 'hwm', 'entry_date', 'entry_week'}
    equity_curve = []
    trade_history = []

    # 遍历评估窗口的每一周 (除了最后一周, 因为需要下周执行)
    for pos in range(len(min_data_weeks) - 1):
        sig_week  = min_data_weeks[pos]       # 信号周 (周五收盘后扫描)
        exec_week = min_data_weeks[pos + 1]   # 执行周 (下周一开盘)

        # --- 更新持仓HWM (用信号周close) ---
        for code in list(portfolio.keys()):
            ind = all_week_to_ind.get(code, {}).get(sig_week)
            if ind:
                if ind['close'] > portfolio[code]['hwm']:
                    portfolio[code]['hwm'] = ind['close']

        # --- 止损检查 (用信号周的low检查是否触发) ---
        to_sell = []
        for code, pos_info in list(portfolio.items()):
            ind = all_week_to_ind.get(code, {}).get(sig_week)
            if not ind:
                continue
            cost_stop = pos_info['buy_price'] * (1 + STOP_COST_PCT)
            hwm_stop  = pos_info['hwm'] * (1 + STOP_HWM_PCT)
            # 用low检查: 如果本周low触及止损线, 则触发
            if ind['low'] <= cost_stop or ind['low'] <= hwm_stop:
                to_sell.append(('stop', code))

        # 执行止损卖出 (在执行周开盘)
        for reason, code in to_sell:
            if code not in portfolio:
                continue
            pos_info = portfolio.pop(code)
            bar = all_weeks_dict.get(code, {}).get(exec_week)
            exec_price = bar['open'] if bar else pos_info['buy_price']

            pnl = pos_info['shares'] * (exec_price - pos_info['buy_price'])
            pnl_pct = (exec_price / pos_info['buy_price'] - 1) * 100

            trade_history.append({
                'entry_date':  pos_info['entry_date'],
                'exit_date':   bar['date_end'] if bar else exec_week,
                'side':        'long',
                'size':        pos_info['shares'],
                'entry_price': pos_info['buy_price'],
                'exit_price':  exec_price,
                'pnl':         pnl,
                'pnl_pct':     pnl_pct,
                'holding_bars': _count_weeks(min_data_weeks, pos_info['entry_week'], sig_week),
                'symbol':      code,
                'symbol_name': code_info.get(code, {}).get('name', code),
                'reason':      'stop_loss',
            })
            cash += pos_info['shares'] * exec_price

        # --- 每周扫描: 生成候选列表 ---
        candidates = []
        for code in all_week_to_ind:
            ind = all_week_to_ind[code].get(sig_week)
            if ind is None:
                continue
            if not check_filters(ind):
                continue
            candidates.append({'code': code, 'score': ind['score']})

        # 按评分排序 + 同类别去重
        candidates.sort(key=lambda x: x['score'], reverse=True)
        seen_cats = set()
        target_codes = []
        for c in candidates:
            cat = code_info.get(c['code'], {}).get('category', '') or c['code']
            if cat not in seen_cats:
                seen_cats.add(cat)
                target_codes.append(c['code'])
                if len(target_codes) >= TOP_N:
                    break

        # --- 调仓: 不在target里的持仓卖出 ---
        to_sell_rebal = [code for code in portfolio if code not in set(target_codes)]
        for code in to_sell_rebal:
            if code not in portfolio:
                continue
            pos_info = portfolio.pop(code)
            bar = all_weeks_dict.get(code, {}).get(exec_week)
            exec_price = bar['open'] if bar else pos_info['buy_price']

            pnl = pos_info['shares'] * (exec_price - pos_info['buy_price'])
            pnl_pct = (exec_price / pos_info['buy_price'] - 1) * 100

            trade_history.append({
                'entry_date':  pos_info['entry_date'],
                'exit_date':   bar['date_end'] if bar else exec_week,
                'side':        'long',
                'size':        pos_info['shares'],
                'entry_price': pos_info['buy_price'],
                'exit_price':  exec_price,
                'pnl':         pnl,
                'pnl_pct':     pnl_pct,
                'holding_bars': _count_weeks(min_data_weeks, pos_info['entry_week'], sig_week),
                'symbol':      code,
                'symbol_name': code_info.get(code, {}).get('name', code),
                'reason':      'rebalance_out',
            })
            cash += pos_info['shares'] * exec_price

        # --- 买入新标的 ---
        new_codes = [code for code in target_codes if code not in portfolio]
        if new_codes and cash > 0:
            alloc = cash / TOP_N
            for code in new_codes:
                bar = all_weeks_dict.get(code, {}).get(exec_week)
                if not bar or bar['open'] <= 0:
                    continue
                exec_price = bar['open']

                shares = alloc / exec_price
                cost = shares * exec_price
                if cost > cash:
                    shares = cash / exec_price
                    cost = shares * exec_price
                if shares <= 0:
                    break

                cash -= cost
                portfolio[code] = {
                    'shares':       shares,
                    'buy_price':    exec_price,
                    'hwm':          exec_price,
                    'entry_date':   bar['date_end'],
                    'entry_week':   exec_week,
                }

        # --- 记录权益 (用执行周收盘) ---
        eq_value = cash
        for code, pos_info in portfolio.items():
            # 用执行周的close
            ind = all_week_to_ind.get(code, {}).get(exec_week)
            if ind:
                eq_value += pos_info['shares'] * ind['close']
            else:
                # 如果执行周没有指标 (数据缺口), 用buy_price估算
                bar = all_weeks_dict.get(code, {}).get(exec_week)
                if bar:
                    eq_value += pos_info['shares'] * bar['close']
                else:
                    eq_value += pos_info['shares'] * pos_info['buy_price']
        equity_curve.append({
            'date': _get_date_from_week(all_weeks_dict, target_codes + list(portfolio.keys()), exec_week),
            'value': eq_value,
        })

    # 5. 期末强制平仓
    if portfolio:
        last_week = min_data_weeks[-1]
        for code, pos_info in list(portfolio.items()):
            ind = all_week_to_ind.get(code, {}).get(last_week)
            if ind:
                exit_price = ind['close']
                exit_date = ind['date_end']
            else:
                bar = all_weeks_dict.get(code, {}).get(last_week)
                exit_price = bar['close'] if bar else pos_info['buy_price']
                exit_date = bar['date_end'] if bar else last_week

            pnl = pos_info['shares'] * (exit_price - pos_info['buy_price'])
            pnl_pct = (exit_price / pos_info['buy_price'] - 1) * 100

            trade_history.append({
                'entry_date':  pos_info['entry_date'],
                'exit_date':   exit_date,
                'side':        'long',
                'size':        pos_info['shares'],
                'entry_price': pos_info['buy_price'],
                'exit_price':  exit_price,
                'pnl':         pnl,
                'pnl_pct':     pnl_pct,
                'holding_bars': _count_weeks(min_data_weeks, pos_info['entry_week'], last_week),
                'symbol':      code,
                'symbol_name': code_info.get(code, {}).get('name', code),
                'reason':      'period_end',
            })
            cash += pos_info['shares'] * exit_price
        portfolio.clear()
        if equity_curve:
            equity_curve[-1]['value'] = cash

    # 6. 输出结果
    print('=' * 62)
    print(f'  回测完成, 交易次数: {len(trade_history)}')
    print('=' * 62)
    print()

    summary = compute_summary(equity_curve, trade_history, INITIAL_CASH)
    print('=' * 62)
    print('  回测结果摘要')
    print('=' * 62)
    print(f'  累计收益:  {summary["total_return_pct"]:+.1f}%')
    print(f'  年化收益:  {summary["annual_return_pct"]:+.1f}%')
    print(f'  最大回撤:  {summary["max_drawdown_pct"]:.1f}%')
    print(f'  夏普比率:  {summary["sharpe"]:.2f}')
    print(f'  胜率:      {summary["win_rate_pct"]:.1f}%')
    print(f'  交易次数:  {summary["total_trades"]}')
    print()

    write_outputs(equity_curve, trade_history, summary, eval_start, eval_end)
    return equity_curve, trade_history, summary

# =====================================================================
# 辅助函数
# =====================================================================
def _count_weeks(master, start_week, end_week):
    """计算持有周数"""
    try:
        s = master.index(start_week)
        e = master.index(end_week)
        return e - s
    except ValueError:
        return 0

def _get_date_from_week(all_weeks_dict, codes, week):
    """从任意持仓ETF获取某周的日期"""
    for code in codes:
        bar = all_weeks_dict.get(code, {}).get(week)
        if bar:
            return bar['date_end']
    return week

def compute_summary(equity_curve, trade_history, initial_cash):
    if not equity_curve:
        return {'total_return_pct': 0, 'annual_return_pct': 0,
                'max_drawdown_pct': 0, 'sharpe': 0,
                'win_rate_pct': 0, 'total_trades': 0}
    eqs = [pt['value'] for pt in equity_curve]
    init_val = eqs[0]
    final_val = eqs[-1]
    total_ret = (final_val / init_val - 1) * 100

    n = len(eqs)
    years = n / 52.0
    ann_ret = ((final_val / init_val) ** (1.0 / years) - 1) * 100 if years > 0 else 0

    peak = eqs[0]
    max_dd = 0
    for eq in eqs:
        if eq > peak:
            peak = eq
        dd = (eq / peak - 1) * 100
        if dd < max_dd:
            max_dd = dd

    w_rets = [eqs[i] / eqs[i-1] - 1 for i in range(1, n) if eqs[i-1] > 0]
    if len(w_rets) > 1:
        avg_w = statistics.mean(w_rets)
        std_w = statistics.stdev(w_rets)
        sharpe = (avg_w * 52.0) / (std_w * (52.0 ** 0.5)) if std_w > 0 else 0
    else:
        sharpe = 0

    winning = sum(1 for t in trade_history if t.get('pnl', 0) > 0)
    win_rate = winning / len(trade_history) * 100 if trade_history else 0

    return {'total_return_pct': total_ret, 'annual_return_pct': ann_ret,
            'max_drawdown_pct': max_dd, 'sharpe': sharpe,
            'win_rate_pct': win_rate, 'total_trades': len(trade_history)}

def write_outputs(equity_curve, trade_history, summary, start, end):
    import csv, json

    with open('weekly_momentum_v45_equity.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['date', 'value'])
        for pt in equity_curve:
            writer.writerow([pt['date'], round(pt['value'], 2)])

    with open('weekly_momentum_v45_trades.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['entry_date', 'exit_date', 'side', 'size',
                         'entry_price', 'exit_price', 'pnl', 'pnl_pct',
                         'holding_bars', 'symbol', 'symbol_name', 'reason'])
        for t in trade_history:
            writer.writerow([
                t.get('entry_date', ''),
                t.get('exit_date', ''),
                t.get('side', 'long'),
                round(t.get('size', 0), 4),
                round(t.get('entry_price', 0), 4),
                round(t.get('exit_price', 0), 4),
                round(t.get('pnl', 0), 2),
                round(t.get('pnl_pct', 0), 2),
                t.get('holding_bars', 0),
                t.get('symbol', ''),
                t.get('symbol_name', ''),
                t.get('reason', ''),
            ])

    payload = {
        'meta': {
            'strategy_name': '周线动量策略v4.5',
            'symbol': 'ETF Pool (195只)',
            'start': start,
            'end': end,
            'initial_cash': INITIAL_CASH,
            'market': 'china_a',
            'generated_at': dt_mod.now().isoformat(),
        },
        'summary': summary,
    }
    with open('weekly_momentum_v45_summary.json', 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print('已生成文件:')
    print('  - weekly_momentum_v45_equity.csv')
    print('  - weekly_momentum_v45_trades.csv')
    print('  - weekly_momentum_v45_summary.json')

if __name__ == '__main__':
    main()
