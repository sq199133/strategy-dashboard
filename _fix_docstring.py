#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'D:\Qclaw_Trading\weekly_scan_v4.py'
with open(path, encoding='utf-8') as f:
    lines = f.readlines()

new_doc = '"""v4.8 weekly momentum scan  |  MA21 hard filter  dev=30%  no c_bonus  skip vr>1.5"""\n'
# docstring is line index 3 (0-based)
lines[3] = new_doc

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('docstring fixed ->', new_doc.strip())
print('DEFAULT_MAX_DEV check:', sum(1 for l in lines if 'DEFAULT_MAX_DEV = 30' in l), 'occurrences of =30')
