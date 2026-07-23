import sys
path = 'D:/Qclaw_Trading/weekly_scan_v4.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
# Fix ATR print line that lost its indent when G3 print was removed
old = lines[1163]
lines[1163] = '    print(f"  ATR filter: {ATR_RATIO:.2f} (ATR14/ATR21 < {ATR_RATIO:.2f} -> skip)")\n'
with open(path, 'w', encoding='utf-8', newline='') as f:
    f.writelines(lines)
print(f'Fixed line 1164 (0-indexed 1163)')
print(f'  Old: {old.rstrip()!r}')
print(f'  New: {lines[1163].rstrip()!r}')
