path = 'D:/Qclaw_Trading/weekly_scan_v4.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
# Remove the duplicate ATR print at line 1162 (no indent, bug)
# and keep the correctly-indented one at line 1164
# Line 1162 is index 1161
del lines[1161]
with open(path, 'w', encoding='utf-8', newline='') as f:
    f.writelines(lines)
print(f'Removed duplicate ATR line. File now {len(lines)} lines')
