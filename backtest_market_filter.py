#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.8 + 宽基趋势过滤回测
过滤规则：当宽基指数(沪深300/中证500)周线close < 自身MA21时，空仓（不持有任何ETF）
对比：v4.8原版 vs v4.8+各宽基过滤
"""
import sys, os, json, glob, statistics
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime as dt

HIST  = r"D:\Qclaw_Trading\data\history_long_v2"
POOL  = r"D:\Qclaw_Trading\data\etf_pool_V1_full.json"
TOP_N = 1; LB = 3; ATR_F = 0.85; CAP = 100000.0
W1, W3, W8 = 0.50, 0.50, 0.00
MAX_DEV = 30.0

BENCH = {'hs300':'510300', 'zz500':'510500'}

def load_series(code):
    path = os.path.join(HIST, code + ".json")
    if not os.path.exists(path):
        m = glob.glob(os.path.join(HIST, "*"+code+".json"))
        if not m: return None, None, None
        path = m[0]
    try:
        with open(path, encoding="utf-8") as f:
            recs = json.loads(f.read().replace("NaN","null"))
            recs = recs.get("records",[]) if isinstance(recs,dict) else recs
    except: return None, None, None
    if not recs: return None, None, None
    wm = {}
    for r in recs:
        ds = r.get("date","") or r.get("w","")
        if not ds: continue
        try:
            y,wn = dt.strptime(ds,"%Y-%m-%d").isocalendar()[:2]
            wk = f"{y}-W{wn:02d}"
            c=r.get("close",0);o=r.get("open",0);h=r.get("high",0);l=r.get("low",0);v=r.get("vol",0)
            if wk not in wm or ds > wm[wk][0]: wm[wk]=(ds,c,o,h,l,v)
        except: pass
    if not wm: return None, None, None
    sr = sorted(wm.items())
    series = [(wk, v[1]) for wk, v in sr]
    ohlc = {wk:{"o":v[2],"h":v[3],"l":v[4],"c":v[1],"v":v[5]} for wk, v in sr}
    return series, ohlc, {wk:v[0] for wk,v in sr}

# 加载池
with open(POOL, encoding="utf-8") as f:
    d = json.loads(f.read())
etfs = d if isinstance(d, list) else d.get("data", [])
series, ohlc, cats = {}, {}, {}
for e in etfs:
    code = e["code"]; cat = e.get("category","") or ""
    cats[code] = cat
    s, o, _ = load_series(code)
    if s: series[code], ohlc[code] = s, o

# 加载宽基
bench_series = {}
for key, code in BENCH.items():
    s, o, _ = load_series(code)
    if s: bench_series[key] = s

all_wk = sorted(set(wk for s in series.values() for wk,_ in s))
for bs in bench_series.values():
    all_wk = sorted(set(all_wk) | set(wk for wk,_ in bs))
all_wk = sorted(all_wk)

# ATR
atr = {}
for code, wd in ohlc.items():
    if len(wd) < 30: continue
    wkl = sorted(wd.keys()); trs=[None]*len(wkl)
    for i in range(1,len(wkl)):
        c,p = wd[wkl[i]], wd[wkl[i-1]]
        trs[i]=max(c["h"]-c["l"], abs(c["h"]-p["c"]), abs(c["l"]-p["c"]))
    atrs={}
    for i in range(21,len(wkl)):
        vs=[trs[j] for j in range(i-20,i+1) if trs[j] is not None]
        if len(vs)>=21:
            f14=sum(vs[-14:])/14; s21=sum(vs)/21
            if s21>0: atrs[wkl[i]]=f14/s21
    atr[code]=atrs

cwkl = {c:[wk for wk,_ in s] for c,s in series.items()}
def find_idx(w): return next((i for i,ww in enumerate(all_wk) if ww==w), None)
is0 = max(0, (find_idx("2017-W01") or 0) - 1)
is1 = find_idx("2023-W01")
fi = {c: next((j for j,(wk,_) in enumerate(s) if wk==all_wk[is0]), None) for c,s in series.items()}

# 宽基索引
bench_fi = {}
for key, bs in bench_series.items():
    bench_fi[key] = {wk: i for i,(wk,_) in enumerate(bs)}

def bench_bear(key, sw):
    """判断宽基在sw周是否走熊(close<MA21)"""
    bs = bench_series[key]
    if sw not in bench_fi[key]: return False
    idx = bench_fi[key][sw]
    if idx < 21: return False
    ma21 = sum(bs[j][1] for j in range(idx-20,idx+1))/21
    price = bs[idx][1]
    return price < ma21

def sim(market_filter):
    """market_filter: 'none' | 'hs300' | 'zz500' | 'any'"""
    port = {}; cash = CAP; nb = 0; n_sell_bear = 0
    eq_ts = []; bear_weeks = 0; total_weeks = 0
    
    for si in range(is1, len(all_wk)-1):
        sw = all_wk[si]; ew = all_wk[si+1]
        total_weeks += 1
        
        # 环境判断
        bear = False
        if market_filter == 'hs300': bear = bench_bear('hs300', sw)
        elif market_filter == 'zz500': bear = bench_bear('zz500', sw)
        elif market_filter == 'any':
            bear = bench_bear('hs300', sw) or bench_bear('zz500', sw)
        if bear: bear_weeks += 1
        
        # 候选筛选
        cands = []
        for code, s in series.items():
            fi0 = fi.get(code)
            if fi0 is None: continue
            idx_ = fi0 + (si - is0)
            if idx_ < 21 or idx_ >= len(s): continue
            o = ohlc.get(code, {}); sr = series.get(code, [])
            price = sr[idx_][1]
            if not price or price <= 0: continue
            ma21 = sum(sr[j][1] for j in range(idx_-20,idx_+1))/21
            if ma21 == 0: continue
            dev = abs(price/ma21 - 1) * 100
            if dev > MAX_DEV: continue
            if price <= ma21: continue
            ar = atr.get(code,{}).get(sr[idx_][0])
            if ar is not None and ar < ATR_F: continue
            mom = price/sr[idx_-LB][1]-1
            mom1w = price/sr[idx_-1][1]-1 if idx_>=1 else mom
            score = W1*mom1w + W3*mom
            w0 = o.get(sr[idx_][0],{})
            vr = 1.0
            if w0 and all(w0.get(k) for k in ("c","o","h","l")):
                vv=[o.get(cwkl[code][j],{}).get("v",0) for j in range(max(0,idx_-9),idx_+1)]
                vv=[v for v in vv if v]
                avg10=sum(vv)/len(vv) if vv else 1
                vr=w0.get("v",0)/avg10 if avg10>0 else 1
            if vr > 1.5: continue
            cands.append({"code":code,"score":score,"cat":cats.get(code,"")})
        
        cands.sort(key=lambda x: x["score"], reverse=True)
        used=set(); tgt=[]
        for c in cands:
            if c["cat"] not in used: used.add(c["cat"]); tgt.append(c)
        tgt = tgt[:TOP_N]; tcodes = {t["code"] for t in tgt}
        
        # 更新hwm
        for code, pos in list(port.items()):
            p = next((cl for wk,cl in series[code] if wk==sw), None)
            if p and p>port[code]["hwm"]: port[code]["hwm"] = p
        
        # 卖出逻辑
        sell = []
        if bear:
            # 环境走熊，清仓
            sell = list(port.keys())
            n_sell_bear += len(sell)
        else:
            for code, pos in list(port.items()):
                p = next((cl for wk,cl in series[code] if wk==sw), None)
                if p is None: sell.append(code)
                else:
                    cp = p/pos["buy_price"]-1; hp = p/pos["hwm"]-1
                    if cp<=-0.08 or hp<=-0.10 or code not in tcodes:
                        sell.append(code)
        
        for code in sell:
            pos = port.pop(code)
            p = next((cl for wk,cl in series[code] if wk==sw), None)
            cash += pos["weight"]*(p or pos["buy_price"])
        
        # 买入逻辑
        if not bear and (TOP_N - len(port)) > 0 and cash > 0:
            bl = [t for t in tgt if t["code"] not in port]
            ta = cash + sum(p2["weight"]*p2["buy_price"] for p2 in port.values())
            bws = []
            for bc in bl[:TOP_N-len(port)]:
                px = next((cl for wk,cl in series[bc["code"]] if wk==sw), None)
                if not px or px<=0: continue
                wa = max(atr.get(bc["code"],{}).get(sw,1), 0.3)
                bws.append((bc["code"], px, wa))
            if bws:
                tw = sum(w for _,_,w in bws)
                for code,px,wa in bws:
                    sv = ta*(wa/tw); wt = sv/px
                    if wt*px > cash*0.98: wt = cash*0.98/px
                    if wt<=0: continue
                    cash -= wt*px
                    port[code] = {"weight":wt,"buy_price":px,"hwm":px}; nb += 1
        
        eq = cash + sum(
            p2["weight"]*next((cl for wk,cl in series[c] if wk==ew), p2["buy_price"])
            for c,p2 in port.items())
        eq_ts.append(eq)
    
    return eq_ts, nb, bear_weeks, total_weeks

def stats(eq_ts):
    eqs = eq_ts; n = len(eqs)
    if n < 2: return None
    init,final = eqs[0],eqs[-1]; yrs = n/52
    ann = ((final/init)**(1/yrs)-1)*100 if yrs>0 else 0
    peak=eqs[0]; mdd=0
    for eq in eqs:
        if eq>peak: peak=eq
        dd=eq/peak-1
        if dd<mdd: mdd=dd
    wr=[eqs[i]/eqs[i-1]-1 for i in range(1,n) if eqs[i-1]>0]
    aw=statistics.mean(wr) if wr else 0
    sw=statistics.stdev(wr) if len(wr)>1 else 1e-9
    shp=(aw*52-0.02)/(sw*52**0.5) if sw>0 else 0
    return {"ann":ann,"max_dd":mdd*100,"sharpe":shp,"final":final}

print("="*78)
print("  v4.8 + 宽基趋势过滤回测  |  OOS 2023-2026")
print("  过滤规则: 宽基周线close < 自身MA21 → 空仓")
print("="*78)

results = []
for mf in ['none', 'hs300', 'zz500', 'any']:
    eq_ts, nb, bw, tw = sim(mf)
    st = stats(eq_ts)
    label = {'none':'v4.8原版(无过滤)','hs300':'+沪深300过滤','zz500':'+中证500过滤','any':'+任一走熊空仓'}[mf]
    results.append((label, st, nb, bw, tw))
    print(f"\n{label}:")
    print(f"  年化={st['ann']:+.1f}%  Sharpe={st['sharpe']:.3f}  MaxDD={abs(st['max_dd']):.1f}%  "
          f"交易={nb}  空仓周={bw}/{tw}({bw/tw*100:.0f}%)  净值={st['final']:.0f}")

print("\n" + "="*78)
print("  对比汇总")
print("="*78)
base = results[0][1]
print(f"{'方案':<18}{'年化':>9}{'Sharpe':>9}{'MaxDD':>9}{'交易':>6}{'空仓%':>8}{'净值':>11}")
for label, st, nb, bw, tw in results:
    print(f"{label:<18}{st['ann']:>+8.1f}%{st['sharpe']:>9.3f}{abs(st['max_dd']):>8.1f}%{nb:>6}{bw/tw*100:>7.0f}%{st['final']:>11.0f}")

# 保存
import datetime as dt2
out = {
    "test": "v4.8 + market breadth filter",
    "period": "OOS 2023-2026",
    "results": [{"label":l,"ann":st['ann'],"sharpe":st['sharpe'],"max_dd":st['max_dd'],
                 "trades":nb,"bear_weeks":bw,"total_weeks":tw,"final":st['final']} for l,st,nb,bw,tw in results]
}
with open(r"D:\Qclaw_Trading\review\market_filter_test_20260717.json","w",encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"\n已保存: D:\\Qclaw_Trading\\review\\market_filter_test_20260717.json")
