#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中长期动量策略回测
目标：降低短期动量权重，避免突发事件驱动的脉冲行情

方案对比：
  v4.7基准: w1=0.50, w3=0.50, w8=0.00
  方案A:    w1=0.30, w3=0.40, w8=0.30 (均衡型)
  方案B:    w1=0.20, w3=0.40, w8=0.40 (中长期偏好)
  方案C:    w1=0.10, w3=0.30, w8=0.60 (强中长期)

额外过滤：
  - MA5 > MA21 > MA60 (趋势稳定性)
  - ATR比率 < 1.5 (避免追高波动品种)
"""
import os, json, glob, statistics
from datetime import datetime as dt

HIST  = r"D:\Qclaw_Trading\data\history_long_v2"
POOL  = r"D:\Qclaw_Trading\data\etf_pool_V1_full.json"
TOP_N = 1; LB = 3; ATR_F = 0.85; DEV = 20.0; CAP = 100000.0

# 动量权重配置
CONFIGS = [
    {"name": "v4.7基准", "w1": 0.50, "w3": 0.50, "w8": 0.00, "w12": 0.00, "ma_trend": False, "atr_penal": False},
    {"name": "方案A_均衡", "w1": 0.30, "w3": 0.40, "w8": 0.30, "w12": 0.00, "ma_trend": False, "atr_penal": False},
    {"name": "方案B_中长期", "w1": 0.20, "w3": 0.40, "w8": 0.40, "w12": 0.00, "ma_trend": False, "atr_penal": False},
    {"name": "方案C_强长期", "w1": 0.10, "w3": 0.30, "w8": 0.40, "w12": 0.20, "ma_trend": False, "atr_penal": False},
    {"name": "方案D_趋势稳定", "w1": 0.20, "w3": 0.40, "w8": 0.40, "w12": 0.00, "ma_trend": True, "atr_penal": False},
    {"name": "方案E_波动惩罚", "w1": 0.20, "w3": 0.40, "w8": 0.40, "w12": 0.00, "ma_trend": False, "atr_penal": True},
    {"name": "方案F_综合", "w1": 0.20, "w3": 0.40, "w8": 0.40, "w12": 0.00, "ma_trend": True, "atr_penal": True},
]

# ---- 加载数据 ----
print("加载数据...")
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

# 计算ATR
print("计算ATR...")
atr = {}
for code, wd in ohlc.items():
    if len(wd) < 60: continue
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

def sim(cfg):
    """模拟OOS阶段"""
    w1, w3, w8, w12 = cfg["w1"], cfg["w3"], cfg["w8"], cfg["w12"]
    ma_trend = cfg["ma_trend"]
    atr_penal = cfg["atr_penal"]
    
    port = {}; cash = CAP; nb = ns = 0
    eq_ts = []
    
    for si in range(is1, len(all_wk)-1):
        sw = all_wk[si]; ew = all_wk[si+1]; yr = int(ew.split("-W")[0])
        
        # 候选筛选
        cands = []
        for code, s in series.items():
            fi0 = fi.get(code)
            if fi0 is None: continue
            idx_ = fi0 + (si - is0)
            if idx_ < 60 or idx_ >= len(s): continue  # 需要60周数据计算MA60
            o = ohlc.get(code, {}); sr = series.get(code, [])
            price = sr[idx_][1]
            if not price or price <= 0: continue
            
            # 均线
            ma5  = sum(sr[j][1] for j in range(idx_-4,idx_+1)) / 5
            ma21 = sum(sr[j][1] for j in range(idx_-20,idx_+1)) / 21
            ma60 = sum(sr[j][1] for j in range(idx_-59,idx_+1)) / 60
            if ma21 == 0 or ma60 == 0: continue
            
            # v4.7基础过滤
            dev = abs(price/ma21 - 1) * 100
            if dev > DEV: continue
            if price <= ma21: continue
            
            ar = atr.get(code,{}).get(sr[idx_][0])
            if ar is not None and ar < ATR_F: continue
            
            # 动量
            mom   = price / sr[idx_-LB][1] - 1
            mom1w = price / sr[idx_-1][1] - 1 if idx_>=1 else mom
            mom8w = price / sr[idx_-8][1] - 1 if idx_>=8 else mom
            mom12w = price / sr[idx_-12][1] - 1 if idx_>=12 else mom
            
            score = w1*mom1w + w3*mom + w8*mom8w + w12*mom12w
            
            # 趋势稳定性过滤
            if ma_trend and not (ma5 > ma21 > ma60):
                continue
            
            # 波动率惩罚
            if atr_penal:
                atr_val = max(atr.get(code,{}).get(sr[idx_][0], 1.0), 0.3)
                if atr_val > 1.5:
                    score -= 0.02 * (atr_val - 1.5)  # ATR每超0.1，扣0.002分
            
            # 量比过滤
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
        
        # 高水位
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
                if cp<=-0.08 or hp<=-0.10 or code not in tcodes:
                    sell.append(code)
        
        for code in sell:
            pos = port.pop(code)
            p = next((cl for wk,cl in series[code] if wk==sw), None)
            cash += pos["weight"]*(p or pos["buy_price"]); ns += 1
        
        # 买入
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
        eq_ts.append((ew, eq, yr))
    
    return eq_ts, nb, ns

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
    return {"ann":ann,"max_dd":mdd*100,"sharpe":shp,"final":final}

# ---- 回测 ----
print("\n" + "="*80)
print("  中长期动量策略回测 (OOS 2023-2026)")
print("="*80)
print("\n配置: w1=1周动量权重, w3=3周动量权重, w8=8周动量权重, w12=12周动量权重")
print("      ma_trend=MA5>MA21>MA60趋势过滤, atr_penal=波动率惩罚\n")

results = []
for cfg in CONFIGS:
    print(f"{cfg['name']:20s} ... ", end="", flush=True)
    eq_ts, nb, ns = sim(cfg)
    st = stats(eq_ts)
    if st:
        results.append((cfg["name"], cfg, st, nb, eq_ts))
        print(f"年化{st['ann']:+6.1f}%  Sharpe={st['sharpe']:.3f}  MaxDD={abs(st['max_dd']):5.1f}%  交易{nb:3d}")
    else:
        print("N/A")

# ---- 结果表格 ----
print("\n" + "="*80)
print("  回测结果对比")
print("="*80)
print("{:20s}  {:>8s}  {:>7s}  {:>8s}  {:>5s}  {:>6s}".format(
    "策略", "年化收益", "Sharpe", "最大回撤", "交易", "最终净值"))
print("-"*80)
for name, cfg, st, nb, _ in results:
    print("{:20s}  {:>+8.1f}%  {:>7.3f}  {:>7.1f}%  {:>5d}  {:>10.0f}".format(
        name, st["ann"], st["sharpe"], abs(st["max_dd"]), nb, st["final"]))

# ---- 找最优 ----
best = max(results, key=lambda x: x[2]["sharpe"])
print("\n" + "="*80)
print(f"  最优策略: {best[0]}")
print("="*80)
print(f"  年化收益: {best[2]['ann']:+.1f}%")
print(f"  Sharpe:   {best[2]['sharpe']:.3f}")
print(f"  最大回撤: {abs(best[2]['max_dd']):.1f}%")
print(f"  交易次数: {best[3]}")
print(f"  参数: w1={best[1]['w1']:.2f} w3={best[1]['w3']:.2f} w8={best[1]['w8']:.2f} w12={best[1]['w12']:.2f}")
print(f"        ma_trend={best[1]['ma_trend']} atr_penal={best[1]['atr_penal']}")

# ---- 保存结果 ----
out_data = {
    "configurations": [
        {"name": name, "params": cfg, "stats": st, "trades": nb}
        for name, cfg, st, nb, _ in results
    ],
    "best": {
        "name": best[0],
        "params": best[1],
        "stats": best[2],
        "trades": best[3]
    }
}
out_path = r"D:\Qclaw_Trading\review\momentum_stability_test_20260714.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out_data, f, ensure_ascii=False, indent=2)
print(f"\n结果已保存: {out_path}")
