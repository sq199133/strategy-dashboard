"""Quick view of backtest_v5_qual_sizer.py key sections"""
import sys; sys.stdout.reconfigure(encoding='utf-8')
c = open(r'D:\Qclaw_Trading\backtest_v5_qual_sizer.py','rb').read().decode('utf-8')

# Find the scoring/sorting section
for kw in ['# sort', '# score', '# filter', '# rank', 'def check_qualify', 'def run(', '# compute', '# precompute']:
    idx = 0
    while True:
        idx = c.find(kw, idx+1)
        if idx < 0: break
        print(f'--- {kw!r} at {idx} ---')
        print(c[idx:idx+300])
        print()
