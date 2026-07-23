# -*- coding: utf-8 -*-
import json, re, urllib.request

HISTORY = r"D:\QClaw_Trading\data\history"
POOL_FILE = r"D:\QClaw_Trading\data\etf_pool_V1_full.json"
UA = {"User-Agent": "Mozilla/5.0", "Referer": "http://finance.sina.com.cn"}

with open(POOL_FILE, encoding="utf-8") as f:
    obj = json.load(f)
pool_codes = [item["code"] for item in obj["data"]]
for fc in ["512890", "515910", "512750", "159399"]:
    if fc not in pool_codes:
        pool_codes.append(fc)

# Build Sina URL
parts = []
for c in pool_codes:
    if c[0] == "5" or re.match(r"^1[15]\d{4}$", c):
        parts.append(f"sh{c}")
    else:
        parts.append(f"sz{c}")
url = "http://hq.sinajs.cn/list=" + ",".join(parts)
req = urllib.request.Request(url, headers=UA)
resp = urllib.request.urlopen(req, timeout=30)
raw_text = resp.read().decode("gb18030", errors="replace")

found = set()
for m in re.finditer(r'hq_str_(?:sh|sz)(\w+)="([^"]+)"', raw_text):
    found.add(m.group(1))

missing = [c for c in pool_codes if c not in found]
print(f"Pool: {len(pool_codes)}, Found: {len(found)}, Missing: {len(missing)}")
print("Missing:", missing)

# Check if 159399 is in the raw text
if "159399" in raw_text:
    print("159399 IS in raw text (but not parsed - check why)")
else:
    print("159399 NOT in raw text at all")
