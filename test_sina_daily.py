import requests, base64, time

# Test Sina daily data
codes = ['sz159107', 'sh512880', 'sh513400']
for code in codes:
    url = 'https://finance.sina.com.cn/realstock/company/%s/hisdata/klc_kl.js' % code
    try:
        r = requests.get(url, timeout=10)
        text = r.text
        if '="' in text:
            data_part = text.split('="')[1].rstrip('"')
            print('%s: %d chars' % (code, len(data_part)))
            try:
                decoded = base64.b64decode(data_part)
                print('  decoded (first 200): %s' % decoded[:200])
            except Exception as e:
                print('  decode error: %s' % e)
        else:
            print('%s: no data pattern found' % code)
    except Exception as e:
        print('%s: error %s' % (code, e))
    time.sleep(0.3)
