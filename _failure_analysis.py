# -*- coding: utf-8 -*-
"""失败案例深度分析"""
import json, os, glob
import numpy as np
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

WORK = r'D:\QClaw_Trading'
HIST_DIR = os.path.join(WORK, 'data', 'history_long_v2')

history = {}
for fpath in glob.glob(os.path.join(HIST_DIR, '*.json')):
    code = os.path.basename(fpath)[:-5]
    try:
        with open(fpath, encoding='utf-8') as f:
            history[code] = json.load(f)
    except:
        pass

def _fetch(code):
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

def calc_ema(data, period):
    if len(data) < period:
        return None
    k = 2.0 / (period + 1)
    ema_val = float(data[0])
    for v in data[1:]:
        ema_val = float(v) * k + ema_val * (1 - k)
    return ema_val

def _fmt(v, decimals=3):
    if v is None: return 'N/A'
    return str(round(float(v), decimals))

def full_analysis(code, price_now):
    recs = history.get(code, {}).get('records', [])
    if len(recs) < 15:
        return None
    closes = [float(x['close']) for x in recs]
    vols   = [float(x.get('vol', 0)) for x in recs]
    n = len(closes)

    closes_arr = np.array(closes)
    ma5  = float(np.mean(closes_arr[-5:]))  if n >= 5 else None
    ma10 = float(np.mean(closes_arr[-10:])) if n >= 10 else None
    ma21 = float(np.mean(closes_arr[-21:])) if n >= 21 else None
    ma60 = float(np.mean(closes_arr[-60:])) if n >= 60 else None

    mom1 = (closes[-1] / closes[-2] - 1)  if n >= 2 else 0
    mom2 = (closes[-1] / closes[-3] - 1)  if n >= 3 else 0
    mom3 = (closes[-1] / closes[-4] - 1)  if n >= 4 else 0
    mom5 = (closes[-1] / closes[-6] - 1)  if n >= 6 else 0
    mom8 = (closes[-1] / closes[-9] - 1)  if n >= 9 else 0

    def trend_slope(data, lookback):
        if len(data) < lookback:
            return None
        arr = data[-lookback:]
        x = np.arange(len(arr))
        try:
            return float(np.polyfit(x, arr, 1)[0])
        except:
            return None

    slope5  = trend_slope(closes, 5)
    slope10 = trend_slope(closes, 10)
    slope21 = trend_slope(closes, 21)

    atr14 = np.std(closes[-14:]) if n >= 14 else 0
    atr21_s = np.std(closes[-21:]) if n >= 21 else 0
    vola_ratio = atr14 / atr21_s if atr21_s > 0 else 1

    vol_avg5 = np.mean(vols[-5:]) if n >= 5 else 0
    vr = vols[-1] / vol_avg5 if vol_avg5 > 0 else 0

    deltas = np.diff(closes[-15:]) if n >= 15 else np.array([0.0])
    gain = float(np.mean(deltas[deltas > 0])) if len(deltas[deltas > 0]) > 0 else 0.0
    loss = abs(float(np.mean(deltas[deltas < 0]))) if len(deltas[deltas < 0]) > 0 else 0.0
    rs = gain / loss if loss > 1e-10 else 100.0
    rsi14 = 100.0 - (100.0 / (1.0 + rs)) if rs > 0 else 50.0

    e12 = calc_ema(closes, 12)
    e26 = calc_ema(closes, 26)
    macd_bull = bool(e12 is not None and e26 is not None and e12 > e26)

    dev = (price_now / ma21 - 1) * 100.0 if ma21 else 999.0

    return {
        'code': code,
        'price': price_now,
        'ma5': ma5, 'ma10': ma10, 'ma21': ma21, 'ma60': ma60,
        'mom1': mom1, 'mom2': mom2, 'mom3': mom3, 'mom5': mom5, 'mom8': mom8,
        'slope5': slope5, 'slope10': slope10, 'slope21': slope21,
        'dev': dev, 'vr': vr, 'vola_ratio': vola_ratio,
        'rsi14': rsi14,
        'macd_bull': macd_bull,
        'ma5_ok': bool(ma5 and closes[-1] > ma5 and closes[-2] <= ma5),
        'ma21_ok': bool(ma21 and price_now > ma21),
    }

# ── 主程序 ──────────────────────────────────────────────
codes_to_check = [
    '159837', '560080', '513190', '159928', '512010',
    '588000', '159949', '510300', '512880', '518880',
    '159268', '159636', '513070', '159850',
]

price_map = {}
with ThreadPoolExecutor(max_workers=15) as ex:
    futures = {ex.submit(_fetch, c): c for c in codes_to_check}
    for fut in as_completed(futures):
        code, price = fut.result()
        if price:
            price_map[code] = price

def show_analysis(code, label):
    price = price_map.get(code)
    if not price:
        print(f"{label}: 价格获取失败\n")
        return
    a = full_analysis(code, price)
    if not a:
        print(f"{label}: 历史数据不足\n")
        return
    print(f"\n{'='*55}")
    print(f"{label} ({code})  当前价: {a['price']}")
    print(f"{'='*55}")
    print(f"  --- 均线 ---")
    print(f"  MA5={_fmt(a['ma5'])}  MA10={_fmt(a['ma10'])}  MA21={_fmt(a['ma21'])}  MA60={_fmt(a['ma60'])}")
    print(f"  --- 趋势斜率 ---")
    s5 = _fmt(a['slope5']) if a['slope5'] is not None else 'N/A'
    s10 = _fmt(a['slope10']) if a['slope10'] is not None else 'N/A'
    s21 = _fmt(a['slope21']) if a['slope21'] is not None else 'N/A'
    arrow5 = chr(9650) if a['slope5'] and a['slope5']>0 else chr(9660) if a['slope5'] else '?'
    arrow10 = chr(9650) if a['slope10'] and a['slope10']>0 else chr(9660) if a['slope10'] else '?'
    print(f"  5周斜率: {s5} {arrow5}   10周斜率: {s10} {arrow10}   21周斜率: {s21}")
    print(f"  --- 动量 ---")
    print(f"  1周={a['mom1']*100:+.1f}%  2周={a['mom2']*100:+.1f}%  3周={a['mom3']*100:+.1f}%")
    print(f"  5周={a['mom5']*100:+.1f}%  8周={a['mom8']*100:+.1f}%")
    print(f"  --- 质量指标 ---")
    rsi_label = "高位风险" if a['rsi14']>65 else "超卖" if a['rsi14']<40 else "中性"
    print(f"  RSI-14: {a['rsi14']:.0f}  [{rsi_label}]")
    macd_label = "多头" if a['macd_bull'] else "空头"
    print(f"  MACD: {macd_label}")
    print(f"  波动率比: {a['vola_ratio']:.2f}  量比VR: {a['vr']:.1f}x")
    print(f"  --- v4.8过滤 ---")
    ma21_ok_str = str(a['ma21_ok'])
    print(f"  MA21_ok={ma21_ok_str}  偏离度={a['dev']:+.1f}%")

# 失败案例
show_analysis('159837', '失败案例1: 生物科技ETF')
show_analysis('560080', '失败案例2: 中药ETF')

# 大盘背景
print(f"\n\n{'='*55}")
print("大盘背景（买入时的市场环境）")
print(f"{'='*55}")
show_analysis('510300', '沪深300ETF')
show_analysis('159949', '创业板50ETF')
show_analysis('588000', '科创50ETF')

# 当前候选
print(f"\n\n{'='*55}")
print("当前候选标的（07-24 TOP1-5）")
print(f"{'='*55}")
show_analysis('513190', 'TOP1: 港股金融ETF')
show_analysis('513310', 'TOP2: 中韩半导体ETF')
show_analysis('513880', 'TOP3: 港股创新药ETF')
show_analysis('513290', 'TOP4: 纳指生物科技ETF')
show_analysis('159502', 'TOP5: 标普生物科技ETF')

# 消费/港股消费对比
print(f"\n\n{'='*55}")
print("消费类对比（潜在防御型标的）")
print(f"{'='*55}")
show_analysis('159928', '消费ETF')
show_analysis('159268', '港股通消费ETF')
show_analysis('518880', '黄金ETF')

print(f"\n\n{'='*55}")
print("失败模式总结")
print(f"{'='*55}")
