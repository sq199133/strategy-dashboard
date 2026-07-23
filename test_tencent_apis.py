"""腾讯多接口测试"""
import requests

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://gu.qq.com/',
}

# 1. ETF批量行情
url1 = 'https://qt.gtimg.cn/q=sh512690,sz159928,sh518880,sh510500'
r1 = requests.get(url1, headers=headers, timeout=10)
print("=== ETF批量行情 ===")
for line in r1.text.strip().split('\n'):
    p = line.split('~')
    if len(p) > 36:
        name = p[1] if len(p) > 1 else '?'
        price = p[3] if p[3] else '?'
        chg_pct = p[32] if p[32] else '?'
        open_p = p[5] if p[5] else '?'
        high = p[33] if p[33] else '?'
        low = p[34] if p[34] else '?'
        vol = p[36] if p[36] else '?'
        print(f"  {p[0][-6:]} {name} 现价:{price} 涨跌:{chg_pct}% 今开:{open_p} 高:{high} 低:{low} 量:{vol}")

# 2. 指数行情
url2 = 'https://qt.gtimg.cn/q=s_sh000001,s_sz399001,s_sz399006,s_sz399005'
r2 = requests.get(url2, headers=headers, timeout=10)
print("\n=== 指数行情 ===")
for line in r2.text.strip().split('\n'):
    p = line.split('~')
    if len(p) > 10:
        name = p[1] if p[1] else '?'
        price = p[3] if p[3] else '?'
        chg = p[4] if p[4] else '?'
        chg_pct = p[32] if len(p) > 32 and p[32] else '?'
        print(f"  {name} {price} {chg} ({chg_pct}%)")

# 3. 港股行情
url3 = 'https://qt.gtimg.cn/q=hk00700,hkHSCEI,hk03690'
r3 = requests.get(url3, headers=headers, timeout=10)
print("\n=== 港股/指数行情 ===")
for line in r3.text.strip().split('\n'):
    p = line.split('~')
    if len(p) > 10:
        name = p[1] if p[1] else '?'
        price = p[3] if p[3] else '?'
        chg = p[4] if p[4] else '?'
        chg_pct = p[32] if len(p) > 32 and p[32] else '?'
        print(f"  {p[0]} {name} {price} {chg} ({chg_pct}%)")

# 4. 腾讯ETF详情 (另一接口)
url4 = 'https://web.ifzq.gtimg.cn/appstock/app/etfqfq/get?param=sh512690,qfqday,,,5,qfq'
r4 = requests.get(url4, headers={'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/'}, timeout=10)
print("\n=== 腾讯ETF K线 ===")
print("Status:", r4.status_code, "Body[:300]:", r4.text[:300])

# 5. AKShare 状态
import subprocess
result = subprocess.run(['pip', 'show', 'akshare'], capture_output=True, text=True, timeout=5)
print("\n=== AKShare ===")
print("已安装" if result.returncode == 0 else "未安装")
if result.returncode == 0:
    for line in result.stdout.split('\n')[:2]:
        print(" ", line)
