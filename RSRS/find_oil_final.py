"""定位黄金/原油数据 — 多路尝试"""
import warnings; warnings.filterwarnings('ignore')

# ── 1. 用akshare的global_hist_sina探测可用商品指数 ──
print('=== 全球指数表(Sina) ===')
import akshare as ak
try:
    tb = ak.index_global_name_table()
    print(f'  共{len(tb)}条')
    for _, r in tb.iterrows():
        print(f'  {r.iloc[0]:<20} {r.iloc[1]:<12}', end='')
        try:
            df = ak.index_global_hist_sina(symbol=r.iloc[1])
            print(f' {len(df)}行 {df.iloc[0]["date"]} ~ {df.iloc[-1]["date"]}')
        except:
            print(' ❌')
except Exception as e:
    print(f'  ERR: {e}')

# ── 2. 用request直连新浪黄金数据 ──
print('\n=== 新浪期货/商品行情 ===')
import requests as rq
sym_map = {'au888':'黄金期货','sc888':'原油期货','cu888':'铜期货'}
for sym, name in sym_map.items():
    url = f'https://stock.finance.sina.com.cn/futures/api/jsonp.php/var%20p=sym,name={sym}&f=date,close'
    try:
        resp = rq.get(url, timeout=10)
        txt = resp.text[:200]
        print(f'{name:<10}({sym:<8}): {txt[:150]}')
    except Exception as e:
        print(f'{name:<10}({sym:<8}): ERR {str(e)[:60]}')

# ── 3. 传统新浪黄金/原油 —— ID表 ──
print('\n=== 新浪贵金属/商品ID ===')
# 国内黄金市场
for url_name, name in [
    ('https://hq.sinajs.cn/list=au1806,gc1806,if1806','期货活跃合约'),
    ('https://hq.sinajs.cn/list=hf_GC','纽约金'),
    ('https://hq.sinajs.cn/list=hf_CL','纽约原油'),
    ('https://hq.sinajs.cn/list=hf_XAU','伦敦金现'),
    ('https://hq.sinajs.cn/list=hf_XAG','伦敦银现'),
    ('https://stock.finance.sina.com.cn/stock/api/jsonp.php/var%20sp=sym=XAUUSD&f=close','伦敦金现2'),
]:
    try:
        resp = rq.get(url_name, timeout=10, headers={'Referer':'https://finance.sina.com.cn'})
        print(f'{name:<12}: {resp.text[:120]}')
    except Exception as e:
        print(f'{name:<12}: {str(e)[:60]}')

# ── 4. 改用东方财富的金/银/铜/原油指数 ──
print('\n=== 东方财富指数(备用) ===')
for sym in ['sh000066','sh000015','sh000049','sh000052','sh000117']:
    try:
        df = ak.stock_zh_index_daily(symbol=sym)
        print(f'{sym}: {len(df)}行 {df.iloc[0]["date"]} ~ {df.iloc[-1]["date"]}')
    except:
        pass
