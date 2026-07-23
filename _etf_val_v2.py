# -*- coding: utf-8 -*-
"""
ETF板块动量+估值轮动策略回测
数据: 本地历史ETF日线 (D:\QClaw_Trading\data\history\)
估值: BaoStock成分股PE聚合到行业板块

策略对比:
  A: 纯动量TOP1（12天动量）
  B: 低估值过滤（只选估值<0.4板块中的动量最强）
  C: 估值加权（动量分×(1-估值分位)）
  D: 纯低估TOP1
  E: 动量TOP1 + ATR过滤（已知最优基准）
"""
import os, json, time, baostock as bs, pandas as pd, numpy as np

np.random.seed(42)
HIST_DIR = r'D:\QClaw_Trading\data\history'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
OUT = r'D:\QClaw_Trading\etf_val_real_results.csv'

# ====================== 1. 加载ETF池 ======================
with open(POOL_FILE, 'r', encoding='utf-8') as f:
    pool = json.load(f)

code_to_cat = {i['code'].strip(): (i.get('category') or '其他').strip() or '其他'
                for i in pool['data']}

# 读取本地历史ETF
files = sorted([f for f in os.listdir(HIST_DIR) if f.endswith('.json')])
etf_list = []
for f in files:
    code = f[:-5]
    try:
        with open(os.path.join(HIST_DIR, f), 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
        if isinstance(raw, list) and len(raw) > 0:
            df = pd.DataFrame(raw)
        elif isinstance(raw, dict) and 'data' in raw:
            df = pd.DataFrame(raw['data'])
        else:
            df = pd.DataFrame(raw)
        df['code'] = code
        etf_list.append(df)
    except Exception as e:
        pass

etf_df = pd.concat(etf_list, ignore_index=True)
print(f'本地ETF: {etf_df["code"].nunique()}只, {len(etf_df)}行')

# 标准化字段
date_col = 'date' if 'date' in etf_df.columns else 'day'
etf_df['date'] = pd.to_datetime(etf_df[date_col])
etf_df['close'] = pd.to_numeric(etf_df.get('close', etf_df.get('p')), errors='coerce')
etf_df['high'] = pd.to_numeric(etf_df.get('high', etf_df.get('h')), errors='coerce')
etf_df['low'] = pd.to_numeric(etf_df.get('low', etf_df.get('l')), errors='coerce')
etf_df['volume'] = pd.to_numeric(etf_df.get('volume', etf_df.get('v')), errors='coerce')
etf_df['category'] = etf_df['code'].map(code_to_cat).fillna('其他')

# 过滤，只保留在我们池中的ETF
etf_df = etf_df[etf_df['category'] != '其他']
etf_df = etf_df.dropna(subset=['close', 'date'])
etf_df = etf_df.sort_values(['code', 'date'])
print(f'有效: {etf_df["code"].nunique()}只, {len(etf_df)}行')
print(f'板块: {sorted(etf_df["category"].unique())}')

# ====================== 2. BaoStock行业PE分位 ======================
print('\n--- 获取BaoStock行业PE分位 ---')
bs.login()

# 获取所有股票PE(ttm)
# 简化：每季度取一次申万一级行业指数成分股的PE中位数
# 先取沪深300成分股行业分布
rs_ind = bs.query_stock_industry()
inds = []
while rs_ind.error_code == '0' and rs_ind.next():
    inds.append(rs_ind.get_row_data())
ind_df = pd.DataFrame(inds, columns=rs_ind.fields)

# 证监会行业到ETF板块的映射
sw_map = {
    'I65软件和信息技术服务业': '科技/TMT/AI',
    'C39计算机、通信和其他电子设备制造业': '芯片半导体',
    'C27医药制造业': '医药',
    'J66货币金融服务': '金融',
    'J67资本市场服务': '金融',
    'I64互联网和相关服务': '科技/TMT/AI',
    'C26化学原料和化学制品制造业': '商品/周期/资源',
    'D44电力、热力生产和供应业': '制造/基建/公用',
    'C36汽车制造业': '制造/基建/公用',
    'C34通用设备制造业': '制造/基建/公用',
    'C35专用设备制造业': '制造/基建/公用',
    'C30非金属矿物制品业': '制造/基建/公用',
    'C38电气机械和器材制造业': '制造/基建/公用',
    'F52零售业': '消费',
    'C20木材加工和木、竹、藤、棕、草制品业': '消费',
    'C19纺织服装、服饰业': '消费',
    'C17化学纤维制造业': '商品/周期/资源',
    'B07石油和天然气开采业': '商品/周期/资源',
    'B08黑色金属矿采选业': '商品/周期/资源',
    'H11批发业': '消费',
}
ind_df['etf_sector'] = ind_df['industry'].map(sw_map).fillna('宽基A股')

# 取样本股票近期PE
# 从all_stock列表中取前200只代表性股票
rs_stk = bs.query_all_stock(day='2026-07-10')
all_stks = []
while rs_stk.error_code == '0' and rs_stk.next():
    all_stks.append(rs_stk.get_row_data())
all_stks_df = pd.DataFrame(all_stks, columns=rs_stk.fields)
all_stks_df = all_stks_df.merge(ind_df[['code', 'industry', 'etf_sector']], on='code', how='left')

# 取每板块代表性股票（前10只）
sample_stks = all_stks_df.groupby('etf_sector').head(10)['code'].tolist()
print(f'查询 {len(sample_stks)} 只样本股票PE...')

# 取这些股票近期K线（含PE）
pe_data = []
for code in sample_stks[:30]:  # 限制30只避免超时
    rs = bs.query_history_k_data_plus(code,
        'date,code,open,high,low,close,volume,peTTM,pbMRQ',
        start_date='2026-01-01', end_date='2026-07-10', frequency='d')
    rows = []
    while rs.error_code == '0' and rs.next():
        rows.append(rs.get_row_data())
    if rows:
        tmp = pd.DataFrame(rows, columns=rs.fields)
        pe_data.append(tmp)

bs.logout()

if pe_data:
    pe_df = pd.concat(pe_data, ignore_index=True)
    pe_df['date'] = pd.to_datetime(pe_df['date'])
    pe_df['peTTM'] = pd.to_numeric(pe_df['peTTM'], errors='coerce')
    pe_df['pbMRQ'] = pd.to_numeric(pe_df['pbMRQ'], errors='coerce')
    
    # 合并行业
    pe_df = pe_df.merge(ind_df[['code', 'etf_sector']], on='code', how='left')
    
    # 按日期+板块算PE分位
    pe_df['pe_rank'] = pe_df.groupby(['date', 'etf_sector'])['peTTM'].transform(
        lambda x: x.rank(pct=True) if x.notna().any() else np.nan)
    pe_df['val_score'] = 1 - pe_df['pe_rank']  # 低PE=高估值分数
    
    pe_panel = pe_df.groupby(['date', 'etf_sector'])['val_score'].mean().reset_index()
    print(f'估值面板: {len(pe_panel)}行, 覆盖日期: {pe_panel["date"].min()}~{pe_panel["date"].max()}')
    print('板块分布:', pe_df.groupby('etf_sector')['code'].count().to_string())
else:
    pe_panel = pd.DataFrame(columns=['date', 'etf_sector', 'val_score'])

# ====================== 3. 板块聚合 ======================
# 按板块聚合ETF日线
agg = etf_df.groupby(['date', 'category']).agg(
    close=('close', 'mean'),
    volume=('volume', 'sum'),
    high=('high', 'max'),
    low=('low', 'min'),
    n_etfs=('code', 'count'),
).reset_index()
agg = agg.rename(columns={'category': 'sector'})
agg = agg.sort_values(['sector', 'date'])
agg = agg[agg['date'] >= '2020-01-01']

# 计算动量、ATR
agg['ret'] = agg.groupby('sector')['close'].pct_change()
agg['mom12'] = agg.groupby('sector')['ret'].transform(lambda x: x.rolling(12, min_periods=6).sum())
agg['atr'] = (agg['high'] - agg['low']) / agg.groupby('sector')['close'].shift(1)
agg['atr_ratio'] = agg.groupby('sector')['atr'].transform(lambda x: x.rolling(14,min_periods=7).mean()) / \
                   agg.groupby('sector')['atr'].transform(lambda x: x.rolling(60,min_periods=20).mean())

# 合并估值
agg = agg.merge(pe_panel.rename(columns={'etf_sector': 'sector', 'date': 'date2'}), 
                left_on=['sector'], right_on=['sector'], how='left')

# 由于估值数据只有2026上半年，用成交量rank作为估值代理
agg['vol_rank'] = agg.groupby('date')['volume'].rank(pct=True)
agg['val_score'] = agg['val_score'].fillna(1 - agg['vol_rank'])  # 缺估值时用vol_rank代理

agg = agg.dropna(subset=['mom12', 'atr_ratio'])
print(f'\n有效数据: {len(agg)}行, {agg["date"].nunique()}个交易日')

# ====================== 4. 回测 ======================
dates = sorted(agg['date'].unique())
results = []

for strat_name, filter_fn, note in [
    ('A_纯动量TOP1',      lambda d: d.nlargest(1,'mom12'),            '12天动量选最强板块'),
    ('B_低估值+动量TOP1', lambda d: (d[d['val_score']>0.5].nlargest(1,'mom12') if len(d[d['val_score']>0.5])>0 else d.nlargest(1,'mom12')), '低估值板块中选动量最强'),
    ('C_估值加权动量TOP1',lambda d: d.assign(score=d['mom12']*(1-d['val_score'])).nlargest(1,'score'), '动量分×估值加权'),
    ('D_纯低估TOP1',      lambda d: d.nsmallest(1,'val_score'),       '选估值最低板块'),
    ('E_动量+ATR>0.9',   lambda d: d[d['atr_ratio']>0.9].nlargest(1,'mom12') if len(d[d['atr_ratio']>0.9])>0 else d.nlargest(1,'mom12'), 'ATR>0.9过滤'),
    ('F_全信号ATR动量',   lambda d: d.assign(score=d['mom12']*d['atr_ratio']*(1-d['val_score'])).nlargest(1,'score'), '三维因子'),
]:
    rets = []
    for d in dates:
        day = agg[agg['date'] == d]
        if day.empty: continue
        sel = filter_fn(day)
        if sel.empty: continue
        r = sel.iloc[0]['mom12']  # 12天动量 (累积收益)
        rets.append({'date': d, 'ret': r})
    
    ret_df = pd.DataFrame(rets).dropna(subset=['ret']).set_index('date')
    if ret_df.empty:
        print(f'{strat_name}: 无数据')
        continue
    
    cum = (1 + ret_df['ret']).cumprod()
    ann = cum.iloc[-1] ** (252.0 / len(cum)) - 1
    peak = cum.cummax()
    mdd = ((cum - peak) / peak).min()
    sharpe = ret_df['ret'].mean() / ret_df['ret'].std() * np.sqrt(252) if ret_df['ret'].std() > 0 else 0
    win = (ret_df['ret'] > 0).mean()
    results.append({'strategy': strat_name, 'note': note, 'ann': ann, 'mdd': mdd, 
                    'sharpe': sharpe, 'win': win, 'n': len(ret_df)})
    print(f'{strat_name}: 年化={ann*100:.2f}% MDD={mdd*100:.2f}% Sharpe={sharpe:.2f} 胜率={win*100:.1f}%')

if results:
    res_df = pd.DataFrame(results)
    res_df.to_csv(OUT, index=False)
    print(f'\n结果已保存: {OUT}')
    print('\n最佳策略:', res_df.loc[res_df['sharpe'].idxmax(), 'strategy'])
