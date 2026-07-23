"""
当前交易建议：RSRS信号 + C63选股 + 波动率仓位
"""
import json, os, sys, warnings
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

from rsrs_final_strategy import (DEFAULT_POOL, DATA_DIR, load_etf, build_panel,
                                 compute_rsrs, compute_momentum, c63_score,
                                 compute_vol_scaling, run_strategy)

N, M, BUY, SELL = 18, 900, 0.7, -1.0
TOP, RB, VW, TV = 1, 42, 70, 0.16

today = pd.Timestamp('2026-06-16')

print('=' * 55)
print('  RSRS + C63 + 波动率 - 当前交易建议')
print(f'  {today.date()}')
print('=' * 55)

# 1. RSRS
print('\n[1] RSRS 大盘择时')
df510 = load_etf('510300')
sig, zscore, beta = compute_rsrs(df510, N, M, BUY, SELL)
latest_idx = len(df510) - 1
latest_date = df510['date'].iloc[latest_idx]
latest_sig = int(sig[latest_idx])
latest_z = zscore[latest_idx]
last_beta = beta[latest_idx]
print(f'  沪深300最新: {latest_date.date()}')
print(f'  RSRS beta = {last_beta:.4f}')
print(f'  RSRS z-score = {latest_z:.2f}')
msg = 'LONG - 持有' if latest_sig else 'FLAT - 空仓'
print(f'  信号 = {msg}')

if not latest_sig:
    print('\n  *** 当前空仓信号，无买入建议 ***')
    sys.exit(0)

# 2. C63
print('\n[2] C63 动量选股')
data, panel = build_panel(DEFAULT_POOL, min_rows=200)
mom_data = compute_momentum(data, panel)

candidates = []
for code in DEFAULT_POOL:
    try:
        score = c63_score(mom_data[code], today)
        if score is not None:
            candidates.append((code, DEFAULT_POOL[code], score))
    except:
        pass

candidates.sort(key=lambda x: -x[2])

print('  得分排序:')
for code, name, score in candidates:
    ok = ' Y' if score > 0 else '  '
    print(f'    {code:>6} {name:<10} C63={score:+.4f}  {ok}')

print(f'\n  Top {TOP} 选入:')
selected = [c for c in candidates if c[2] > 0][:TOP]
if selected:
    for code, name, score in selected:
        print(f'    >> {code} {name}  C63={score:+.4f}')
else:
    print('    >> 无正动量ETF，建议空仓')
    sys.exit(0)

# 3. 波动率
print('\n[3] 波动率仓位管理')
scale = compute_vol_scaling(df510, panel.index, VW, TV)
latest_scale = float(scale.loc[today]) if today in scale.index else 1.0
print(f'  当前波动率缩放因子: {latest_scale:.2f}')
print(f'  建议仓位比例: {latest_scale*100:.0f}%')

# 4. 综合
print(f'\n{"="*55}')
print(f'  *** 综合交易建议 ***')
print(f'{"="*55}')
for code, name, score in selected:
    pct = latest_scale * 100
    print(f'')
    print(f'  买入: {code} {name}')
    print(f'  仓位: {pct:.0f}% (波动率缩放后)')
    print(f'  理由: RSRS看多 + C63全池第1({score:+.4f}) + 波动率缩放{latest_scale:.2f}')
    print(f'')
print(f'  持仓周期: 至下次调仓日或RSRS转空')
print(f'  止损条件: RSRS信号转空(z-score < {SELL}) 或 日跌幅超-7%')
print(f'{"="*55}')

# 保存
out = {
    'date': str(today.date()),
    'rsrs': {'beta': round(last_beta,4), 'zscore': round(latest_z,2), 'signal': 'long' if latest_sig else 'flat'},
    'c63_rank': [{'code':c, 'name':n, 'score':round(s,4)} for c,n,s in candidates],
    'selected': [{'code':c, 'name':n, 'score':round(s,4)} for c,n,s in selected],
    'volatility_scale': round(latest_scale, 2),
    'position_pct': round(latest_scale * 100, 0),
}
with open('D:\\QClaw_Trading\\RSRS\\trade_signal.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f'\n[已保存] trade_signal.json')
