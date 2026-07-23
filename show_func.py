with open(r'D:\Qclaw_Trading\weekly_scan_v4.py', encoding='utf-8') as f:
    lines = f.readlines()

# Show lines 763-810
for i in range(762, 820):
    print(f'L{i+1:4d}: {lines[i].rstrip()}')
