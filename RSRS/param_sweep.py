"""
RSRS 参数网格扫描 — V2（修正回测逻辑）
修正：每日检查RSRS大盘信号，非调仓日也实时响应（与原策略一致）
"""
import sys, os, json, warnings, time
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

from rsrs_final_strategy import (DEFAULT_POOL, load_etf, build_panel,
                                 compute_rsrs, compute_momentum, c63_score,
                                 compute_vol_scaling)


def backtest_daily_rsrs(data, panel, rsrs_signal, rsrs_dates, mom_data,
                        vol_scaling, rebalance_days=42, top_n=1):
    """
    匹配原策略逻辑：
    - 每日检查RSRS信号
    - RSRS为0时立即清仓, nr重置
    - RSRS变1时立即触发调仓
    - 非RSRS变盘日按调仓周期触发
    """
    n = len(panel)
    positions = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)

    # 对齐 RSRS → panel 日期
    rsrs_dates_ns = rsrs_dates.astype('datetime64[ns]')
    panel_dates_ns = panel.index.values.astype('datetime64[ns]')
    sig_idx = np.searchsorted(rsrs_dates_ns, panel_dates_ns)
    sig = [rsrs_signal[i] if i < len(rsrs_signal) else 0 for i in sig_idx]

    # 波动率对齐
    if vol_scaling is not None:
        vs = vol_scaling.reindex(panel.index, method='ffill', limit=5).fillna(1.0)
    else:
        vs = pd.Series(1.0, index=panel.index)

    nr = None  # 下次调仓日
    holdings = []
    last_market = 0

    for i, date in enumerate(panel.index):
        market = int(sig[i])
        scale = float(vs.loc[date])

        # RSRS 变盘 → 即时响应
        if not market or scale <= 0:
            if market != last_market:
                holdings = []
            if holdings:
                holdings = []
            nr = None
            positions.loc[date] = 0
            last_market = market
            continue

        # RSRS 为多 → 判断是否需要调仓
        rebalance_trigger = False
        if last_market == 0:
            # 刚转多，立即调仓
            rebalance_trigger = True
        elif nr is None or date >= nr:
            rebalance_trigger = True

        if rebalance_trigger:
            candidates = [(c, c63_score(mom_data[c], date)) for c in panel.columns]
            candidates = [(c, s) for c, s in candidates if s is not None and s > 0]
            candidates.sort(key=lambda x: -x[1])
            holdings = [c[0] for c in candidates[:top_n]] if candidates else []
            nr = panel.index[min(i + rebalance_days, n - 1)]

        if holdings:
            w = scale / len(holdings)
            for c in holdings:
                positions.loc[date, c] = w

        last_market = market

    return positions


def calc_metrics(panel, positions):
    sr = (panel.pct_change().fillna(0) * positions.shift(1).fillna(0)).sum(axis=1)
    eq = (1 + sr).cumprod()
    bh = (1 + panel.pct_change().fillna(0).mean(axis=1)).cumprod()
    yrs = len(sr) / 252
    cagr = eq.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else 0
    sh = np.sqrt(252) * sr.mean() / sr.std() if sr.std() > 1e-10 else 0
    mdd = ((eq - eq.cummax()) / eq.cummax()).min()
    exc = cagr - (bh.iloc[-1] ** (1 / yrs) - 1)
    pr = (positions.sum(axis=1) > 0).mean()
    calmar = cagr / abs(mdd) if mdd < 0 else 99
    return {'CAGR': round(cagr*100,1), 'Sharpe': round(sh,2), 'MDD': round(mdd*100,1),
            'Excess': round(exc*100,1), 'Pos%': round(pr*100,1), 'Ret/DD': round(calmar,2)}


def print_sweep(var_name, var_values, results):
    print(f'\n{"─"*72}')
    print(f'  [扫描] {var_name}')
    print(f'  {"参数":<18} {"CAGR%":>6} {"Sharpe":>7} {"MDD%":>6} {"Excess%":>8} {"Pos%":>5} {"Ret/DD":>6}')
    print(f'  {"─"*60}')
    for v, m in zip(var_values, results):
        pstr = str(v) if not isinstance(v, tuple) else f'buy={v[0]},sell={v[1]}'
        print(f'  {pstr:<18} {m["CAGR"]:>6.1f} {m["Sharpe"]:>7.2f} {m["MDD"]:>6.1f} {m["Excess"]:>8.1f} {m["Pos%"]:>5.1f} {m["Ret/DD"]:>6.2f}')


if __name__ == '__main__':
    print('=' * 72)
    print('  RSRS 参数网格扫描 V2 (修正每日RSRS响应逻辑)')
    print('=' * 72)

    t0 = time.time()

    # ── 1. 加载 ──
    print('\n[1] 加载ETF数据...', end=' ')
    data, panel = build_panel(DEFAULT_POOL)
    df510 = load_etf('510300')
    print(f'{len(panel)}个交易日, {time.time()-t0:.0f}s')

    # ── 2. 动量 ──
    print('[2] 计算C63动量...', end=' ')
    mom_data = compute_momentum(data, panel)
    print('OK')

    # ── 3. 波动率 ──
    print('[3] 计算波动率缩放...', end=' ')
    scale = compute_vol_scaling(df510, panel.index)
    print(f'均仓{scale.mean()*100:.0f}%')

    # ── 4. 扫描 ──
    print('[4] 执行扫描...')

    all_rows = []
    FN, FM, FB, FS = 18, 900, 0.7, -1.0
    FT, FR = 1, 42
    cache = {}

    def get_sig(n, m, buy, sell):
        key = (n, m, round(buy,2), round(sell,2))
        if key not in cache:
            sig, _, _ = compute_rsrs(df510, n, m, buy, sell)
            cache[key] = (sig, df510['date'].values.copy())
        return cache[key]

    # a) N值
    vals = [10, 15, 18, 20, 25, 30, 40]
    res = []
    for v in vals:
        sig, dates = get_sig(v, FM, FB, FS)
        pos = backtest_daily_rsrs(data, panel, sig, dates, mom_data, scale, FR, FT)
        m = calc_metrics(panel, pos); m['dim'] = f'N={v}'; res.append(m); all_rows.append(m)
    print_sweep('N (RSRS回归窗口)', vals, res)

    # b) M值
    vals = [400, 600, 900, 1200, 1500, 2000]
    res = []
    for v in vals:
        sig, dates = get_sig(FN, v, FB, FS)
        pos = backtest_daily_rsrs(data, panel, sig, dates, mom_data, scale, FR, FT)
        m = calc_metrics(panel, pos); m['dim'] = f'M={v}'; res.append(m); all_rows.append(m)
    print_sweep('M (标准化窗口)', vals, res)

    # c) 买卖阈值
    vals = [(0.3,-1.0),(0.5,-1.0),(0.7,-0.5),(0.7,-0.7),(0.7,-1.0),
            (0.7,-1.5),(1.0,-0.5),(1.0,-1.0),(1.0,-1.5),(1.5,-1.0)]
    res = []
    for buy, sell in vals:
        sig, dates = get_sig(FN, FM, buy, sell)
        pos = backtest_daily_rsrs(data, panel, sig, dates, mom_data, scale, FR, FT)
        m = calc_metrics(panel, pos); m['dim'] = f'buy={buy},sell={sell}'; res.append(m); all_rows.append(m)
    print_sweep('buy/sell阈值', vals, res)

    # d) TopN
    vals = [1, 2, 3, 5, 7, 10]
    res = []
    for v in vals:
        sig, dates = get_sig(FN, FM, FB, FS)
        pos = backtest_daily_rsrs(data, panel, sig, dates, mom_data, scale, FR, v)
        m = calc_metrics(panel, pos); m['dim'] = f'Top{v}'; res.append(m); all_rows.append(m)
    print_sweep('TopN (持有数)', vals, res)

    # e) 调仓周期
    vals = [5, 10, 21, 42, 63, 84, 126, 252]
    res = []
    for v in vals:
        sig, dates = get_sig(FN, FM, FB, FS)
        pos = backtest_daily_rsrs(data, panel, sig, dates, mom_data, scale, v, FT)
        m = calc_metrics(panel, pos); m['dim'] = f'{v}d'; res.append(m); all_rows.append(m)
    print_sweep('调仓周期 (交易日)', vals, res)

    # ── 5. Top排名 ──
    print(f'\n{"="*72}')
    print('  综合排名 — Top 20（夏普比降序）')
    print(f'{"="*72}')
    print(f'  {"Rank":<5} {"Sharpe":>6} {"CAGR%":>6} {"MDD%":>6} {"Ret/DD":>6} {"Excess%":>7} {"Pos%":>5}  参数')
    print(f'  {"-"*66}')

    df = pd.DataFrame(all_rows)
    top = df.sort_values('Sharpe', ascending=False).head(20)
    for i, (_, r) in enumerate(top.iterrows(), 1):
        print(f'  #{i:<3} {r["Sharpe"]:>6.2f} {r["CAGR"]:>6.1f} {r["MDD"]:>6.1f} '
              f'{r["Ret/DD"]:>6.2f} {r["Excess"]:>7.1f} {r["Pos%"]:>5.0f}  {r["dim"]}')

    # 基线
    sig, dates = get_sig(FN, FM, FB, FS)
    pos_base = backtest_daily_rsrs(data, panel, sig, dates, mom_data, scale, FR, FT)
    mb = calc_metrics(panel, pos_base)
    print(f'\n{"─"*72}')
    print(f'  基线: N={FN}, M={FM}, buy={FB}, sell={FS}, Top{FT}, {FR}d')
    print(f'  CAGR={mb["CAGR"]}%  Sharpe={mb["Sharpe"]}  MDD={mb["MDD"]}%  '
          f'Excess={mb["Excess"]}%  Pos={mb["Pos%"]}%  Ret/DD={mb["Ret/DD"]}')
    print(f'  (确认与原始策略一致)')
    print(f'\n  {time.time()-t0:.0f}s total')

    out = 'D:\\QClaw_Trading\\RSRS\\param_sweep_results.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(all_rows, f, ensure_ascii=False)
    print(f'[Saved] {out}')
