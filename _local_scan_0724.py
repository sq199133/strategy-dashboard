# -*- coding: utf-8 -*-
"""0724周线扫描 - 并发价格版"""
import json, os, glob
import numpy as np
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

WORK = r'D:\QClaw_Trading'
HIST_DIR = os.path.join(WORK, 'data', 'history_long_v2')
POOL_FILE = os.path.join(WORK, 'data', 'etf_pool_V1_full.json')

# 加载ETF池
with open(POOL_FILE, encoding='utf-8') as f:
    _raw = json.load(f)
etf_list = _raw.get('data', _raw if isinstance(_raw, list) else [])
etf_pool = {item['code']: item for item in etf_list}

# 加载历史
history = {}
for fpath in glob.glob(os.path.join(HIST_DIR, '*.json')):
    code = os.path.basename(fpath)[:-5]
    try:
        with open(fpath, encoding='utf-8') as f:
            history[code] = json.load(f)
    except:
        pass
print(f"历史加载: {len(history)}")

# 并发取价
def _fetch_one(code):
    c = ('sh' if code.startswith(('51','58','50','56','52')) else 'sz') + code
    try:
        req = urllib.request.Request(
            'https://qt.gtimg.cn/q=' + c,
            headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as r:
            parts = r.read().decode('gbk', errors='replace').split('~')
        if len(parts) > 4:
            return code, float(parts[3])
    except:
        pass
    return code, None

all_codes = list(etf_pool.keys())
price_map = {}
with ThreadPoolExecutor(max_workers=20) as ex:
    futures = {ex.submit(_fetch_one, c): c for c in all_codes}
    for fut in as_completed(futures):
        code, price = fut.result()
        if price is not None:
            price_map[code] = price

print(f"实时价格获取: {len(price_map)}/{len(all_codes)}")

# 配置
SC_W1, SC_W3, SC_W8 = 0.5, 0.5, 0.0
MAX_DEV = 30.0
VR_THRESH = 1.5
ATR_RATIO = 0.85

results = []
for code in etf_pool:
    hdata = history.get(code)
    if not hdata:
        continue
    records = hdata.get('records', [])
    if len(records) < 8:
        continue
    try:
        closes = [float(x['close']) for x in records]
        vols = [float(x.get('vol', 0)) for x in records]
    except:
        continue

    price = price_map.get(code)
    if price is None:
        continue

    n = len(closes)
    ma21 = np.mean(closes[-21:]) if n >= 21 else None
    ma5  = np.mean(closes[-5:])  if n >= 5 else None
    ma5p = closes[-2]             if n >= 2 else None

    ma5_ok  = bool(ma5 and closes[-1] > ma5 and ma5 > ma5p)
    ma21_ok = bool(ma21 and price > ma21)

    mom1 = (closes[-1] / closes[-2] - 1) if n >= 2 else 0
    mom3 = (closes[-1] / closes[-4] - 1) if n >= 4 else 0
    mom8 = (closes[-1] / closes[-9] - 1) if n >= 9 else 0

    dev = (price / ma21 - 1) * 100 if ma21 else 999
    score = SC_W1 * mom1 * 100 + SC_W3 * mom3 * 100 + SC_W8 * mom8 * 100

    atr14 = np.std(closes[-14:]) if n >= 14 else 0
    atr21_s = np.std(closes[-21:]) if n >= 21 else 0
    atr_skip = bool(ATR_RATIO and atr21_s > 0 and (atr14 / atr21_s) < ATR_RATIO)

    vol_avg = np.mean(vols[-5:]) if n >= 5 else 0
    vr = vols[-1] / vol_avg if vol_avg > 0 else 0

    results.append({
        'code': code, 'price': price,
        'ma5': ma5, 'ma21': ma21,
        'mom1': mom1, 'mom3': mom3, 'mom8': mom8,
        'dev': dev, 'score': score,
        'ma5_ok': ma5_ok, 'ma21_ok': ma21_ok,
        'atr_skip': atr_skip, 'vr': vr,
    })

print(f"有效ETF: {len(results)}")

candidates = [
    r for r in results
    if r['ma21_ok'] and r['dev'] <= MAX_DEV
    and r['vr'] >= VR_THRESH and not r['atr_skip']
]
candidates.sort(key=lambda x: x['score'], reverse=True)

print(f"候选: {len(candidates)}")
print()
print(f"{'#':>3} {'code':>10} {'price':>7} {'dev':>7} {'mom1':>7} {'mom3':>7} {'VR':>5} {'score':>8}")
print("-" * 60)
for i, r in enumerate(candidates[:10], 1):
    print(f"{i:>3} {r['code']:>10} {r['price']:>7.3f} {r['dev']:>+6.1f}% "
          f"{r['mom1']*100:>+6.1f}% {r['mom3']*100:>+6.1f}% {r['vr']:>5.1f} {r['score']:>+8.3f}")

if candidates:
    top = candidates[0]
    print()
    print(f"TOP1: {top['code']}, price={top['price']}, ma21={top['ma21']:.4f}")
    print(f"  dev={top['dev']:+.1f}%, mom1={top['mom1']*100:+.1f}%, mom3={top['mom3']*100:+.1f}%")
    print(f"  VR={top['vr']:.1f}, score={top['score']:+.4f}")
    print(f"  hard_stop={top['price']*0.92:.3f}, high_stop={top['price']*0.90:.3f}")
else:
    print("无候选!")
    no_ma21 = [r for r in results if not r['ma21_ok']]
    no_ma21.sort(key=lambda x: x['score'], reverse=True)
    print(f"MA21失败: {len(no_ma21)}, 最高分: {no_ma21[0] if no_ma21 else 'N/A'}")
