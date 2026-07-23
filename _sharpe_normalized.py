#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核心问题：ATR加权后的equity曲线，夏普比是否虚胖？
思路：用同一套交易信号，分别用ATR仓位和等权仓位计算equity，
      然后看夏普比是否有显著差异。
如果ATR加权夏普 >> 等权夏普 → 夏普是仓位放大的，不是策略本身的风险调整
"""
import os, json, glob, statistics
from datetime import datetime as dt

HIST = r"D:\Qclaw_Trading\data\history_long_v2"
POOL = r"D:\Qclaw_Trading\data\etf_pool_V1_full.json"
TOP_N=1; LB=3; ATR_F=0.85; DEV=20.0; W1=W3=0.50; W8=0.00; CAP=100000.0

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

def find_idx(w):
    return next((i for i,ww in enumerate(all_wk) if ww==w), None)

is0 = max(0, (find_idx("2017-W01") or 0) - 1)
is1 = find_idx("2023-W01")

fi = {c: next((j for j,(wk,_) in enumerate(s) if wk==all_wk[is0]), None) for c,s in series.items()}

def sim_oos(weighting="atr"):
    """模拟OOS阶段，同时生成ATR仓位和等权仓位的equity"""
    port = {}; cash = CAP; nb = 0
    eq_atr = []; eq_eq = []
    
    for si in range(is1, len(all_wk)-1):
        sw = all_wk[si]; ew = all_wk[si+1]; yr = int(ew.split("-W")[0])
        cands = []
        for code, s in series.items():
            fi0 = fi.get(code)
            if fi0 is None: continue
            idx_ = fi0 + (si - is0)
            if idx_ < 21 or idx_ >= len(s): continue
            o = ohlc.get(code, {}); sr = series.get(code, [])
            price = sr[idx_][1]
            if not price or price <= 0: continue
            ma5  = sum(sr[j][1] for j in range(idx_-4,idx_+1)) / 5
            ma21 = sum(sr[j][1] for j in range(idx_-20,idx_+1)) / 21
            if ma21 == 0: continue
            dev = abs(price/ma21 - 1) * 100
            if dev > DEV: continue
            if price <= ma21: continue
            ar = atr.get(code,{}).get(sr[idx_][0])
            if ar is not None and ar < ATR_F: continue
            mom   = price / sr[idx_-LB][1] - 1
            mom1w = price / sr[idx_-1][1] - 1 if idx_>=1 else mom
            mom8w = price / sr[idx_-8][1] - 1 if idx_>=8 else mom
            score = W1*mom1w + W3*mom + W8*mom8w
            w0 = o.get(sr[idx_][0],{})
            vr = 1.0
            if w0 and all(w0.get(k) for k in ("c","o","h","l")):
                vv = [o.get(cwkl[code][j],{}).get("v",0) for j in range(max(0,idx_-9),idx_+1)]
                vv = [v for v in vv if v]
                avg10 = sum(vv)/len(vv) if vv else 1
                vr = w0.get("v",0)/avg10 if avg10>0 else 1
            if vr > 1.5: continue
            atr_v = max(atr.get(code,{}).get(sr[idx_][0], 1.0), 0.3)
            cands.append({"code":code,"_adj":score,"cat":cats.get(code,""),"atr":atr_v})

        cands.sort(key=lambda x: x["_adj"], reverse=True)
        used = set(); tgt = []
        for c in cands:
            if c["cat"] not in used: used.add(c["cat"]); tgt.append(c)
        tgt = tgt[:TOP_N]; tcodes = {t["code"] for t in tgt}

        # 高水位更新
        for code, pos in list(port.items()):
            p = next((cl for wk,cl in series[code] if wk==sw), None)
            if p and p>port[code]["hwm"]: port[code]["hwm"] = p

        # 止损
        sell = []
        for code, pos in list(port.items()):
            p = next((cl for wk,cl in series[code] if wk==sw), None)
            if p is None: sell.append(code)
            else:
                cp = p/pos["buy_price"]-1; hp = p/pos["hwm"]-1
                if cp<=-0.08 or hp<=-0.10: sell.append(code)
                elif code not in tcodes: sell.append(code)
        for code in sell:
            pos = port.pop(code)
            p = next((cl for wk,cl in series[code] if wk==sw), None)
            cash += pos["weight"]*(p or pos["buy_price"])

        slots = TOP_N - len(port)
        if slots > 0 and cash > 0:
            bl = [t for t in tgt if t["code"] not in port]
            ta = cash + sum(p2["weight"]*p2["buy_price"] for p2 in port.values())
            
            # ATR仓位
            bws_atr = []
            for bc in bl[:slots]:
                px = next((cl for wk,cl in series[bc["code"]] if wk==sw), None)
                if not px or px<=0: continue
                wa = max(atr.get(bc["code"],{}).get(sw,1), 0.3)
                bws_atr.append((bc["code"], px, wa))
            if bws_atr:
                tw_a = sum(w for _,_,w in bws_atr)
                for code,px,wa in bws_atr:
                    sv = ta*(wa/tw_a); wt = sv/px
                    if wt*px > cash*0.98: wt = cash*0.98/px
                    if wt<=0: continue
                    cash -= wt*px
                    port[code] = {"weight":wt,"buy_price":px,"hwm":px,"atr_wa":wa}; nb += 1

        # 计算equity
        eq_a = cash + sum(
            p2["weight"]*next((cl for wk,cl in series[c] if wk==ew), p2["buy_price"])
            for c,p2 in port.items())
        eq_atr.append((ew, eq_a, yr))

    # 等权版本：用相同的交易信号，但等权计算
    port2 = {}; cash2 = CAP
    eq_eq = []
    
    for si in range(is1, len(all_wk)-1):
        sw = all_wk[si]; ew = all_wk[si+1]; yr = int(ew.split("-W")[0])
        cands = []
        for code, s in series.items():
            fi0 = fi.get(code)
            if fi0 is None: continue
            idx_ = fi0 + (si - is0)
            if idx_ < 21 or idx_ >= len(s): continue
            o = ohlc.get(code, {}); sr = series.get(code, [])
            price = sr[idx_][1]
            if not price or price <= 0: continue
            ma5  = sum(sr[j][1] for j in range(idx_-4,idx_+1)) / 5
            ma21 = sum(sr[j][1] for j in range(idx_-20,idx_+1)) / 21
            if ma21 == 0: continue
            dev = abs(price/ma21 - 1) * 100
            if dev > DEV: continue
            if price <= ma21: continue
            ar = atr.get(code,{}).get(sr[idx_][0])
            if ar is not None and ar < ATR_F: continue
            mom   = price / sr[idx_-LB][1] - 1
            mom1w = price / sr[idx_-1][1] - 1 if idx_>=1 else mom
            mom8w = price / sr[idx_-8][1] - 1 if idx_>=8 else mom
            score = W1*mom1w + W3*mom + W8*mom8w
            w0 = o.get(sr[idx_][0],{})
            vr = 1.0
            if w0 and all(w0.get(k) for k in ("c","o","h","l")):
                vv = [o.get(cwkl[code][j],{}).get("v",0) for j in range(max(0,idx_-9),idx_+1)]
                vv = [v for v in vv if v]
                avg10 = sum(vv)/len(vv) if vv else 1
                vr = w0.get("v",0)/avg10 if avg10>0 else 1
            if vr > 1.5: continue
            cands.append({"code":code,"_adj":score,"cat":cats.get(code,"")})

        cands.sort(key=lambda x: x["_adj"], reverse=True)
        used = set(); tgt = []
        for c in cands:
            if c["cat"] not in used: used.add(c["cat"]); tgt.append(c)
        tgt = tgt[:TOP_N]; tcodes = {t["code"] for t in tgt}

        for code, pos in list(port2.items()):
            p = next((cl for wk,cl in series[code] if wk==sw), None)
            if p and p>port2[code]["hwm"]: port2[code]["hwm"] = p

        sell = []
        for code, pos in list(port2.items()):
            p = next((cl for wk,cl in series[code] if wk==sw), None)
            if p is None: sell.append(code)
            else:
                cp = p/pos["buy_price"]-1; hp = p/pos["hwm"]-1
                if cp<=-0.08 or hp<=-0.10: sell.append(code)
                elif code not in tcodes: sell.append(code)
        for code in sell:
            pos = port2.pop(code)
            p = next((cl for wk,cl in series[code] if wk==sw), None)
            cash2 += pos["weight"]*(p or pos["buy_price"])

        slots = TOP_N - len(port2)
        if slots > 0 and cash2 > 0:
            bl = [t for t in tgt if t["code"] not in port2]
            ta2 = cash2 + sum(p2["weight"]*p2["buy_price"] for p2 in port2.values())
            bws_eq = []
            for bc in bl[:slots]:
                px = next((cl for wk,cl in series[bc["code"]] if wk==sw), None)
                if not px or px<=0: continue
                bws_eq.append((bc["code"], px, 1.0))  # 等权
            if bws_eq:
                tw_e = sum(w for _,_,w in bws_eq)
                for code,px,wa in bws_eq:
                    sv = ta2*(wa/tw_e); wt = sv/px
                    if wt*px > cash2*0.98: wt = cash2*0.98/px
                    if wt<=0: continue
                    cash2 -= wt*px
                    port2[code] = {"weight":wt,"buy_price":px,"hwm":px}

        eq_e = cash2 + sum(
            p2["weight"]*next((cl for wk,cl in series[c] if wk==ew), p2["buy_price"])
            for c,p2 in port2.items())
        eq_eq.append((ew, eq_e, yr))

    return eq_atr, eq_eq

def stats(eq_ts):
    eqs = [e[1] for e in eq_ts]; n = len(eqs)
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
    return {
        "ann": ann, "max_dd": mdd*100, "sharpe": shp,
        "ann_vol": sw*52**0.5*100,
        "final": final, "init": init,
        "n": n, "win_rate": sum(1 for r in wr if r>0)/len(wr)*100 if wr else 0
    }

print("=== 同一信号，ATR仓位 vs 等权仓位 → 夏普比对比 ===\n")
eq_atr, eq_eq = sim_oos()
st_a = stats(eq_atr)
st_e = stats(eq_eq)

print("仓位模式  {:>10s}  {:>8s}  {:>8s}  {:>8s}  {:>8s}".format(
    "年化收益", "波动率", "夏普比", "最大回撤", "初始→最终"))
print("-"*65)
print("{:12s} {:>+10.1f}%  {:>7.1f}%  {:>8.3f}  {:>7.1f}%  {:.0f}→{:.0f}".format(
    "ATR仓位", st_a["ann"], st_a["ann_vol"], st_a["sharpe"],
    abs(st_a["max_dd"]), st_a["init"], st_a["final"]))
print("{:12s} {:>+10.1f}%  {:>7.1f}%  {:>8.3f}  {:>7.1f}%  {:.0f}→{:.0f}".format(
    "等权仓位", st_e["ann"], st_e["ann_vol"], st_e["sharpe"],
    abs(st_e["max_dd"]), st_e["init"], st_e["final"]))

# 关键比率
print("\n=== 关键分析 ===")
print("ATR vs 等权 年化差异: {:+.1f}pp".format(st_a["ann"] - st_e["ann"]))
print("ATR vs 等权 波动率差异: {:+.1f}%".format(st_a["ann_vol"] - st_e["ann_vol"]))
print("ATR vs 等权 夏普比差异: {:.3f}".format(st_a["sharpe"] - st_e["sharpe"]))
print("")
print("结论判断:")
if st_a["sharpe"] > st_e["sharpe"] * 1.1:
    print("  ATR夏普 > 等权夏普 → 仓位放大收益同时放大了波动，但超额收益超出波动增幅")
    print("  → 夏普有部分来自策略本身的选股能力，非纯杠杆效应")
elif abs(st_a["sharpe"] - st_e["sharpe"]) < 0.05:
    print("  ATR夏普 ≈ 等权夏普 → 仓位变化对风险调整收益无显著影响")
    print("  → 夏普反映的是策略本身的选股能力，与仓位无关")
else:
    print("  ATR夏普 < 等权夏普 → ATR加权反而降低了风险调整收益")
    print("  → 高ATR仓位放大了下行波动，超额收益不够补偿额外风险")
