#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网格搜索：寻找最优偏离度上限和ATR过滤组合
"""
import os, json, glob, statistics
from datetime import datetime as dt

HIST  = r"D:\Qclaw_Trading\data\history_long_v2"
POOL  = r"D:\Qclaw_Trading\data\etf_pool_V1_full.json"
TOP_N = 1; LB = 3; ATR_F = 0.85; CAP = 100000.0
W1, W3, W8 = 0.50, 0.50, 0.00

# 网格参数
DEV_RANGE = [15, 18, 20, 22, 25, 28, 30]
ATR_RANGE = [None, 1.8, 1.5, 1.3, 1.0]

# 加载数据
with open(POOL, encoding="utf-8") as f:
    d = json.loads(f.read())
etfs = d if isinstance(d, list) else d.get("data", [])
series, ohlc, cats, weeks = {}, {}, {}, set()
for e in etfs:
    code = e["code"]; cat = e.get("category","") or ""
    cats[code] = cat
    path = os.path.join(HIST, code + ".json")
    if not os.path.exists(path):
        m = glob.glob(os.path.join(HIST, "*" + code + ".json"))
        if not m: continue
        path = m[0]
    try:
        with open(path, encoding="utf-8") as f:
            recs = json.loads(f.read().replace("NaN","null"))
            recs = recs.get("records",[]) if isinstance(recs,dict) else recs
    except: continue
    if not recs: continue
    wm = {}
    for r in recs:
        ds = r.get("date","") or r.get("w","")
        if not ds: continue
        try:
            y,wn = dt.strptime(ds,"%Y-%m-%d").isocalendar()[:2]
            wk = "{}-W{:02d}".format(y, wn)
            c=r.get("close",0); o=r.get("open",0); h=r.get("high",0); l=r.get("low",0); v=r.get("vol",0)
            if wk not in wm or ds > wm[wk][0]: wm[wk] = (ds,c,o,h,l,v)
        except: pass
    if not wm: continue
    sr = sorted(wm.items())
    series[code] = [(wk, v[1]) for wk, v in sr]
    ohlc[code]   = {wk:{"o":v[2],"h":v[3],"l":v[4],"c":v[1],"v":v[5]} for wk, v in sr}
    weeks.update(w for w,_ in sr)
all_wk = sorted(weeks)

atr = {}
for code, wd in ohlc.items():
    if len(wd) < 30: continue
    wkl = sorted(wd.keys()); trs = [None]*len(wkl)
    for i in range(1,len(wkl)):
        c,p = wd[wkl[i]], wd[wkl[i-1]]
        trs[i] = max(c["h"]-c["l"], abs(c["h"]-p["c"]), abs(c["l"]-p["c"]))
    atrs = {}
    for i in range(21, len(wkl)):
        vs = [trs[j] for j in range(i-20,i+1) if trs[j] is not None]
        if len(vs) >= 21:
            f14=sum(vs[-14:])/14; s21=sum(vs)/21
            if s21>0: atrs[wkl[i]] = f14/s21
    atr[code] = atrs

cwkl = {c:[wk for wk,_ in s] for c,s in series.items()}
fi = {c: next((j for j,(wk,_) in enumerate(s) if wk==all_wk[0]), None) for c,s in series.items()}
def find_idx(w): return next((i for i,ww in enumerate(all_wk) if ww==w), None)
is0 = max(0, (find_idx("2017-W01") or 0) - 1)
is1 = find_idx("2023-W01")
fi = {c: next((j for j,(wk,_) in enumerate(s) if wk==all_wk[is0]), None) for c,s in series.items()}

def sim(max_dev, max_atr):
    port = {}; cash = CAP; nb = 0
    eq_ts = []
    
    for si in range(is1, len(all_wk)-1):
        sw = all_wk[si]; ew = all_wk[si+1]
        
        cands = []
        for code, s in series.items():
            fi0 = fi.get(code)
            if fi0 is None: continue
            idx_ = fi0 + (si - is0)
            if idx_ < 21 or idx_ >= len(s): continue
            o = ohlc.get(code, {}); sr = series.get(code, [])
            price = sr[idx_][1]
            if not price or price <= 0: continue
            
            ma21 = sum(sr[j][1] for j in range(idx_-20,idx_+1)) / 21
            if ma21 == 0: continue
            
            dev = abs(price/ma21 - 1) * 100
            if dev > max_dev: continue
            if price <= ma21: continue
            
            ar = atr.get(code,{}).get(sr[idx_][0])
            if ar is not None and ar < ATR_F: continue
            
            atr_val = max(atr.get(code,{}).get(sr[idx_][0], 1.0), 0.3)
            if max_atr and atr_val > max_atr: continue
            
            mom = price / sr[idx_-LB][1] - 1
            mom1w = price / sr[idx_-1][1] - 1 if idx_>=1 else mom
            score = W1*mom1w + W3*mom
            
            w0 = o.get(sr[idx_][0],{})
            vr = 1.0
            if w0 and all(w0.get(k) for k in ("c","o","h","l")):
                vv = [o.get(cwkl[code][j],{}).get("v",0) for j in range(max(0,idx_-9),idx_+1)]
                vv = [v for v in vv if v]
                avg10 = sum(vv)/len(vv) if vv else 1
                vr = w0.get("v",0)/avg10 if avg10>0 else 1
            if vr > 1.5: continue
            
            cands.append({"code":code,"score":score,"cat":cats.get(code,"")})
        
        cands.sort(key=lambda x: x["score"], reverse=True)
        used = set(); tgt = []
        for c in cands:
            if c["cat"] not in used: used.add(c["cat"]); tgt.append(c)
        tgt = tgt[:TOP_N]; tcodes = {t["code"] for t in tgt}
        
        for code, pos in list(port.items()):
            p = next((cl for wk,cl in series[code] if wk==sw), None)
            if p and p>port[code]["hwm"]: port[code]["hwm"] = p
        
        sell = []
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
        
        slots = TOP_N - len(port)
        if slots > 0 and cash > 0:
            bl = [t for t in tgt if t["code"] not in port]
            ta = cash + sum(p2["weight"]*p2["buy_price"] for p2 in port.values())
            bws = []
            for bc in bl[:slots]:
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
    
    return eq_ts, nb

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
    return {"ann":ann,"max_dd":mdd*100,"sharpe":shp}

# 网格搜索
print("="*90)
print("  网格搜索：偏离度上限 × ATR过滤")
print("="*90)

grid_results = []
for dev in DEV_RANGE:
    for atr_max in ATR_RANGE:
        eq_ts, nb = sim(dev, atr_max)
        st = stats(eq_ts)
        if st:
            grid_results.append({
                "dev": dev, "atr": atr_max, "stats": st, "trades": nb
            })

# 结果表格
print("\n偏离度  ATR上限   年化收益   Sharpe   最大回撤   交易")
print("-"*70)
for r in grid_results:
    atr_str = str(r["atr"]) if r["atr"] else "无"
    print(f"  {r['dev']:2d}%    {atr_str:>6s}   {r['stats']['ann']:+7.1f}%   {r['stats']['sharpe']:.3f}   {abs(r['stats']['max_dd']):6.1f}%   {r['trades']:3d}")

# 最优组合
best = max(grid_results, key=lambda x: x["stats"]["sharpe"])
print("\n" + "="*90)
print("  最优参数组合")
print("="*90)
print(f"  偏离度上限: {best['dev']}%")
print(f"  ATR上限: {best['atr'] if best['atr'] else '无限制'}")
print(f"  年化收益: {best['stats']['ann']:+.1f}%")
print(f"  Sharpe: {best['stats']['sharpe']:.3f}")
print(f"  最大回撤: {abs(best['stats']['max_dd']):.1f}%")
print(f"  交易次数: {best['trades']}")

# 对比v4.7基准
baseline = next((r for r in grid_results if r["dev"]==20 and r["atr"] is None), None)
if baseline and best["dev"] != 20:
    print("\n" + "="*90)
    print("  vs v4.7基准 (dev=20%, ATR=无限制)")
    print("="*90)
    ann_diff = best["stats"]["ann"] - baseline["stats"]["ann"]
    shp_diff = best["stats"]["sharpe"] - baseline["stats"]["sharpe"]
    print(f"  年化收益: {best['stats']['ann']:+.1f}% vs {baseline['stats']['ann']:+.1f}% ({ann_diff:+.1f}pp)")
    print(f"  Sharpe: {best['stats']['sharpe']:.3f} vs {baseline['stats']['sharpe']:.3f} ({shp_diff:+.3f})")
