"""Debug Tencent index API"""
import requests, re

url = 'https://qt.gtimg.cn/q=s_sh000001,s_sz399006,s_sh000300'
r = requests.get(url, timeout=20)
print("Raw response:")
for line in r.text.strip().split('\n'):
    if '~' in line:
        m = re.search(r'v_(\w+)="(.+)"', line)
        if m:
            qt = m.group(1)
            fields = m.group(2).split('~')
            print(f'\n{qt}: {len(fields)} fields')
            for i, f in enumerate(fields[:45]):
                if f and f != '-': print(f'  [{i:2d}] {f}')
