import re

with open(r'D:\QClaw_Trading\weekly_scan_v4.py', encoding='utf-8') as f:
    content = f.read()

# Patch 1: add --no-dedup argument
old1 = "    ap.add_argument('--holdings', type=str, default='')\n    a = ap.parse_args()"
new1 = "    ap.add_argument('--holdings', type=str, default='')\n    ap.add_argument('--no-dedup', action='store_true', default=False)\n    a = ap.parse_args()"
content = content.replace(old1, new1, 1)

# Patch 2: modify target selection
old2 = "    target = dedup[:a.top_n]"
new2 = """    # no-dedup: 直接按adj_score取前top_n，不做赛道去重
    if a.no_dedup:
        target = qual[:a.top_n]  # qual已按adj_score降序排列
        print(f"  [no-dedup mode] 直接取前{a.top_n}名")
    else:
        target = dedup[:a.top_n]"""
content = content.replace(old2, new2, 1)

with open(r'D:\QClaw_Trading\weekly_scan_v4.py', encoding='utf-8', newline='\n') as f:
    f.write(content)

print("Patch applied successfully")
print("Changes made:")
print("1. Added --no-dedup argument")
print("2. Modified target selection to support no-dedup mode")
