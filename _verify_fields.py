# -*- coding: utf-8 -*-
import urllib.request, re

codes = "sh510500,sz159915,sh512800"
url = "http://hq.sinajs.cn/list=" + codes
headers = {"User-Agent": "Mozilla/5.0", "Referer": "http://finance.sina.com.cn"}
req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req, timeout=20)
raw_text = resp.read().decode("gb18030", errors="replace")

# Use [^"]+ non-greedy
for m in re.finditer(r'hq_str_(sh|sz)(\w+)="([^"]+)"', raw_text):
    code = m.group(2)
    fields = [f.strip() for f in m.group(3).split(",")]
    print(f"\n{code}: {len(fields)} fields")
    print(f"  [0] name    = {fields[0]}")
    print(f"  [1] open    = {fields[1]}")
    print(f"  [2] prev    = {fields[2]}")
    print(f"  [3] high    = {fields[3]}")
    print(f"  [4] low     = {fields[4]}")
    print(f"  [5] close   = {fields[5]}")
    print(f"  [7] vol     = {fields[7]}")
    print(f"  [8] amount  = {fields[8]}")
    print(f"  [-3] date   = {fields[-3]}")
    print(f"  [-2] time   = {fields[-2]}")
