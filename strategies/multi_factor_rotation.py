"""
多因子板块轮动策略
===================
全量194ETF合成11板块指数 → 多因子打分选板块 → 多因子打分选ETF
"""

import json, os, math, sys, statistics
from datetime import datetime

# ──────────────────────────────────────────
# 配置
# ──────────────────────────────────────────
CATEGORIES = [
    '科技/TMT/AI', '商品/周期/资源', '制造/基建/公用',
    '消费', '医药生物', '新能源', '金融', '科创板', '红利策略',
    '宽基/综合', '海外/跨境'
]

MOM_DAYS = 12
REBAL_WEEKDAY = 0
CASH_RATE = 0.02
DATA_DIR = r'D:\QClaw_Trading\data'
ETF_PICK_N = 2

# ── 多因子权重配置 ──
SECTOR_FACTORS = {
    'momentum':      {'weight': 0.35, 'desc': '12日动量'},       # 趋势强度
    'atr_premium':   {'weight': 0.20, 'desc': 'ATR比溢价'},      # 波动健康度
    'price_health':  {'weight': 0.25, 'desc': '价格与MA5偏离'},  # 短期趋势确认
    'internal_mom':  {'weight': 0.20, 'desc': '板块内ETF上涨比例'},# 板块内动量广度
}

ETF_FACTORS = {
    'corr_to_sector': {'weight': 0.35, 'desc': '与板块相关度'},   # 跟板块紧度
    'rel_momentum':   {'weight': 0.30, 'desc': '板块内相对动量'},  # 相对强弱
    'rel_volatility': {'weight': 0.15, 'desc': '相对低波动'},     # 稳定性加分
    'scale':          {'weight': 0.20, 'desc': '规模/存续天数'},  # 代表性和流动性
}

# ──────────────────────────────────────────
# 数据加载（复用）
# ──────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
import atr_momentum_rotation as atr

def load_all_data(data_until=None):
    """加载全部所需数据"""
    cat_px, dates, weekday_of, week_key = atr.build_sector_indices(data_until=data_until)
    cat_atr_ratio = atr.compute_atr_ratios(cat_px)
    
    code_cat = atr.load_pool()
    all_closes = {}; cat_etfs = {}
    for code, cat in code_cat.items():
        data = atr.load_etf_data(code)
        if data and len(data) > 50:
            all_closes[code] = data
            cat_etfs.setdefault(cat, []).append(code)
    
    return cat_px, dates, weekday_of, week_key, cat_atr_ratio, all_closes, cat_etfs


# ──────────────────────────────────────────
# 因子计算：板块级别
# ──────────────────────────────────────────
def calc_momentum(cat_px, cat, today_idx, dates, n=MOM_DAYS):
    px = cat_px.get(cat, {})
    p0 = px.get(dates[today_idx - n])
    p1 = px.get(dates[today_idx - 1])
    return p1/p0 - 1 if p0 and p1 and p0 > 0 else -999

def calc_atr_premium(cat_atr_ratio, cat, today, atr_min=0.85):
    ar = cat_atr_ratio.get(cat, {}).get(today, 0)
    return max(0, ar - atr_min)  # 超过阈值的部分

def calc_price_health(cat_px, cat, today_idx, dates):
    """close / MA5 - 1"""
    px = cat_px.get(cat, {})
    n = 5
    if today_idx < n:
        return 0
    vals = [px.get(dates[today_idx - j]) for j in range(1, n+1)]
    vals = [v for v in vals if v]
    if not vals:
        return 0
    ma5 = sum(vals) / len(vals)
    today_val = px.get(dates[today_idx - 1])
    return today_val/ma5 - 1 if today_val and ma5 > 0 else 0

def calc_internal_momentum(cat_etfs, all_closes, cat, today_idx, dates):
    """板块内有多少ETF的12日动量为正"""
    etfs = cat_etfs.get(cat, [])
    positive = 0; total = 0
    for code in etfs:
        d = all_closes.get(code, {})
        p0 = d.get(dates[today_idx - MOM_DAYS])
        p1 = d.get(dates[today_idx - 1])
        if p0 and p1 and p0 > 0:
            total += 1
            if p1/p0 - 1 > 0:
                positive += 1
    return positive / total if total > 0 else 0


def rank_score(values_dict, key):
    """将因子值转为排名分(0-100)"""
    items = [(k, v) for k, v in values_dict.items() if v is not None]
    if not items:
        return {}
    items.sort(key=lambda x: x[1])  # 升序
    scores = {}
    for rank, (k, v) in enumerate(items):
        scores[k] = rank / (len(items) - 1) * 100 if len(items) > 1 else 50
    return scores


def compute_sector_scores(cat_px, cat_atr_ratio, cat_etfs, all_closes,
                           today_idx, dates):
    """多因子合成板块得分"""
    today = dates[today_idx - 1]
    
    factor_values = {}
    for fn in SECTOR_FACTORS:
        factor_values[fn] = {}
    
    categories = [c for c in cat_px if c in CATEGORIES]
    
    # 计算每个板块的各因子原始值
    for cat in categories:
        factor_values['momentum'][cat] = calc_momentum(cat_px, cat, today_idx, dates)
        factor_values['atr_premium'][cat] = calc_atr_premium(cat_atr_ratio, cat, today)
        factor_values['price_health'][cat] = calc_price_health(cat_px, cat, today_idx, dates)
        factor_values['internal_mom'][cat] = calc_internal_momentum(cat_etfs, all_closes, cat, today_idx, dates)
    
    # 排名化+加权合成
    sector_scores = {}
    for cat in categories:
        sector_scores[cat] = 0
    
    for fn, cfg in SECTOR_FACTORS.items():
        rank_scores = rank_score(factor_values[fn], fn)
        for cat, score in rank_scores.items():
            sector_scores[cat] += score * cfg['weight']
    
    # 降序排列
    return sorted(sector_scores.items(), key=lambda x: -x[1])


# ──────────────────────────────────────────
# 因子计算：ETF级别
# ──────────────────────────────────────────
def compute_etf_scores(sector, etf_codes, cat_px, all_closes, today_idx, dates, cat_etfs):
    """在选中板块内，多因子选ETF"""
    px = cat_px.get(sector, {})
    scores_list = []
    
    for code in etf_codes:
        d = all_closes.get(code, {})
        
        # 因子1: 与板块相关度
        sr, er = [], []
        for j in range(today_idx - 12, today_idx):
            sd, pd = dates[j], dates[j-1]
            sp = px.get(sd); pp = px.get(pd)
            ep = d.get(sd); epp = d.get(pd)
            if sp and pp and pp>0 and ep and epp and epp>0:
                sr.append(sp/pp-1)
                er.append(ep/epp-1)
        corr = 0
        if len(sr) >= 5:
            ms = sum(sr)/len(sr); me = sum(er)/len(er)
            d1 = math.sqrt(sum((s-ms)**2 for s in sr))
            d2 = math.sqrt(sum((e-me)**2 for e in er))
            corr = sum((s-ms)*(e-me) for s,e in zip(sr,er))/(d1*d2) if d1*d2>0 else 0
        
        # 因子2: 板块内相对动量（个股动量 - 板块动量）
        p0 = d.get(dates[today_idx - 12]); p1 = d.get(dates[today_idx - 1])
        etf_mom = p1/p0-1 if p0 and p1 and p0>0 else -999
        cat_p0 = px.get(dates[today_idx - 12]); cat_p1 = px.get(dates[today_idx - 1])
        cat_mom = cat_p1/cat_p0-1 if cat_p0 and cat_p1 and cat_p0>0 else 0
        rel_mom = etf_mom - cat_mom if etf_mom > -999 else -999
        
        # 因子3: 相对波动（低波动加分）
        rets = [d.get(dates[j])/d.get(dates[j-1])-1 for j in range(today_idx-12, today_idx)
                if d.get(dates[j]) and d.get(dates[j-1]) and d.get(dates[j-1])>0]
        volatility = statistics.stdev(rets) if len(rets) >= 5 else 999
        
        # 因子4: 规模（存续天数代表ETF的成熟度）
        scale = len(d)
        
        scores_list.append((code, corr, rel_mom, volatility, scale))
    
    # 排名化
    if not scores_list:
        return []
    
    def rank_on_field(field_idx, reverse=False):
        items = [(s[0], s[field_idx]) for s in scores_list]
        items.sort(key=lambda x: x[1], reverse=reverse)
        ranks = {}
        for i, (code, _) in enumerate(items):
            ranks[code] = i / (len(items)-1) * 100 if len(items) > 1 else 50
        return ranks
    
    corr_rank = rank_on_field(1, reverse=True)
    rel_mom_rank = rank_on_field(2, reverse=True)
    vol_rank = rank_on_field(3, reverse=False)  # 低波动加分
    scale_rank = rank_on_field(4, reverse=True)
    
    final_scores = {}
    for code, _, _, _, _ in scores_list:
        s = (corr_rank.get(code, 0) * ETF_FACTORS['corr_to_sector']['weight'] +
             rel_mom_rank.get(code, 0) * ETF_FACTORS['rel_momentum']['weight'] +
             vol_rank.get(code, 0) * ETF_FACTORS['rel_volatility']['weight'] +
             scale_rank.get(code, 0) * ETF_FACTORS['scale']['weight'])
        final_scores[code] = s
    
    return sorted(final_scores.items(), key=lambda x: -x[1])


# ──────────────────────────────────────────
# 信号
# ──────────────────────────────────────────
def get_signal(cat_px, cat_atr_ratio, cat_etfs, all_closes, today_idx, dates,
               atr_min=0.85):
    """多因子信号"""
    # ATR比硬过滤（波动萎缩的板块排除）
    today = dates[today_idx - 1]
    categories = [c for c in cat_px if c in CATEGORIES]
    
    eligible = []
    for cat in categories:
        ar = cat_atr_ratio.get(cat, {}).get(today, 0)
        if ar >= atr_min:
            eligible.append(cat)
    
    if not eligible:
        return None, []
    
    # 多因子打分
    ranked = compute_sector_scores(
        {c: cat_px[c] for c in eligible}, cat_atr_ratio,
        cat_etfs, all_closes, today_idx, dates)
    
    if not ranked:
        return None, []
    
    sector = ranked[0][0]
    
    # 板块内多因子选ETF
    etf_codes = cat_etfs.get(sector, [])
    etf_ranked = compute_etf_scores(sector, etf_codes, cat_px, all_closes,
                                      today_idx, dates, cat_etfs)
    picked = [code for code, _ in etf_ranked[:ETF_PICK_N]]
    
    return sector, ranked, etf_ranked


# ──────────────────────────────────────────
# 回测
# ──────────────────────────────────────────
def backtest(start_date='2014-01-01', end_date='2026-06-01'):
    """多因子回测"""
    cat_px, dates, wd, wk, cat_atr, all_closes, cat_etfs = load_all_data()
    
    ds = [d for d in dates if start_date <= d <= end_date]
    eq = 1.0; eq_c = [1.0]; tc = 0; lw = ''
    sector = None; held = []
    
    for i, today in enumerate(ds):
        if i < max(60, 12):
            eq_c.append(eq); continue
        wk_key = wk[today]
        is_mon = (wd[today] == 0)
        rebal = (is_mon and wk_key != lw)
        
        if rebal:
            lw = wk_key
            result = get_signal(cat_px, cat_atr, cat_etfs, all_closes, i, ds)
            if result[0]:
                sector = result[0]
                held = [c for c, _ in result[2][:ETF_PICK_N]]
            else:
                sector = None; held = []
            tc += 1 if held else 0
        
        if held:
            rets = []
            for code in held:
                pt = all_closes.get(code, {}).get(today)
                py = all_closes.get(code, {}).get(ds[max(0, i-1)])
                if pt and py and py > 0:
                    rets.append(pt/py-1)
            if rets:
                eq *= (1 + sum(rets)/len(rets))
        else:
            eq *= (1 + 0.02/252)
        eq_c.append(eq)
    
    yrs = len(ds)/252
    ar = eq**(1/yrs)-1 if yrs else 0
    peak = 1; mdd = 0
    for e in eq_c[1:]:
        if e > peak: peak = e
        dd = (e-peak)/peak
        if dd < mdd: mdd = dd
    drs = [eq_c[j]/eq_c[j-1]-1 for j in range(1, len(eq_c))]
    mr = sum(drs)/len(drs) if drs else 0
    v = sum((r-mr)**2 for r in drs)/len(drs) if drs else 0
    sp = (mr-0.02/252)/math.sqrt(v)*math.sqrt(252) if v else 0
    return {'ar': ar, 'mdd': mdd, 'sp': sp, 'eq': eq, 'tc': tc}


if __name__ == '__main__':
    # 对比：原单因子 vs 多因子
    cat_px, dates, wd, wk, cat_atr, all_closes, cat_etfs = load_all_data()
    
    categories = [c for c in cat_px if c in CATEGORIES]
    
    print('=' * 65)
    print('  多因子 vs 单因子 对比回测')
    print('=' * 65)
    
    # 原单因子 (atr_momentum_rotation 的相关度选3只)
    r_old = atr.backtest_etf(cat_px, categories, dates, wd, wk, cat_atr,
                              all_closes, cat_etfs, etf_pick_n=3)
    
    print(f'\n  {"版本":<20} {"年化":>8} {"夏普":>6} {"回撤":>8} {"交易":>5}')
    print(f'  {"-" * 50}')
    print(f'  {"单因子(动量)":<20} {r_old["annual_return"]*100:>+7.2f}% {r_old["sharpe"]:>+5.2f} {r_old["max_drawdown"]*100:>7.2f}% {r_old["trade_count"]:>5d}')
    
    r_new = backtest()
    diff = (r_new['ar'] - r_old['annual_return']) * 100
    tag = '🏆' if diff > 0 else '🟡' if diff > -2 else '🔴'
    print(f'  {"多因子(4因子)":<20} {r_new["ar"]*100:>+7.2f}% {r_new["sp"]:>+5.2f} {r_new["mdd"]*100:>7.2f}% {r_new["tc"]:>5d}  差异{diff:+.2f}% {tag}')
    
    print()
    print('  板块因子权重:')
    for fn, cfg in SECTOR_FACTORS.items():
        print(f'    {cfg["desc"]:<16} {cfg["weight"]*100:>3.0f}%')
    print()
    print('  ETF因子权重:')
    for fn, cfg in ETF_FACTORS.items():
        print(f'    {cfg["desc"]:<16} {cfg["weight"]*100:>3.0f}%')
