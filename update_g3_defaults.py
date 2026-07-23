import os
os.chdir(r'D:\Qclaw_Trading')
with open('backtest_v5_qual_sizer.py', 'r', encoding='utf-8', newline='') as f:
    content = f.read()
# Update default G3 thresholds to disabled
old_defaults = [
    ("ap.add_argument('--mom1w-threshold', type=float, default=-1.0, help='G3 1-week momentum threshold (%)')",
     "ap.add_argument('--mom1w-threshold', type=float, default=-100.0, help='G3 1-week momentum threshold (%)')"),
    ("ap.add_argument('--mom3w-threshold', type=float, default=0.0, help='G3 3-week momentum threshold (%)')",
     "ap.add_argument('--mom3w-threshold', type=float, default=-100.0, help='G3 3-week momentum threshold (%)')"),
]
for old, new in old_defaults:
    if old in content:
        content = content.replace(old, new)
        print(f'Updated: {old.split("default=")[1].split(",")[0]} -> {new.split("default=")[1].split(",")[0]}')
    else:
        print(f'Could not find: {old[:60]}')

with open('backtest_v5_qual_sizer.py', 'w', encoding='utf-8', newline='') as f:
    f.write(content)
print('Done')
