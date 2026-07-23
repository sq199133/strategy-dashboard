# -*- coding: utf-8 -*-
import urllib.request, re

codes = "sh510500,sz159915,sh512800"
url = "http://hq.sinajs.cn/list=" + codes
headers = {"User-Agent": "Mozilla/5.0", "Referer": "http://finance.sina.com.cn"}
req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req, timeout=20)
raw_text = resp.read().decode("gb18030", errors="replace")

# Show raw bytes around first match
m = re.search(r'hq_str_(sh|sz)(\w+)=', raw_text)
pos = m.end()
print(f"Match: '{m.group(0)}', pos={pos}")
print(f"Chars around pos: {repr(raw_text[pos-5:pos+30])}")
print(f"Bytes around pos: {raw_text[pos-5:pos+30].encode('gb18030')!r}")

# Find the next double quote
try:
    q_pos = raw_text.index('"', pos)
    print(f"Next quote at: {q_pos}, char='{raw_text[q_pos]}'")
    print(f"Chars between pos and q_pos: {repr(raw_text[pos:q_pos])}")
    print(f"Chars after q_pos: {repr(raw_text[q_pos:q_pos+50])}")
except Exception as e:
    print(f"Error: {e}")
