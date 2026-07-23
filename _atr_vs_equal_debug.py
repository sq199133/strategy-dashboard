#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATR vs 等权调试"""
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

def find_idx(w):
    return next((i for i,ww in enumerate(all_wk) if ww==w), None)

is0 = max(0, (find_idx("2017-W01") or 0) - 1)
is1 = find_idx("2023-W01")
print("IS起点: {} is0={}  OOS起点: {} is1={}".format(all_wk[is0], is0, all_wk[is1], is1))

fi = {c: next((j for j,(wk,_) in enumerate(s) if wk==all_wk[is0]), None) for c,s in series.items()}

si = is1  # 第一个OOS周
sw = all_wk[si]; ew = all_wk[si+1]
print("\n=== OOS第1周 {} 候选筛选 ===".format(sw))

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
    mom = price / sr[idx_-LB][1] - 1
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
    cands.append({"code":code,"score":score,"atr":atr_v,"price":price,"cat":cats.get(code,"")})

print("候选数量: {}".format(len(cands)))
cands.sort(key=lambda x: x["score"], reverse=True)
used = set(); tgt = []
for c in cands:
    if c["cat"] not in used: used.add(c["cat"]); tgt.append(c)
tgt = tgt[:TOP_N]

print("选中: {}只".format(len(tgt)))
for t in tgt[:3]:
    print("  code={} score={:.4f} atr={:.3f} price={:.3f}".format(
        t["code"], t["score"], t["atr"], t["price"]))

# ATR vs 等权 仓位
if tgt:
    t = tgt[0]
    atr_wa = max(atr.get(t["code"],{}).get(sw, 1.0), 0.3)
    # ATR分配
    sv_atr = CAP * (atr_wa / atr_wa)  # 只有1个ETF
    wt_atr = sv_atr / t["price"]
    # 等权分配
    sv_eq = CAP * (1.0 / 1.0)
    wt_eq = sv_eq / t["price"]
    print("\n  ATR分配: 仓位价值={:.0f} 股数={:.0f} ATR权重={:.3f}".format(sv_atr, wt_atr, atr_wa))
    print("  等权分配: 仓位价值={:.0f} 股数={:.0f} 权重=1.0".format(sv_eq, wt_eq))
    print("  股数比: ATR/等权 = {:.2f}x".format(wt_atr/wt_eq))

print("\n=== ATR值分布（全部候选）===")
if cands:
    atr_vals = [c["atr"] for c in cands]
    atr_vals.sort()
    n = len(atr_vals)
    print("ATR: min={:.3f} p25={:.3f} median={:.3f} p75={:.3f} max={:.3f}".format(
        atr_vals[0], atr_vals[n//4], atr_vals[n//2], atr_vals[3*n//4], atr_vals[-1]))
    print("ATR=1.0的比例: {:.0f}%".format(sum(1 for v in atr_vals if v<=1.0)/n*100))
    print("ATR>1.2的比例: {:.0f}%".format(sum(1 for v in atr_vals if v>1.2)/n*100))

    # 模拟top=3时，ATR vs 等权的差异
    print("\n=== top=3 ATR vs 等权 仓位差异 ===")
    tgt3 = tgt[:3]
    if len(cands) >= 3:
        cats_used2 = set(); tgt3 = []
        for c in cands:
            if c["cat"] not in cats_used2: cats_used2.add(c["cat"]); tgt3.append(c)
        tgt3 = tgt3[:3]
        bws_atr = [(t["code"], t["price"], max(atr.get(t["code"],{}).get(sw,1.0),0.3)) for t in tgt3]
        bws_eq  = [(t["code"], t["price"], 1.0) for t in tgt3]
        tw_a = sum(w for _,_,w in bws_atr)
        tw_e = sum(w for _,_,w in bws_eq)
        print("top=3 候选: {}".format([t["code"] for t in tgt3]))
        print("ATR权重: " + ", ".join("{:.3f}".format(w) for _,_,w in bws_atr))
        print("等权权重: " + ", ".join("{:.3f}".format(w) for _,_,w in bws_eq))
        for i, ((code,px,wa), (code2,px2,wa2)) in enumerate(zip(bws_atr, bws_eq)):
            sv_a = CAP*(wa/tw_a); sv_e = CAP*(wa2/tw_e)
            print("  ETF{}: ATR仓位={:.0f} 等权仓位={:.0f} 差={:+.0f}({:.1f}%)".format(
                i+1, sv_a, sv_e, sv_a-sv_e, (sv_a/sv_e-1)*100))

print("\n=== 结论 ===")
print("top=1时，ATR vs 等权无差异（因为只有一个ETF，tw=wa）")
print("→ verify_atr_effect两个结果相同是正常的")
print("→ 真正的差距是backtest_composite_stop缺少vr>1.5过滤")
