#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基于本地数据(截止07-17)的v4.8全池扫描，确认真实信号"""
import sys, os, json, glob
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime as dt

HIST = r"D:\Qclaw_Trading\data\history_long_v2"
POOL = r"D:\Qclaw_Trading\data\etf_pool_V1_full.json"
TOP_N = 1; LB = 3; ATR_F = 0.85
W1, W3, W8 = 0.50, 0.50, 0.00
MAX_DEV = 30.0

with open(POOL, encoding="utf-8") as f:
    d = json.loads(f.read())
etfs = d if isinstance(d, list) else d.get("data", [])
series, ohlc, cats = {}, {}, {}
for e in etfs:
    code = e["code"]; cat = e.get("category","") or ""
    cats[code] = cat
    path = os.path.join(HIST, code + ".json")
    if not os.path.exists(path):
        m = glob.glob(os.path.join(HIST, "*"+code+".json"))
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
            wk = f"{y}-W{wn:02d}"
            c=r.get("close",0);o=r.get("open",0);h=r.get("high",0);l=r.get("low",0);v=r.get("vol",0)
            if wk not in wm or ds > wm[wk][0]: wm[wk]=(ds,c,o,h,l,v)
        except: pass
    if not wm: continue
    sr = sorted(wm.items())
    series[code] = [(wk,v[1]) for wk,v in sr]
    ohlc[code] = {wk:{"o":v[2],"h":v[3],"l":v[4],"c":v[1],"v":v[5]} for wk,v in sr}

all_wk = sorted(set(wk for s in series.values() for wk,_ in s))
# 截至周
END = "2026-W29"

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

# 各标的最新周索引
def widx(code):
    s = series[code]
    for i,(wk,_) in enumerate(s):
        if wk==END: return i
    return len(s)-1

cands=[]
for code, s in series.items():
    idx = widx(code)
    if idx < 21 or idx >= len(s): continue
    sr = s; o = ohlc[code]
    price = sr[idx][1]
    if not price or price<=0: continue
    ma21 = sum(sr[j][1] for j in range(idx-20,idx+1))/21
    if ma21==0: continue
    dev = abs(price/ma21-1)*100
    if dev > MAX_DEV: continue
    if price <= ma21: continue   # MA21硬过滤
    ar = atr.get(code,{}).get(sr[idx][0])
    if ar is not None and ar < ATR_F: continue
    mom = price/sr[idx-LB][1]-1
    mom1w = price/sr[idx-1][1]-1 if idx>=1 else mom
    score = W1*mom1w + W3*mom
    # 量比
    w0 = o.get(sr[idx][0],{})
    vr = 1.0
    if w0 and all(w0.get(k) for k in ("c","o","h","l")):
        vv=[o.get(series[code][j][0],{}).get("v",0) for j in range(max(0,idx-9),idx+1)]
        vv=[v for v in vv if v]
        avg10=sum(vv)/len(vv) if vv else 1
        vr=w0.get("v",0)/avg10 if avg10>0 else 1
    if vr > 1.5: continue
    cands.append({"code":code,"name":cats.get(code,""),"close":price,"ma21":ma21,"dev":dev,
                  "mom":mom,"mom1w":mom1w,"score":score,"vr":vr,"cat":cats.get(code,"")})

cands.sort(key=lambda x:x["score"], reverse=True)
# 去重
used=set(); tgt=[]
for c in cands:
    if c["cat"] not in used: used.add(c["cat"]); tgt.append(c)
tgt = tgt[:TOP_N]

print(f"基于 {END} (本地数据) 合格候选数: {len(cands)}")
print(f"\nTOP{TOP_N}:")
for t in tgt:
    print(f"  {t['code']} {t['name']} close={t['close']:.3f} ma21={t['ma21']:.4f} dev={t['dev']:.1f}% "
          f"mom={t['mom']*100:+.1f}% score={t['score']*100:+.2f}% vr={t['vr']:.2f}")

# 159837是否在候选中
in_cand = any(c["code"]=="159837" for c in cands)
in_top = any(t["code"]=="159837" for t in tgt)
print(f"\n159837 是否在合格候选: {in_cand}")
print(f"159837 是否TOP1: {in_top}")
print(f"\n持仓动作: {'维持持有' if in_top else ('卖出并买入 '+ (tgt[0]['code'] if tgt else '空仓'))}")
