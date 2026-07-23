#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
os.chdir(r'D:\Qclaw_Trading')
with open('weekly_scan_v4.py', 'r', encoding='utf-8', newline='') as f:
    content = f.read()

# Remove G3 filter block
idx = content.find('g3_pass = True')
if idx > 0:
    # Find start: look backwards for the G3 comment or blank line after check()
    # Search backward for '        # G3' or '        g3_pass'
    start = content.rfind('        # G3', 0, idx)
    # Find end: look forward for '        ok = ok and g3_pass'
    end_marker = '        ok = ok and g3_pass'
    end = content.find(end_marker, idx)
    if end > 0:
        end = end + len(end_marker)
        # Also include trailing blank lines until next meaningful code
        while end < len(content) and content[end:end+1] in ('\n', '\r', ' '):
            end += 1
        if start >= 0:
            removed = content[start:end]
            content = content[:start] + content[end:]
            print(f'G3 filter block removed. Removed {len(removed)} chars, file now {len(content)} chars')
        else:
            print('G3 comment not found, but g3_pass found. Trying alternative...')
    else:
        print(f'Could not find end marker')
else:
    # Try finding the G3 comment directly
    idx = content.find('G3')
    print(f'G3 text found at {idx}: {content[idx:idx+50]!r}')

# Remove G3 print line
g3_print = '    print(f"  G3 filter: 3w>=0% AND 1w>=-1%")'
if g3_print in content:
    # Remove the print line and the following blank line
    idx = content.find(g3_print)
    end = idx + len(g3_print)
    # Skip the line
    while end < len(content) and content[end:end+1] in ('\n', '\r', ' '):
        end += 1
    content = content[:idx] + content[end:]
    print(f'G3 print line removed')

with open('weekly_scan_v4.py', 'w', encoding='utf-8', newline='') as f:
    f.write(content)
print('Done')
