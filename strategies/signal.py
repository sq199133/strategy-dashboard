"""
策略信号生成脚本 — 生产版
=============================
动15MA175_ETF28_T3 +黄金ETF

每周一收盘后运行:
  python signal.py

输出:
  1. 当前最佳板块(动量最强+MA175过滤)
  2. 应买入的3只ETF(28天动量排序, 等权)
  3. 操作建议(换仓/持有/空仓)

数据文件:
  D:\QClaw_Trading\data\history\*.json
  D:\QClaw_Trading\data\cat_assignment_full.json
"""
import json, os, sys, numpy as np
from collections import defaultdict
from datetime import datetime as dt

sys.stdout.reconfigure(encoding='utf-8')

# ============================================================
#  配置
# ============================================================
DATA_DIR = r'D:\QClaw_Trading\data\history'
CAT_FILE = r'D:\QClaw_Trading\data\cat_assignment_full.json'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'

MOM_DAYS = 15      # 板块动量
MA_DAYS = 175       # MA过滤
ETF_MOM = 28        # ETF动量
TOP_K = 3           # 选ETF数

EXTRA_ETFS = {
    '商品/周期/资源': ['518880'],
}

# ============================================================
#  数据加载
# ============================================================
def load_names():
    if not os.path.exists(POOL_FILE):
        return {}
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        pool = json.load(f)
    names = {}
    for e in pool.get('data', []):
        names[str(e['code'])] = e.get('name', '').replace('\xa0', ' ').strip()
    names['518880'] = '黄金ETF华夏'
    return names

def load_cat_map():
    with open(CAT_FILE, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    cm = {}
    for kw, entries in raw.get('assignments', {}).items():
        for entry in entries:
            cm[entry[0]] = entry[1]
    return cm

def build_sectors(cat_map):
    sectors = defaultdict(list)
    for code, cat in cat_map.items():
        if cat != '海外/跨境':
            sectors[cat].append(code)
    for cat, codes in EXTRA_ETFS.items():
        for c in codes:
            if c not in sectors[cat]:
                sectors[cat].append(c)
    return dict(sectors)

def load_records(code):
    for prefix in ['', 'sz']:
        fn = os.path.join(DATA_DIR, prefix + code + '.json')
        if os.path.exists(fn):
            with open(fn, 'r', encoding='utf-8') as f:
                r = json.load(f).get('records', [])
            if r:
                return r
    return []

def load_prices(cat_map, sectors):
    all_codes = set()
    for codes in sectors.values():
        all_codes.update(codes)
    prices = {}
    for code in all_codes:
        recs = load_records(code)
        if recs:
            prices[code] = {r['date']: r.get('close', 0.0) for r in recs}
    return prices

# ============================================================
#  信号计算
# ============================================================
def calc_signal():
    print('加载数据...')
    names = load_names()
    cat_map = load_cat_map()
    sectors = build_sectors(cat_map)
    prices = load_prices(cat_map, sectors)
    
    # 所有交易日并集
    all_dates = sorted(set(d for pm in prices.values() for d in pm))
    if not all_dates:
        print('错误: 无有效数据')
        return
    
    today = all_dates[-1]  # 最新一个交易日
    print('最新交易日:', today)
    
    # 需要足够历史
    need_days = max(MOM_DAYS, MA_DAYS, ETF_MOM)
    if len(all_dates) < need_days:
        print('数据不足, 最少需要%d天' % need_days)
        return
    
    # 构建板块指数
    print('构建板块指数...')
    indices = {}
    for cat, codes in sectors.items():
        arr = np.full(len(all_dates), np.nan)
        for i, dt in enumerate(all_dates):
            vals = [prices[c].get(dt, np.nan) for c in codes if c in prices]
            valid = [v for v in vals if not np.isnan(v)]
            if len(valid) >= max(1, len(codes) // 3):
                arr[i] = np.mean(valid)
        indices[cat] = arr
    
    i = len(all_dates) - 1  # 最新索引
    
    # 找最佳板块
    best_cat = None
    best_mom = -999.0
    
    print('\n正在扫描板块...')
    print('%-16s %8s %8s  %s' % ('板块', '15d动量', '>MA175', '状态'))
    print('-' * 55)
    
    for cat, idx in indices.items():
        curr = idx[i]
        if np.isnan(curr):
            continue
        
        # 15天动量
        past = idx[i - MOM_DAYS]
        if np.isnan(past) or past <= 0:
            continue
        momentum = curr / past - 1
        
        # MA175过滤
        ma_vals = idx[i-MA_DAYS:i]
        ma_vals = ma_vals[~np.isnan(ma_vals)]
        if len(ma_vals) < MA_DAYS // 3:
            ma_pass = False
            ma_val = np.nan
        else:
            ma_val = np.mean(ma_vals)
            ma_pass = curr > ma_val
        
        live = '📈' if ma_pass else '📉(排除)'
        print('%-16s %+7.2f%% %7s  %s' % (cat, momentum*100,
              '✓' if ma_pass else '✗', live))
        
        if ma_pass and momentum > best_mom:
            best_mom = momentum
            best_cat = cat
    
    print()
    
    if not best_cat:
        print('❌ 无板块通过MA%d过滤 → 建议空仓(清仓持有现金)' % MA_DAYS)
        return
    
    # 板块内选ETF
    candidates = sectors.get(best_cat, [])
    ranked = []
    for c in candidates:
        if c not in prices:
            continue
        cp = prices[c].get(today, np.nan)
        if np.isnan(cp):
            continue
        # 28天动量
        pp = prices[c].get(all_dates[i - ETF_MOM], np.nan)
        if np.isnan(pp) or pp <= 0:
            continue
        etf_mom = cp / pp - 1
        ranked.append((etf_mom, c, cp))
    
    ranked.sort(reverse=True)
    
    print('✅ 选中的板块:', best_cat)
    print('   板块动量:', '%+.2f%%' % (best_mom * 100))
    print('   MA%d过滤: 通过' % MA_DAYS)
    print()
    
    print('板块内ETF 28天动量排序:')
    print('%-8s %-36s %8s' % ('代码', '名称', '动量'))
    print('-' * 58)
    for etf_mom, code, _ in ranked[:8]:
        nm = names.get(code, code)
        sel = '← 买入' if len([x for x in ranked[:TOP_K] if x[1]==code]) > 0 else ''
        print('%-8s %-36s %+7.2f%% %s' % (code, nm[:34], etf_mom*100, sel))
    
    print()
    selected = [c for _, c, _ in ranked[:min(TOP_K, len(ranked))]]
    print('🎯 操作建议:')
    for c in selected:
        nm = names.get(c, c)
        print('   买入 %s (%s)' % (c, nm))
    print('   等权分配, 周二开盘执行')
    print()
    
    # 最新收盘价参考
    print('  参考价格(最新收盘):')
    for c in selected:
        cp = prices[c].get(today, 'N/A')
        if cp != 'N/A':
            print('    %s: %.3f' % (c, cp))
    
    print()
    print('' + '='*55)
    print('  持仓周期: 持有至下周一信号')
    print('  注意事项: 若下周一信号板块不变→继续持有')
    print('            若下周一信号板块变化→按新信号调仓')
    print('            若下周一无板块过MA175过滤→清仓空仓')

if __name__ == '__main__':
    calc_signal()
