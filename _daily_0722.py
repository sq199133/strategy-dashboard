# -*- coding: utf-8 -*-
"""获取0722行情数据 - 腾讯API"""
import urllib.request, json

codes = {
    "sh560080": "中药ETF",
    "sz159837": "生物科技ETF", 
    "sh510300": "沪深300ETF",
    "sz159949": "创业板50ETF",
    "sh518880": "黄金ETF",
}

for code, name in codes.items():
    try:
        url = f"https://qt.gtimg.cn/q={code}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode('gbk', errors='replace')
        # 解析腾讯数据格式
        # 格式: v_sz159837="1~名称~代码~当前价~昨收~开盘~成交量~外盘~内盘~..."
        parts = raw.split('~')
        if len(parts) > 30:
            name_full = parts[1]
            price = float(parts[3])
            prev_close = float(parts[4])
            open_price = float(parts[5])
            high = float(parts[33]) if len(parts) > 33 else 0
            low = float(parts[34]) if len(parts) > 34 else 0
            change_pct = (price - prev_close) / prev_close * 100
            print(f"{name} {code}: 现价={price:.3f} 昨收={prev_close:.3f} 涨跌={change_pct:+.2f}% 开={open_price:.3f} 高={high:.3f} 低={low:.3f}")
        else:
            print(f"{name}: 解析失败, parts={len(parts)}")
    except Exception as e:
        print(f"{name} {code} error: {e}")
