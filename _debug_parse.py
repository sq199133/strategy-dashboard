# -*- coding: utf-8 -*-
import urllib.request, re

codes = "sh510500,sz159915,sh512800"
url = "http://hq.sinajs.cn/list=" + codes
headers = {"User-Agent": "Mozilla/5.0", "Referer": "http://finance.sina.com.cn"}
req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req, timeout=20)
raw_bytes = resp.read()
charset = resp.headers.get_content_charset() or "GB18030"
raw_text = raw_bytes.decode(charset, errors="replace")

print("charset detected:", charset)
print("text length:", len(raw_text))
print("first 300 chars:")
print(raw_text[:300])
print("\n--- regex test ---")
matches = list(re.finditer(r'hq_str_(sh|sz)(\w+)=', raw_text))
print(f"regex found {len(matches)} matches")
if matches:
    m = matches[0]
    print(f"first match: prefix={m.group(1)} code={m.group(2)} pos={m.start()}-{m.end()}")
    # Try finding the end quote
    pos = m.end()
    try:
        end_q = raw_text.index('"', pos)
        snippet = raw_text[pos+1:end_q]
        print(f"fields string (first 200): {repr(snippet[:200])}")
        fields = [f.strip() for f in snippet.split(",")]
        print(f"field count: {len(fields)}")
        print(f"first 10 fields: {fields[:10]}")
        print(f"last 5 fields: {fields[-5:]}")
    except Exception as e:
        print(f"Error finding end quote: {e}")
