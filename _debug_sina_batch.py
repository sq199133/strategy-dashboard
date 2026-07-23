# -*- coding: utf-8 -*-
import urllib.request, re, sys

codes = "sh510500,sz159915,sh512800"
url = "http://hq.sinajs.cn/list=" + codes
headers = {"User-Agent": "Mozilla/5.0", "Referer": "http://finance.sina.com.cn"}
req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req, timeout=20)
raw_bytes = resp.read()
print("status:", resp.status)
print("content-type:", resp.headers.get("content-type"))
print("raw_bytes len:", len(raw_bytes))
print("first 300 bytes:", repr(raw_bytes[:300]))
print("encoding attempts:")
for enc in ("gbk", "gb2312", "utf-8", "latin-1"):
    try:
        txt = raw_bytes.decode(enc)
        print(f"  {enc}: OK, first 100 = {repr(txt[:100])}")
    except Exception as e:
        print(f"  {enc}: FAIL {e}")
