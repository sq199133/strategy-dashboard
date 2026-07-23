#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, datetime, glob, os, re, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

def get_daily(secid):
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={secid},day,,,20,qfq'
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/'})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode('utf-8'))
        data = d.get('data',{}).get(secid,{})
        klines = data.get('qfqday',[]) or data.get('day',[])
        return [(k[0], float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])) for k in klines]
    except: return []

print("="*68)
print(f"  今日复盘  2026-07-20 (周一)")
print("="*68)

# 1. 今日行情
targets = [
    ('sz159837','生物科技ETF(159837)'),
    ('sh560080','中药ETF(560080)'),
    ('sh510300','沪深300ETF'),
    ('sz159949','创业板50ETF'),
]
print("\n【一、今日行情（腾讯日K，2026-07-20收盘）】")
print(f"{'名称':<22}{'07-18':>9}{'07-20':>9}{'周一涨跌':>10}{'本周前':>9}")
for secid, name in targets:
    k = get_daily(secid)
    if not k: print(f"{name:<22}获取失败"); continue
    dates = {r[0]: r for r in k}
    p18 = dates.get('2026-07-18')
    p19 = dates.get('2026-07-19')
    p20 = dates.get('2026-07-20')
    p17 = dates.get('2026-07-17')
    
    if p18 and p20:
        chg = (p20[1]/p18[1]-1)*100
        # 本周vs上周收盘
        if p17:
            wk_chg = (p18[1]/p17[1]-1)*100
            print(f"{name:<22}{p18[1]:>9.3f}{p20[1]:>9.3f}{chg:>+9.2f}%{wk_chg:>+8.2f}%")
        else:
            print(f"{name:<22}{p18[1]:>9.3f}{p20[1]:>9.3f}{chg:>+9.2f}%")
    else:
        # 周末休市，直接比较07-17和07-20
        if p17 and p20:
            chg = (p20[1]/p17[1]-1)*100
            print(f"{name:<22}周末休市{p20[1]:>9.3f}{chg:>+9.2f}%")

# 2. 持仓159837最新状态
print("\n【二、持仓状态（159837 生物科技ETF）】")
# 持仓成本（来自holdings.md）
buy_price = 0.482
buy_qty = 155600
cost = buy_price * buy_qty
p20_159837 = None
for secid, name in [('sz159837','生物科技ETF')]:
    k = get_daily(secid)
    if k:
        dates = {r[0]: r for r in k}
        p20_159837 = dates.get('2026-07-20', [None,0])[1]
        p18 = dates.get('2026-07-18', [None,0])[1]
        p17 = dates.get('2026-07-17', [None,0])[1]
        
        # 本周高低价
        this_week = [r for r in k if r[0] >= '2026-07-18']
        high = max(r[3] for r in this_week) if this_week else p18
        low = min(r[4] for r in this_week) if this_week else p18
        
        # 持仓高点（历史）
        all_high = max(r[3] for r in k if r[0] >= '2026-07-10')
        
        mkt_val = p20_159837 * buy_qty
        pnl = mkt_val - cost
        pnl_pct = pnl / cost * 100
        
        print(f"  持仓成本:  ¥{buy_price:.3f} × {buy_qty:,} = ¥{cost:,.0f}")
        print(f"  当前价(07-20):  ¥{p20_159837:.3f}")
        print(f"  市值:  ¥{mkt_val:,.0f}")
        print(f"  浮动盈亏:  ¥{pnl:,.0f} ({pnl_pct:+.2f}%)")
        print(f"  本周区间:  ¥{low:.3f} ~ ¥{high:.3f}")
        print(f"  历史高点(07-11):  ¥{all_high:.3f}")
        # 止损检查
        stop_hard = buy_price * 0.92  # 0.444
        stop_hwm = all_high * 0.90
        hwm_ret = (p20_159837/all_high - 1) * 100
        print(f"  硬止损价:  ¥{stop_hard:.3f}  {'✅未触发' if p20_159837>stop_hard else '❌已触发'}")
        print(f"  高点止损:  ¥{stop_hwm:.3f}  {'✅未触发' if p20_159837>stop_hwm else '❌已触发'}  (当前高点回撤:{hwm_ret:.1f}%)")
        # MA21检查
        # 用本地周线数据
        hist_file = r'D:\Qclaw_Trading\data\history_long_v2\sz159837.json'
        if os.path.exists(hist_file):
            with open(hist_file, encoding='utf-8') as f:
                dd = json.loads(f.read().replace('NaN','null'))
            recs = dd.get('records',[]) if isinstance(dd,dict) else dd
            weeks={}
            for r in recs:
                ds=r.get('date','')
                if not ds: continue
                y,wn,_=datetime.datetime.strptime(ds,'%Y-%m-%d').isocalendar()
                wk=f'{y}-W{wn:02d}'
                if wk not in weeks or ds>weeks[wk][0]:
                    weeks[wk]=(ds,r.get('close',0))
            sr=sorted(weeks.items())
            # 截至07-17的ma21
            for i,(wk,v) in enumerate(sr):
                if v[0]=='2026-07-17':
                    ma21_local = sum(sr[j][1][1] for j in range(max(0,i-20),i+1))/min(21,i+1)
                    print(f"  MA21(07-17周线):  ¥{ma21_local:.4f}  {'✅价格>MA21' if p20_159837>ma21_local else '❌价格<MA21'}")
                    break

# 3. 策略信号更新
print("\n【三、策略信号（v4.8，基于07-17周线已确认）】")
# 重新跑本地扫描
HIST = r"D:\Qclaw_Trading\data\history_long_v2"
POOL = r"D:\Qclaw_Trading\data\etf_pool_V1_full.json"
import glob as g
with open(POOL, encoding='utf-8') as f:
    d = json.loads(f.read())
etfs = d if isinstance(d,list) else d.get('data',[])
series2, ohlc2, cats2 = {}, {}, {}
for e in etfs:
    code=e['code']; cat=e.get('category','') or ''
    cats2[code]=cat
    path=os.path.join(HIST,code+'.json')
    if not os.path.exists(path):
        m=g.glob(os.path.join(HIST,'*'+code+'.json'))
        if not m: continue
        path=m[0]
    try:
        with open(path, encoding='utf-8') as f:
            recs=json.loads(f.read().replace('NaN','null'))
            recs=recs.get('records',[]) if isinstance(recs,dict) else recs
    except: continue
    if not recs: continue
    wm={}
    for r in recs:
        ds=r.get('date',''); 
        if not ds: continue
        try:
            y,wn=datetime.datetime.strptime(ds,'%Y-%m-%d').isocalendar()[:2]
            wk=f'{y}-W{wn:02d}'
            if wk not in wm or ds>wm[wk][0]: wm[wk]=(ds,r.get('close',0))
        except: pass
    if not wm: continue
    sr=sorted(wm.items())
    series2[code]=[(wk,v[1]) for wk,v in sr]

# 最新周
all_wk2=sorted(set(wk for s in series2.values() for wk,_ in s))
END='2026-W29'  # 07-17那周

# 找159837和560080
for code,name in [('159837','生物科技ETF'),('560080','中药ETF')]:
    s=series2.get(code,[])
    if not s: print(f'{code} 无本地数据'); continue
    idx=next((i for i,(wk,_) in enumerate(s) if wk==END), None)
    if idx is None: idx=len(s)-1
    price=s[idx][1]
    ma21=sum(s[j][1] for j in range(max(0,idx-20),idx+1))/min(21,idx+1)
    mom=price/s[idx-3][1]-1 if idx>=3 else 0
    dev=abs(price/ma21-1)*100
    signal='✅候选' if price>ma21 and dev<=30 else '❌淘汰'
    print(f'  {code} {name}: 现价={price:.3f} MA21={ma21:.4f} dev={dev:.1f}% mom3={mom*100:+.1f}% → {signal}')
