"""
ATR动量板块轮动策略 — 最终生产版
======================================
参数: 动15MA175_ETF28_T3
变动: 商品/周期/资源板块新增 518880(黄金ETF华夏)

用法:
  python atr_momentum_rotation.py         # 跑完整回测
  python atr_momentum_rotation.py --scan  # 参数扫描

策略逻辑:
  1. 每周一收盘计算信号
  2. 选出15天动量最强且板块指数>175日均线的板块
  3. 板块内按28天动量选前3只ETF
  4. 周二开盘执行(等权买入)
  5. 无板块通过MA过滤时空仓
"""
import json, os, sys, numpy as np
from collections import defaultdict, Counter
from datetime import datetime as dt_std

# ============================================================
#  配置
# ============================================================
DATA_DIR = r'D:\QClaw_Trading\data\history'
CAT_FILE = r'D:\QClaw_Trading\data\cat_assignment_full.json'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'

# 最终参数
MOM_DAYS = 15       # 板块动量窗口(天)
MA_DAYS = 175       # 绝对趋势过滤(日均线)
ETF_MOM = 28        # ETF排序动量窗口(天)
TOP_K = 3           # 每板块选ETF数
START_DATE = '2014-01-01'
END_DATE = '2025-12-31'

# 补充ETF(手工精选已验证有效)
EXTRA_ETFS = {
    '商品/周期/资源': ['518880'],
}

# ============================================================
#  数据层
# ============================================================
def load_names():
    """加载ETF名称字典"""
    if not os.path.exists(POOL_FILE):
        return {}
    with open(POOL_FILE, 'r', encoding='utf-8') as f:
        pool = json.load(f)
    names = {}
    for e in pool.get('data', []):
        names[str(e['code'])] = e.get('name', '').replace('\xa0', ' ').strip()
    names['518880'] = '黄金ETF华夏'
    return names

def load_category_map():
    """加载ETF→板块映射"""
    with open(CAT_FILE, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    cat_map = {}
    for kw, entries in raw.get('assignments', {}).items():
        for entry in entries:
            cat_map[entry[0]] = entry[1]
    return cat_map

def build_sectors(cat_map):
    """构建板块→ETF列表(排除海外/跨境, 加入补充ETF)"""
    sectors = defaultdict(list)
    for code, cat in cat_map.items():
        if cat != '海外/跨境':
            sectors[cat].append(code)
    for cat, codes in EXTRA_ETFS.items():
        for c in codes:
            if c not in sectors[cat]:
                sectors[cat].append(c)
    return dict(sectors)

def load_etf_records(code):
    """加载单只ETF的日线记录"""
    for prefix in ['', 'sz']:
        path = os.path.join(DATA_DIR, prefix + code + '.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                records = json.load(f).get('records', [])
            if records:
                return records
    return []

def load_price_dict(cat_map, sectors):
    """
    加载所有ETF价格字典 {code: {date: close}}
    仅保留截至END_DATE的数据, 跳过无数据ETF
    """
    all_codes = set()
    for codes in sectors.values():
        all_codes.update(codes)
    
    prices = {}
    for code in all_codes:
        records = load_etf_records(code)
        if not records:
            continue
        pm = {}
        for r in records:
            dt = r.get('date', '')
            if dt > END_DATE:
                continue
            pm[dt] = r.get('close', 0.0)
        if pm:
            prices[code] = pm
    
    return prices

def build_unified_dates(prices):
    """所有ETF的交易日期并集, 排序"""
    all_dates = set()
    for pm in prices.values():
        all_dates.update(pm.keys())
    return sorted(all_dates)

# ============================================================
#  板块指数
# ============================================================
def build_sector_indices(dates, prices, sectors):
    """
    板块指数 = 板块内所有ETF当日价格均值
    要求至少1/3的ETF有数据才计算
    返回 {板块名: ndarray(len(dates))}
    """
    indices = {}
    for cat, codes in sectors.items():
        arr = np.full(len(dates), np.nan)
        for i, dt in enumerate(dates):
            vals = [prices[c].get(dt, np.nan) for c in codes if c in prices]
            valid = [v for v in vals if not np.isnan(v)]
            # 至少需要1/3的ETF有数据
            if len(valid) >= max(1, len(codes) // 3):
                arr[i] = np.mean(valid)
        indices[cat] = arr
    return indices

# ============================================================
#  回测引擎
# ============================================================
def backtest(dates, prices, sectors, indices,
             start_date=START_DATE,
             mom_days=MOM_DAYS, ma_days=MA_DAYS,
             etf_mom=ETF_MOM, top_k=TOP_K):
    """
    双动量板块轮动回测
    
    信号逻辑:
      周一收盘 → 板块15日动量排序 + MA175过滤 → 选动量最强板块
      → 板块内ETF按28日动量排序 → 选TOP3 → 周而开盘价入场
    
    返回结果字典
    """
    # 计算起始索引
    sid = next((i for i, d in enumerate(dates) if d >= start_date), None)
    if sid is None or sid >= len(dates):
        return None
    
    # 需要足够的历史数据计算MA/动量
    warmup = max(mom_days, ma_days, etf_mom)
    
    # 初始化
    cash = 1.0                     # 现金净值(不含持仓浮盈)
    cur_sector = None              # 当前持有板块名
    held_etfs = []                 # 当前持有ETF列表
    entry_prices = {}              # {code: 入场价格(周二开盘)}
    equity = [1.0]                 # 全账户净值曲线
    
    trades = []                    # 交易日志 [(date, action, detail)]
    yr_nav = {}                    # {年份: 年末净值}
    
    for i in range(sid, len(dates)):
        dt = dates[i]
        yr = dt[:4]
        
        # ---- 计算当前净值 ----
        if cur_sector and held_etfs:
            rets = []
            for c in held_etfs:
                cp = prices[c].get(dt, np.nan)
                ep = entry_prices.get(c, np.nan)
                if not np.isnan(cp) and not np.isnan(ep) and ep > 0:
                    rets.append(cp / ep)
            nav = cash * np.mean(rets) if rets else cash
        else:
            nav = cash
        equity.append(nav)
        
        # 每年末记录净值
        if yr not in yr_nav or i == len(dates) - 1 or dates[i+1][:4] != yr:
            yr_nav[yr] = nav
        
        # ---- 信号计算(仅周一) ----
        wd = dt_std.strptime(dt, '%Y-%m-%d').weekday()
        if wd != 0:   # 非周一, 跳过
            continue
        if i < warmup:
            continue
        
        # 找最佳板块: 动量最强 + MA过滤
        best_sector = None
        best_momentum = -999.0
        
        for cat, idx in indices.items():
            curr = idx[i]
            if np.isnan(curr):
                continue
            
            # MA175过滤
            if i >= ma_days:
                # 仅用非NaN值计算MA
                ma_vals = idx[i-ma_days:i]
                ma_vals = ma_vals[~np.isnan(ma_vals)]
                if len(ma_vals) < ma_days // 3:
                    continue   # 数据不够, 跳过该板块
                ma = np.mean(ma_vals)
                if curr <= ma:
                    continue  # 在MA之下, 排除
            
            # 15天动量
            past = idx[i - mom_days]
            if np.isnan(past) or past <= 0:
                continue
            momentum = curr / past - 1
            
            if momentum > best_momentum:
                best_momentum = momentum
                best_sector = cat
        
        # ---- 执行信号 ----
        if best_sector and best_sector != cur_sector:
            # 换仓/开仓: 在板块内选ETF
            candidates = sectors.get(best_sector, [])
            ranked = []
            
            for c in candidates:
                if c not in prices:
                    continue
                cp = prices[c].get(dt, np.nan)
                if np.isnan(cp):
                    continue
                pp = prices[c].get(dates[i - etf_mom], np.nan)
                if np.isnan(pp) or pp <= 0:
                    continue
                etf_mom_val = cp / pp - 1
                
                # 确保有下一个交易日的价格作为入场价
                if i + 1 < len(dates):
                    entry_p = prices[c].get(dates[i+1], np.nan)
                    if not np.isnan(entry_p) and entry_p > 0:
                        ranked.append((etf_mom_val, c, entry_p))
            
            ranked.sort(reverse=True)
            
            if ranked:
                selected = ranked[:min(top_k, len(ranked))]
                cash = nav
                cur_sector = best_sector
                held_etfs = []
                entry_prices = {}
                
                mom_str = f'{best_momentum*100:.1f}%'
                code_str = ', '.join([c for _, c, _ in selected])
                trades.append((dt, '开仓', f'{best_sector}(动量{mom_str}) → {code_str}'))
                
                for _, c, ep in selected:
                    held_etfs.append(c)
                    entry_prices[c] = ep
        
        elif not best_sector and cur_sector:
            # 无板块通过MA过滤 → 空仓
            trades.append((dt, '空仓', f'{cur_sector}出清'))
            cash = nav
            cur_sector = None
            held_etfs = []
            entry_prices = {}
    
    # ---- 计算指标 ----
    eq = np.array(equity)
    yrs_trading = (len(eq) - 1) / 250.0
    if yrs_trading <= 0:
        return None
    
    total_ret = eq[-1] - 1
    ann_ret = eq[-1] ** (1.0 / yrs_trading) - 1
    
    # 最大回撤
    running_max = np.maximum.accumulate(eq)
    dd = (running_max - eq) / running_max
    max_dd = float(np.max(dd))
    
    # 夏普比率
    daily_rets = np.diff(eq) / eq[:-1]
    sharpe = float(np.mean(daily_rets) * 250.0 /
                   (np.std(daily_rets) * np.sqrt(250.0) + 1e-9))
    
    # 逐年收益
    sorted_yrs = sorted(yr_nav.keys())
    year_rets = {}
    prev = 1.0
    for yr in sorted_yrs:
        nv = yr_nav[yr]
        year_rets[yr] = nv / prev - 1
        prev = nv
    
    # 板块选中次数
    cat_counter = Counter()
    for _, action, detail in trades:
        if '开仓' in action or '出清' in action:
            for cat in sectors:
                if cat in detail and cat not in ('出清',):
                    cat_counter[cat] += 1
                    break
    
    return {
        'ann_ret': ann_ret,
        'sharpe': sharpe,
        'max_dd': max_dd,
        'total_ret': total_ret,
        'years': yrs_trading,
        'year_rets': year_rets,
        'trades': trades,
        'cat_counter': cat_counter,
        'equity': eq,
    }

# ============================================================
#  参数扫描
# ============================================================
def scan_params(dates, prices, sectors, indices, start_date=START_DATE):
    """扫描动量/MA/ETF动量/TopK参数组合"""
    print('\n参数扫描中...')
    param_space = []
    
    for md in [14, 15, 16, 17]:
        for ma in [160, 165, 170, 175, 180, 185, 190]:
            for em in [20, 22, 24, 26, 28, 30]:
                for tk in [3, 4]:
                    r = backtest(dates, prices, sectors, indices,
                                 start_date, md, ma, em, tk)
                    if r is None:
                        continue
                    param_space.append((r['ann_ret'], r['sharpe'],
                                        r['max_dd'], md, ma, em, tk))
    
    param_space.sort(reverse=True)
    return param_space

# ============================================================
#  打印输出
# ============================================================
def print_results(result, sectors, names, label=''):
    if result is None:
        print('failed: no data')
        return
    
    print()
    print('='*65)
    print('  ' + label)
    print('='*65)
    md = result.get('mom_days','?'); ma = result.get('ma_days','?')
    em = result.get('etf_mom','?'); tk = result.get('top_k','?')
    print('  参数: 动%dMA%d_ETF%d_T%d' % (md, ma, em, tk))
    print('  年化收益: %.2f%%' % (result['ann_ret']*100))
    print('  夏普比率: %.2f' % result['sharpe'])
    print('  最大回撤: %.2f%%' % (result['max_dd']*100))
    print('  总收益: %.0f%%' % (result['total_ret']*100))
    print('  回测区间: %.0f年' % result['years'])
    print()
    
    print('  逐年收益:')
    print('    %6s %8s' % ('年份','年收益'))
    print('    ' + '-'*16)
    neg = 0
    for yr, ret in sorted(result['year_rets'].items()):
        tag = '**亏损' if ret < 0 else '**盈利'
        print('    %6s %+7.2f%%  %s' % (yr, ret*100, tag))
        if ret < 0:
            neg += 1
    print('    %d年仅%d年亏损' % (len(result['year_rets']), neg))
    print()
    
    if result['cat_counter']:
        total = sum(result['cat_counter'].values())
        print('  板块选中率(%d个交易周):' % total)
        for cat, cnt in result['cat_counter'].most_common():
            print('    %-12s: %3d周 (%d%%)' % (cat, cnt, cnt*100/total))

def print_trades(result, sectors, names):
    """打印交易日志摘要(每年首次)"""
    if not result or not result['trades']:
        return
    
    print(f'\n{"="*65}')
    print(f'  交易日志摘要')
    print(f'{"="*65}')
    
    cur_yr = ''
    for dt, action, detail in result['trades']:
        yr = dt[:4]
        if yr != cur_yr:
            print(f'\n--- {yr}年 ---')
            cur_yr = yr
        print(f'  {dt}  {action:4s}  {detail}')

def print_sectors(sectors, names):
    """打印板块及ETF清单"""
    print(f'\n{"="*65}')
    print(f'  板块及ETF清单 (共{sum(len(v) for v in sectors.values())}只)')
    print(f'{"="*65}')
    
    for cat in sorted(sectors.keys()):
        codes = sectors[cat]
        print(f'\n{cat} ({len(codes)}只):')
        for c in sorted(codes):
            nm = names.get(c, c)
            print(f'  {c:>6}  {nm}')

# ============================================================
#  主流程
# ============================================================
def main():
    import sys as _sys
    sys.stdout.reconfigure(encoding='utf-8')
    do_scan = '--scan' in _sys.argv
    
    print('加载数据...')
    names = load_names()
    cat_map = load_category_map()
    sectors = build_sectors(cat_map)
    prices = load_price_dict(cat_map, sectors)
    dates = build_unified_dates(prices)
    indices = build_sector_indices(dates, prices, sectors)
    
    print(f'  交易日: {len(dates)}天 ({dates[0][:10]}~{dates[-1][:10]})')
    print(f'  板块: {len(sectors)}个')
    print(f'  ETF: {sum(len(v) for v in sectors.values())}只')
    for cat in sorted(sectors):
        valid = int(np.sum(~np.isnan(indices[cat])))
        print(f'    {cat:12s}: {len(sectors[cat])}只ETF, {valid}天有效')
    
    # 回测(最终参数)
    print(f'\n回测参数: 动{MOM_DAYS}MA{MA_DAYS}_ETF{ETF_MOM}_T{TOP_K}')
    result = backtest(dates, prices, sectors, indices,
                      START_DATE, MOM_DAYS, MA_DAYS, ETF_MOM, TOP_K)
    
    # 给结果补充参数信息用于输出
    if result:
        result['mom_days'] = MOM_DAYS
        result['ma_days'] = MA_DAYS
        result['etf_mom'] = ETF_MOM
        result['top_k'] = TOP_K
    
    print_results(result, sectors, names, '最终版: 动15MA175_ETF28_T3 +黄金ETF')
    print_trades(result, sectors, names)
    print_sectors(sectors, names)
    
    # 分时段验证
    print(f'\n{"="*65}')
    print(f'  分时段验证')
    print(f'{"="*65}')
    print(f'  {"时段":<16} {"年化":>8} {"夏普":>7} {"回撤":>8}')
    print(f'  {"-"*42}')
    for label, sd in [('全量2014~2025', '2014-01-01'),
                      ('~2018起', '2018-01-01'),
                      ('~2020起', '2020-01-01'),
                      ('~2022起', '2022-01-01')]:
        r = backtest(dates, prices, sectors, indices,
                     sd, MOM_DAYS, MA_DAYS, ETF_MOM, TOP_K)
        if r:
            print(f'  {label:<16} {r["ann_ret"]:>+7.2%} {r["sharpe"]:>6.2f} {r["max_dd"]:>7.2%}')
    
    # 参数扫描
    if do_scan:
        ps = scan_params(dates, prices, sectors, indices, START_DATE)
        print(f'\n{"="*65}')
        print(f'  参数扫描Top 20')
        print(f'{"="*65}')
        print(f'  {"参数":<24} {"年化":>8} {"夏普":>7} {"回撤":>8}')
        print(f'  {"-"*50}')
        for a, s, m, md, ma, em, tk in ps[:20]:
            print(f'  动{md}MA{ma}_ETF{em}_T{tk:<5} {a:>+7.2%} {s:>6.2f} {m:>7.2%}')
    
    print('\n✅ 回测完成')

if __name__ == '__main__':
    main()
