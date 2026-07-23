#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查513400和510880的成交量"""

import json, glob, statistics
from datetime import datetime

codes = ['513400', '510880']
history_dir = r'D:\QClaw_Trading\data\history_long'

for code in codes:
    matches = glob.glob(f'{history_dir}/*{code}.json')
    if matches:
        with open(matches[0], 'r', encoding='utf-8') as f:
            d = json.load(f)
            recs = d if isinstance(d, list) else d.get('records', [])
            if recs:
                weeks = {}
                for r in recs[-30:]:
                    ds = r['date']
                    vol = r.get('vol', 0)
                    cl = r['close']
                    dt = datetime.strptime(ds, '%Y-%m-%d')
                    y, w, _ = dt.isocalendar()
                    wk = f'{y}-W{w:02d}'
                    if wk not in weeks:
                        weeks[wk] = {'close': cl, 'volume': 0}
                    weeks[wk]['close'] = cl
                    weeks[wk]['volume'] += vol

                sw = sorted(weeks.items())[-6:]
                print(f'{code}:')
                volumes = []
                for w, d in sw:
                    print(f'  {w}: close={d["close"]:.3f}, vol={d["volume"]:,}')
                    volumes.append(d['volume'])

                if len(volumes) >= 2:
                    recent = volumes[-1]
                    ma20 = statistics.mean(volumes[:-1])
                    ratio = recent / ma20 if ma20 > 0 else 0
                    print(f'  量比: {ratio:.2f}x (本周{recent:,} vs 过去{len(volumes)-1}周均量{int(ma20):,})')
                print()
