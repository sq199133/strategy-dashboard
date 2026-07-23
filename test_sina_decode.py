import requests, time

# Look at raw Sina data structure
codes = ['sz159107', 'sh512880']
for code in codes:
    url = 'https://finance.sina.com.cn/realstock/company/%s/hisdata/klc_kl.js' % code
    try:
        r = requests.get(url, timeout=10)
        text = r.text
        print('=== %s ===' % code)
        print('Raw (first 500): %s' % repr(text[:500]))
        print()
    except Exception as e:
        print('%s: error %s' % (code, e))
    time.sleep(0.3)
