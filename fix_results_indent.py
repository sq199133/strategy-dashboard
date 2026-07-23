path = 'D:/Qclaw_Trading/weekly_scan_v4.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the results.append({ line that lost its indent
for i, l in enumerate(lines):
    if l.strip() == 'results.append({':
        print(f'Found at line {i+1}: {l.rstrip()!r}')
        lines[i] = '        results.append({\n'
        print(f'Fixed to: {lines[i].rstrip()!r}')
        break

with open(path, 'w', encoding='utf-8', newline='') as f:
    f.writelines(lines)
print(f'Done. File {len(lines)} lines')
