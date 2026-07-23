import json
import pandas as pd
import numpy as np
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from rsrs_final_strategy import (DEFAULT_POOL, DATA_DIR, load_etf, build_panel,
                                 compute_rsrs, compute_momentum, c63_score,
                                 compute_vol_scaling)

# 1. 加载全部池标的数据
data, panel = build_panel(DEFAULT_POOL, min_rows=400)
print(f'panel 范围: {panel.index[0].date()} ~ {panel.index[-1].date()}')

# 查看各ETF的最晚日期
for code in DEFAULT_POOL:
    df = load_etf(code)
    print(f'  {code} {DEFAULT_POOL[code]}: {df.date.min().date()} ~ {df.date.max().date()}  ({len(df)}条)')

print(f'\npanel 起始: {panel.index[0].date()}  终止: {panel.index[-1].date()}  ({len(panel)}条)')

# 看2026年数据范围
p2026 = panel[panel.index >= '2026-01-01']
print(f'\n2026年panel交易日: {len(p2026)}')
if len(p2026) > 0:
    print(f'  范围: {p2026.index[0].date()} ~ {p2026.index[-1].date()}')
else:
    print('  panel中无2026年数据，需要降低min_rows')
