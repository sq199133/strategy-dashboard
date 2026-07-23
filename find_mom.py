with open(r'D:\Qclaw_Trading\weekly_scan_v4.py', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines, 1):
    s = line.strip()
    if any(k in s for k in ['mom1w', 'mom3w', 'mom8w', 'LB', 'lookback', 'mom_w', '.get(\'mom\'', 'wk[-', 'wk_1', 'wk_3', 'wk_8', 'close_', 'score', 'score_w']):
        print(f'L{i:4d}: {s}')
