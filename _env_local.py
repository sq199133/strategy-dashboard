#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, datetime, glob, os
sys.stdout.reconfigure(encoding='utf-8')
HIST = r"D:\Qclaw_Trading\data\history_long_v2"

def weekly_close(code):
    for path in [os.path.join(HIST, code+'.json'), *glob.glob(os.path.join(HIST,'*'+code+'.json'))]:
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                d = json.loads(f.read().replace('NaN','null'))
            recs = d.get('records',[]) if isinstance(d,dict) else d
            weeks = {}
            for r in recs:
                ds = r.get('date','')
                if not ds: continue
                y,wn,_ = datetime.datetime.strptime(ds,'%Y-%m-%d').isocalendar()
                wk = f'{y}-W{wn:02d}'
                if wk not in weeks or ds > weeks[wk][0]:
                    weeks[wk]=(ds,r.get('close',0))
            sr = sorted(weeks.items())
            return {wk:v[1] for wk,v in sr}
    return {}

benchmarks = [
    ('510300','沪深300ETF'),('510500','中证500ETF'),('159949','创业板50ETF'),
    ('563300','中证2000ETF'),('560570','A500ETF'),
]
sectors = [
    ('560080','中药ETF'),('159837','生物科技ETF'),('512010','医药ETF'),
    ('159928','消费ETF'),('515750','科技50ETF'),('588000','科创50ETF'),
]
print("="*72)
print("  大环境（宽基ETF本周涨跌，07-10→07-17）")
print("="*72)
print(f"{'名称':<14}{'07-10':>9}{'07-17':>9}{'周涨跌':>9}")
for code,name in benchmarks:
    w = weekly_close(code)
    if '2026-W28' in w and '2026-W29' in w:
        p10,p17 = w['2026-W28'], w['2026-W29']
        chg = (p17/p10-1)*100
        print(f"{name:<14}{p10:>9.3f}{p17:>9.3f}{chg:>+8.2f}%")
print()
print("="*72)
print("  板块对比（医药/消费/科技本周表现）")
print("="*72)
print(f"{'名称':<14}{'07-10':>9}{'07-17':>9}{'周涨跌':>9}")
for code,name in sectors:
    w = weekly_close(code)
    if '2026-W28' in w and '2026-W29' in w:
        p10,p17 = w['2026-W28'], w['2026-W29']
        chg = (p17/p10-1)*100
        flag = '  <== 逆势强' if chg>0 else ''
        print(f"{name:<14}{p10:>9.3f}{p17:>9.3f}{chg:>+8.2f}%{flag}")
