#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.7 vs v4.8对比图"""
import os, json, glob, statistics
from datetime import datetime as dt
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rcParams
rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
rcParams['axes.unicode_minus'] = False

HIST  = r"D:\Qclaw_Trading\data\history_long_v2"
POOL  = r"D:\Qclaw_Trading\data\etf_pool_V1_full.json"
TOP_N = 1; LB = 3; ATR_F = 0.85; CAP = 100000.0
W1, W3, W8 = 0.50, 0.50, 0.00

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

def sim(max_dev):
    port = {}; cash = CAP; nb = 0
    eq_ts = []
    
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
            
            ma21 = sum(sr[j][1] for j in range(idx_-20,idx_+1)) / 21
            if ma21 == 0: continue
            
            dev = abs(price/ma21 - 1) * 100
            if dev > max_dev: continue
            if price <= ma21: continue
            
            ar = atr.get(code,{}).get(sr[idx_][0])
            if ar is not None and ar < ATR_F: continue
            
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
        eq_ts.append((ew, eq, yr))
    
    return eq_ts, nb

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

# 跑两个策略
print("生成对比图...")
eq_v47, _ = sim(20)
eq_v48, _ = sim(30)
st47 = stats(eq_v47)
st48 = stats(eq_v48)

# 转日期
def to_dates(eq_ts):
    dates = []
    for wk, _, _ in eq_ts:
        y,w = wk.split("-W")
        dt_ = dt(int(y),1,1)
        dt_ += __import__('datetime').timedelta(weeks=int(w)-1, days=-dt_.weekday())
        dates.append(dt_)
    vals = [e[1] for e in eq_ts]
    return dates, vals

d47, v47 = to_dates(eq_v47)
d48, v48 = to_dates(eq_v48)

# 画图
fig, axes = plt.subplots(2, 2, figsize=(16, 11))
fig.patch.set_facecolor('#0d1117')
for ax in axes.flat:
    ax.set_facecolor('#161b22')
    ax.tick_params(colors='#c9d1d9', labelsize=10)
    for spine in ax.spines.values():
        spine.set_color('#30363d')

# 图1：累计收益
ax1 = axes[0,0]
ax1.plot(d47, [v/100000-1 for v in v47], color='#58a6ff', linewidth=2.5, label='v4.7基准 (dev=20%)')
ax1.plot(d48, [v/100000-1 for v in v48], color='#7ee787', linewidth=2.5, label='v4.8优化 (dev=30%)')
ax1.axhline(0, color='#30363d', linewidth=1, linestyle='--')
ax1.set_title('累计收益曲线对比', color='#c9d1d9', fontsize=13, pad=10)
ax1.set_ylabel('累计收益率', color='#c9d1d9')
ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x*100:.0f}%'))
ax1.legend(loc='upper left', facecolor='#21262d', edgecolor='#30363d', labelcolor='#c9d1d9')
ax1.grid(True, alpha=0.1, color='#30363d')
ax1.annotate(f'+{st47["ann"]:.0f}%/年\nSharpe={st47["sharpe"]:.2f}', 
             xy=(d47[-1], v47[-1]/100000-1), xytext=(-80, -20),
             textcoords='offset points', color='#58a6ff', fontsize=11, fontweight='bold')
ax1.annotate(f'+{st48["ann"]:.0f}%/年\nSharpe={st48["sharpe"]:.2f}', 
             xy=(d48[-1], v48[-1]/100000-1), xytext=(-80, 20),
             textcoords='offset points', color='#7ee787', fontsize=11, fontweight='bold')

# 图2：净值曲线
ax2 = axes[0,1]
ax2.plot(d47, v47, color='#58a6ff', linewidth=2, label='v4.7基准')
ax2.plot(d48, v48, color='#7ee787', linewidth=2, label='v4.8优化')
ax2.fill_between(d47, v47, 100000, alpha=0.1, color='#58a6ff')
ax2.fill_between(d48, v48, 100000, alpha=0.1, color='#7ee787')
ax2.axhline(100000, color='#30363d', linewidth=1, linestyle='--')
ax2.set_title('净值曲线对比', color='#c9d1d9', fontsize=13, pad=10)
ax2.set_ylabel('组合净值', color='#c9d1d9')
ax2.legend(loc='upper left', facecolor='#21262d', edgecolor='#30363d', labelcolor='#c9d1d9')
ax2.grid(True, alpha=0.1, color='#30363d')

# 图3：滚动夏普
ax3 = axes[1,0]
def rolling_sharpe(vals, window=12):
    rets = [vals[i]/vals[i-1]-1 for i in range(1,len(vals))]
    shps = []
    for i in range(window, len(rets)):
        rw = rets[i-window:i]
        mu = statistics.mean(rw); sd = statistics.stdev(rw) if len(rw)>1 else 1e-9
        shps.append((mu*52 - 0.02)/(sd*(52**0.5)))
    return shps

shp47 = rolling_sharpe(v47)
shp48 = rolling_sharpe(v48)
ax3.axhline(0, color='#30363d', linewidth=1)
ax3.plot(d47[13:], shp47, color='#58a6ff', linewidth=1.5, label='v4.7基准', alpha=0.8)
ax3.plot(d48[13:], shp48, color='#7ee787', linewidth=1.5, label='v4.8优化', alpha=0.8)
ax3.set_title('12周滚动夏普比率', color='#c9d1d9', fontsize=13, pad=10)
ax3.set_ylabel('年化夏普', color='#c9d1d9')
ax3.legend(loc='upper right', facecolor='#21262d', edgecolor='#30363d', labelcolor='#c9d1d9')
ax3.grid(True, alpha=0.1, color='#30363d')

# 图4：年度收益
ax4 = axes[1,1]
def yearly_rets(dates, vals):
    by_yr = {}
    for dt_, val in zip(dates, vals):
        yr = dt_.year
        by_yr.setdefault(yr, []).append(val)
    ret = {}
    for yr, vs in sorted(by_yr.items()):
        ret[yr] = (vs[-1]/vs[0] - 1) * 100
    return ret

yr47 = yearly_rets(d47, v47)
yr48 = yearly_rets(d48, v48)
years = sorted(set(yr47.keys()) | set(yr48.keys()))
x = range(len(years))
w = 0.35
ax4.bar([i-w/2 for i in x], [yr47.get(y,0) for y in years], width=w, color='#58a6ff', label='v4.7基准')
ax4.bar([i+w/2 for i in x], [yr48.get(y,0) for y in years], width=w, color='#7ee787', label='v4.8优化')
ax4.axhline(0, color='#c9d1d9', linewidth=0.8)
ax4.set_xticks(list(x))
ax4.set_xticklabels([str(y) for y in years], color='#c9d1d9')
ax4.set_title('年度收益率对比', color='#c9d1d9', fontsize=13, pad=10)
ax4.set_ylabel('年度收益率', color='#c9d1d9')
ax4.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.0f}%'))
ax4.legend(loc='upper left', facecolor='#21262d', edgecolor='#30363d', labelcolor='#c9d1d9')
ax4.grid(True, alpha=0.1, color='#30363d', axis='y')

# 标注
for i, y in enumerate(years):
    v47v = yr47.get(y,0); v48v = yr48.get(y,0)
    diff = v48v - v47v
    if abs(diff) > 1:
        color = '#7ee787' if diff > 0 else '#f85149'
        ax4.text(i, max(v47v, v48v)+5, f'{diff:+.0f}pp', ha='center', color=color, fontsize=9)

fig.suptitle('周线动量策略 v4.7 → v4.8 优化对比  |  OOS 2023-2026',
             color='#c9d1d9', fontsize=15, fontweight='bold', y=0.98)

stats_text = (
    f"v4.7基准 (dev=20%): 年化{st47['ann']:+.1f}%  Sharpe={st47['sharpe']:.3f}  MaxDD={abs(st47['max_dd']):.1f}%\n"
    f"v4.8优化 (dev=30%): 年化{st48['ann']:+.1f}%  Sharpe={st48['sharpe']:.3f}  MaxDD={abs(st48['max_dd']):.1f}%\n"
    f"提升: 年化+{st48['ann']-st47['ann']:.1f}pp  Sharpe+{st48['sharpe']-st47['sharpe']:.3f}"
)
fig.text(0.5, 0.01, stats_text, ha='center', va='bottom',
         color='#c9d1d9', fontsize=11,
         bbox=dict(boxstyle='round,pad=0.4', facecolor='#161b22', edgecolor='#30363d'))

plt.tight_layout(rect=[0, 0.08, 1, 0.97])
out_path = r"D:\Qclaw_Trading\charts\v48_comparison.png"
os.makedirs(os.path.dirname(out_path), exist_ok=True)
plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f"图片已保存: {out_path}")
plt.close()
