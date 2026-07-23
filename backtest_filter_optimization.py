#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化方案回测：入场过滤、板块分散、动态仓位
目标：降低突发事件风险，提升整体稳定性
"""
import os, json, glob, statistics
from datetime import datetime as dt

HIST  = r"D:\Qclaw_Trading\data\history_long_v2"
POOL  = r"D:\Qclaw_Trading\data\etf_pool_V1_full.json"
TOP_N = 1; LB = 3; ATR_F = 0.85; CAP = 100000.0
W1, W3, W8 = 0.50, 0.50, 0.00  # v4.7动量权重

# 优化配置
CONFIGS = [
    {"name": "v4.7基准", "max_dev": 20, "max_atr": None, "sector_limit": None, "dynamic_pos": False},
    {"name": "优化A_紧偏离", "max_dev": 15, "max_atr": None, "sector_limit": None, "dynamic_pos": False},
    {"name": "优化B_宽偏离", "max_dev": 25, "max_atr": None, "sector_limit": None, "dynamic_pos": False},
    {"name": "优化C_波动过滤", "max_dev": 20, "max_atr": 1.5, "sector_limit": None, "dynamic_pos": False},
    {"name": "优化D_强波动过滤", "max_dev": 20, "max_atr": 1.3, "sector_limit": None, "dynamic_pos": False},
    {"name": "优化E_板块分散", "max_dev": 20, "max_atr": None, "sector_limit": 1, "dynamic_pos": False},
    {"name": "优化F_动态仓位", "max_dev": 20, "max_atr": None, "sector_limit": None, "dynamic_pos": True},
    {"name": "优化G_综合保守", "max_dev": 15, "max_atr": 1.5, "sector_limit": 1, "dynamic_pos": False},
    {"name": "优化H_综合激进", "max_dev": 25, "max_atr": 1.8, "sector_limit": None, "dynamic_pos": True},
]

# 加载数据
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

# ATR计算
print("计算ATR...")
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

def sim(cfg):
    max_dev = cfg["max_dev"]
    max_atr = cfg["max_atr"]
    sector_limit = cfg["sector_limit"]
    dynamic_pos = cfg["dynamic_pos"]
    
    port = {}; cash = CAP; nb = ns = 0
    eq_ts = []; rejected = {"atr":0, "dev":0, "vr":0}
    
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
            if dev > max_dev: rejected["dev"] += 1; continue
            if price <= ma21: continue
            
            ar = atr.get(code,{}).get(sr[idx_][0])
            if ar is not None and ar < ATR_F: continue
            
            # 波动率上限过滤
            atr_val = max(atr.get(code,{}).get(sr[idx_][0], 1.0), 0.3)
            if max_atr and atr_val > max_atr:
                rejected["atr"] += 1; continue
            
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
            if vr > 1.5: rejected["vr"] += 1; continue
            
            cands.append({"code":code,"score":score,"cat":cats.get(code,""),"atr":atr_val})
        
        cands.sort(key=lambda x: x["score"], reverse=True)
        
        # 板块分散
        if sector_limit:
            used_sectors = set()
            filtered = []
            for c in cands:
                if c["cat"] not in used_sectors:
                    used_sectors.add(c["cat"])
                    filtered.append(c)
            cands = filtered
        
        tgt = cands[:TOP_N]; tcodes = {t["code"] for t in tgt}
        
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
                atr_c = max(atr.get(bc["code"],{}).get(sw, 1.0), 0.3)
                
                # 动态仓位
                if dynamic_pos:
                    # ATR越高，仓位越小
                    pos_weight = max(0.5, min(1.5, 1.5 - atr_c))
                else:
                    pos_weight = 1.0
                
                bws.append((bc["code"], px, atr_c, pos_weight))
            
            if bws:
                tw = sum(w for _,_,_,w in bws)
                for code,px,atr_w,pos_w in bws:
                    sv = ta*(pos_w/tw)
                    wt = sv/px
                    if wt*px > cash*0.98: wt = cash*0.98/px
                    if wt<=0: continue
                    cash -= wt*px
                    port[code] = {"weight":wt,"buy_price":px,"hwm":px}; nb += 1
        
        eq = cash + sum(
            p2["weight"]*next((cl for wk,cl in series[c] if wk==ew), p2["buy_price"])
            for c,p2 in port.items())
        eq_ts.append((ew, eq, yr))
    
    return eq_ts, nb, ns, rejected

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

# 回测
print("\n" + "="*90)
print("  优化方案回测 (OOS 2023-2026)")
print("="*90)
print("\n参数说明:")
print("  max_dev: 偏离度上限(%)")
print("  max_atr: ATR比率上限(None=无限制)")
print("  sector_limit: 板块持仓上限(None=无限制)")
print("  dynamic_pos: 动态仓位(高ATR降仓位)\n")

results = []
for cfg in CONFIGS:
    print(f"{cfg['name']:20s} ... ", end="", flush=True)
    eq_ts, nb, ns, rej = sim(cfg)
    st = stats(eq_ts)
    if st:
        results.append((cfg["name"], cfg, st, nb, rej, eq_ts))
        print(f"年化{st['ann']:+6.1f}%  Sharpe={st['sharpe']:.3f}  MaxDD={abs(st['max_dd']):5.1f}%  交易{nb:3d}")
    else:
        print("N/A")

# 结果表格
print("\n" + "="*90)
print("  回测结果对比")
print("="*90)
print("{:20s}  {:>8s}  {:>7s}  {:>8s}  {:>5s}  {:>6s}".format(
    "策略", "年化收益", "Sharpe", "最大回撤", "交易", "最终净值"))
print("-"*90)
for name, cfg, st, nb, rej, _ in results:
    print("{:20s}  {:>+8.1f}%  {:>7.3f}  {:>7.1f}%  {:>5d}  {:>10.0f}".format(
        name, st["ann"], st["sharpe"], abs(st["max_dd"]), nb, st["final"]))

# 过滤统计
print("\n" + "="*90)
print("  过滤统计 (累计被过滤次数)")
print("="*90)
for name, cfg, st, nb, rej, _ in results:
    print("{:20s}  偏离度:{:>5d}  ATR:{:>5d}  量比:{:>5d}".format(
        name, rej["dev"], rej["atr"], rej["vr"]))

# 最优策略
best = max(results, key=lambda x: x[2]["sharpe"])
print("\n" + "="*90)
print(f"  最优策略: {best[0]}")
print("="*90)
print(f"  年化收益: {best[2]['ann']:+.1f}%")
print(f"  Sharpe:   {best[2]['sharpe']:.3f}")
print(f"  最大回撤: {abs(best[2]['max_dd']):.1f}%")
print(f"  参数: max_dev={best[1]['max_dev']} max_atr={best[1]['max_atr']} sector_limit={best[1]['sector_limit']} dynamic_pos={best[1]['dynamic_pos']}")

# 保存
out_data = {
    "configurations": [
        {"name": name, "params": cfg, "stats": st, "trades": nb, "rejected": rej}
        for name, cfg, st, nb, rej, _ in results
    ],
    "best": {"name": best[0], "params": best[1], "stats": best[2]}
}
out_path = r"D:\Qclaw_Trading\review\filter_optimization_20260714.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out_data, f, ensure_ascii=False, indent=2)
print(f"\n结果已保存: {out_path}")
