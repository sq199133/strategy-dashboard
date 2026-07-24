# -*- coding: utf-8 -*-
"""0724周五收盘 - 策略状态确认"""
import urllib.request

def get_price(code):
    try:
        url = f'https://qt.gtimg.cn/q={code}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode('gbk', errors='replace')
        parts = raw.split('~')
        return float(parts[3]), float(parts[4])
    except:
        return None, None

# 560080中药ETF 0724收盘
price, prev = get_price('sh560080')
print(f"560080 中药ETF 0724收盘: {price}  昨收: {prev}")

# MA21来自akshare周线（前复权，近21周）
# 已确认: MA21 = 1.0340, 当前周收盘 = 0.9640
ma21 = 1.0340
print(f"\n=== 560080 策略状态 ===")
print(f"当前价: {price:.3f}")
print(f"MA21:   {ma21:.4f}")
print(f"price > MA21: {price > ma21}")
print(f"偏离度: {(price/ma21-1)*100:+.1f}%")

# 止损位
cost = 0.988
peak = 1.005   # 买入后高点
hard_stop = cost * 0.92   # -8%
high_stop = peak * 0.90   # 高点-10%
print(f"\n止损位: 硬止损={hard_stop:.3f}  高点止损={high_stop:.3f}")
print(f"距硬止损: {(price/hard_stop-1)*100:+.1f}%")
print(f"距高点止损: {(price/high_stop-1)*100:+.1f}%")

# 综合判断
if price < ma21:
    print(f"\n⚠️  策略信号: SELL → 跌破MA21({ma21:.3f})，策略要求轮动卖出")
elif price < hard_stop:
    print(f"\n⚠️  策略信号: STOP-LOSS → 触发硬止损")
elif price < high_stop:
    print(f"\n⚠️  策略信号: 高点止损警告")
else:
    print(f"\n✅  策略信号: HOLD")
