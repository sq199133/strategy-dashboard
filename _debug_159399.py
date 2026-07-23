# -*- coding: utf-8 -*-
import urllib.request, re

POOL_FILE = r"D:\QClaw_Trading\data\etf_pool_V1_full.json"
UA = {"User-Agent": "Mozilla/5.0", "Referer": "http://finance.sina.com.cn"}

import json
with open(POOL_FILE, encoding="utf-8") as f:
    obj = json.load(f)
pool_codes = [item["code"] for item in obj["data"]]
for fc in ["512890", "515910", "512750", "159399"]:
    if fc not in pool_codes: pool_codes.append(fc)

parts = [f"sz{c}" if c.startswith("159") else f"sh{c}" for c in pool_codes]
url = "http://hq.sinajs.cn/list=" + ",".join(parts)
req = urllib.request.Request(url, headers=UA)
resp = urllib.request.urlopen(req, timeout=30)
raw_text = resp.read().decode("gb18030", errors="replace")

# Find 159399 in raw text
idx = raw_text.find("159399")
if idx >= 0:
    print(f"Found 159399 at index {idx}")
    print("Context (200 chars):")
    print(repr(raw_text[idx-30:idx+200]))
else:
    print("159399 NOT found at all")

# Also check all 159xxx codes that start with 159
m159 = re.findall(r'hq_str_sz(159\d+)="([^"]*)"', raw_text)
print(f"\n159xxx found in regex: {len(m159)} codes")
m159_codes = [x[0] for x in m159]
print("First 10:", m159_codes[:10])
if "159399" in m159_codes:
    val = [x[1] for x in m159 if x[0]=="159399"][0]
    print(f"159399 value length={len(val)}: {repr(val[:100])}")
else:
    print("159399 not matched by hq_str_sz159xxx pattern")

# Try finding it with broader pattern
m2 = re.search(r'159399[^\n]{0,200}', raw_text)
if m2:
    print(f"\nBroad pattern: {repr(m2.group())}")
