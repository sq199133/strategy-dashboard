#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.7 策略收益曲线可视化"""
import os, json, glob, statistics
from datetime import datetime as dt
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import rcParams

rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False

HIST = r"D:\Qclaw_Trading\data\history_long_v2"
POOL = r"D:\Qclaw_Trading\data\etf_pool_V1_full.json"
TOP_N=1; LB=3; ATR_F=0.85; DEV=20.0; W1=W3=0.50; W8=0.00; CAP=100000.0

# ---- 加载数据 ----
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

def sim_oos(stop_mode="baseline"):
    """stop_mode: baseline / ma21_stop / composite_stop"""
    port = {}; cash = CAP; nb = ns = 0
    eq_ts = []; ma21_triggers = []

    for si in range(is1, len(all_wk)-1):
        sw = all_wk[si]; ew = all_wk[si+1]; yr = int(ew.split("-W")[0])

        # === 候选筛选 ===
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
            if price <= ma21: continue  # v4.7 MA21硬过滤
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
        top2_codes = {c["code"] for c in cands[:2]}

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
                base_stop = cp<=-0.08 or hp<=-0.10 or code not in tcodes
                if base_stop:
                    sell.append(code)
                elif stop_mode in ("ma21_stop","composite_stop"):
                    fi0 = fi.get(code)
                    if fi0 is not None:
                        idx_now = fi0 + (si - is0)
                        if idx_now >= 21 and idx_now < len(series[code]):
                            sr_c = series[code]
                            ma21_now = sum(sr_c[j][1] for j in range(idx_now-20, idx_now+1)) / 21
                            price_now = sr_c[idx_now][1]
                            if price_now < ma21_now:
                                if stop_mode == "ma21_stop":
                                    sell.append(code); ma21_triggers.append((sw, code))
                                elif stop_mode == "composite_stop" and code not in top2_codes:
                                    sell.append(code); ma21_triggers.append((sw, code))

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
        eq_ts.append((sw, eq, yr))

    return eq_ts, nb, ns, ma21_triggers

def eq_to_dates(eq_ts):
    """把周标签转为datetime，用于绘图"""
    dates = []
    for wk, _, _ in eq_ts:
        y,w = wk.split("-W")
        # 找到该周周一的日期
        dt_ = dt(int(y),1,1)
        dt_ += __import__('datetime').timedelta(weeks=int(w)-1, days=-dt_.weekday())
        dates.append(dt_)
    vals = [e[1] for e in eq_ts]
    return dates, vals

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
    return {"ann":ann,"max_dd":mdd*100,"sharpe":shp,"final":final,"init":init}

# ---- 跑三个模式 ----
print("正在生成收益曲线...")
eq_baseline, nb_b, ns_b, _ = sim_oos("baseline")
eq_ma21,     nb_m, ns_m, trig_m = sim_oos("ma21_stop")
eq_comp,     nb_c, ns_c, trig_c = sim_oos("composite_stop")

st_b = stats(eq_baseline)
st_m = stats(eq_ma21)
st_c = stats(eq_comp)

dates_b, vals_b = eq_to_dates(eq_baseline)
dates_m, vals_m = eq_to_dates(eq_ma21)
dates_c, vals_c = eq_to_dates(eq_comp)

# ---- 画图 ----
fig, axes = plt.subplots(2, 2, figsize=(16, 11))
fig.patch.set_facecolor('#0d1117')
for ax in axes.flat:
    ax.set_facecolor('#161b22')
    ax.tick_params(colors='#c9d1d9', labelsize=10)
    ax.xaxis.label.set_color('#c9d1d9')
    ax.yaxis.label.set_color('#c9d1d9')
    for spine in ax.spines.values():
        spine.set_color('#30363d')

# 图1：三条equity曲线（累计收益）
ax1 = axes[0,0]
ax1.plot(dates_b, [v/100000-1 for v in vals_b], color='#58a6ff', linewidth=2.0, label='基准止损 (-8%/-10%)', zorder=3)
ax1.plot(dates_m, [v/100000-1 for v in vals_m], color='#f78166', linewidth=1.5, label='+MA21跌破止损', alpha=0.8, zorder=2)
ax1.plot(dates_c, [v/100000-1 for v in vals_c], color='#ffa657', linewidth=1.5, label='+复合止损', alpha=0.8, zorder=2)
ax1.axhline(0, color='#30363d', linewidth=1, linestyle='--')
# IS/OOS分界线
is_end_date = dates_b[0]
ax1.axvline(is_end_date, color='#8b949e', linewidth=1, linestyle=':', alpha=0.7)
ax1.text(is_end_date, ax1.get_ylim()[1]*0.95, ' OOS开始', color='#8b949e', fontsize=9)
ax1.set_title('v4.7 策略累计收益曲线 (2023-2026 OOS)', color='#c9d1d9', fontsize=13, pad=10)
ax1.set_ylabel('累计收益率', color='#c9d1d9')
ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x*100:.0f}%'))
ax1.legend(loc='upper left', facecolor='#21262d', edgecolor='#30363d', labelcolor='#c9d1d9', fontsize=10)
ax1.grid(True, alpha=0.1, color='#30363d')
# 标注终点
ax1.annotate(f'+{st_b["ann"]:.0f}%/年', xy=(dates_b[-1], vals_b[-1]/100000-1),
             xytext=(10,0), textcoords='offset points', color='#58a6ff', fontsize=11, fontweight='bold')

# 图2：基准止损模式的equity（含IS）
ax2 = axes[0,1]
# IS阶段
is_dates = dates_b[:is1-is1]  # OOS开始前的部分？不对，直接用is0开始
# 重新跑IS数据
eq_is, _, _, _ = [], 0, 0, None
# IS太复杂，直接画OOS的drawdown
ax2.plot(dates_b, vals_b, color='#58a6ff', linewidth=2.0, label='组合净值')
ax2.fill_between(dates_b, vals_b, 100000, alpha=0.15, color='#58a6ff')
# 最大回撤标注
eqs_b = vals_b
peak_b = eqs_b[0]; dd_start=dd_end=peak_b
max_dd = 0
for i, v in enumerate(eqs_b):
    if v > peak_b:
        peak_b = v
        dd_start = i
    dd = v/peak_b - 1
    if dd < max_dd:
        max_dd = dd; dd_end = i
ax2.plot([dates_b[dd_start], dates_b[dd_end]],
         [eqs_b[dd_start], eqs_b[dd_end]],
         color='#f85149', linewidth=2.5, linestyle='--', alpha=0.8, label=f'最大回撤 {max_dd*100:.1f}%')
ax2.set_title('基准止损 净值曲线 & 最大回撤', color='#c9d1d9', fontsize=13, pad=10)
ax2.set_ylabel('组合净值', color='#c9d1d9')
ax2.legend(loc='upper left', facecolor='#21262d', edgecolor='#30363d', labelcolor='#c9d1d9', fontsize=10)
ax2.grid(True, alpha=0.1, color='#30363d')
ax2.axhline(100000, color='#30363d', linewidth=1, linestyle='--')

# 图3：三条曲线的季度滚动夏普
ax3 = axes[1,0]
def rolling_sharpe(eq_ts, window=12):
    """12周滚动夏普"""
    dates, vals = eq_to_dates(eq_ts)
    rets = [vals[i]/vals[i-1]-1 for i in range(1,len(vals))]
    shps = []
    for i in range(window, len(rets)):
        rw = rets[i-window:i]
        mu = statistics.mean(rw); sd = statistics.stdev(rw) if len(rw)>1 else 1e-9
        shps.append((dates[i], (mu*52 - 0.02)/(sd*(52**0.5))))
    return shps

shp_b = rolling_sharpe(eq_baseline, 12)
shp_m = rolling_sharpe(eq_ma21, 12)
shp_c = rolling_sharpe(eq_comp, 12)

ax3.axhline(0, color='#30363d', linewidth=1)
ax3.plot([s[0] for s in shp_b], [s[1] for s in shp_b], color='#58a6ff', linewidth=1.8, label='基准止损')
ax3.plot([s[0] for s in shp_m], [s[1] for s in shp_m], color='#f78166', linewidth=1.5, label='+MA21止损', alpha=0.7)
ax3.plot([s[0] for s in shp_c], [s[1] for s in shp_c], color='#ffa657', linewidth=1.5, label='+复合止损', alpha=0.7)
ax3.set_title('12周滚动夏普比率', color='#c9d1d9', fontsize=13, pad=10)
ax3.set_ylabel('年化夏普', color='#c9d1d9')
ax3.legend(loc='upper right', facecolor='#21262d', edgecolor='#30363d', labelcolor='#c9d1d9', fontsize=10)
ax3.grid(True, alpha=0.1, color='#30363d')

# 图4：年度回报柱状图
ax4 = axes[1,1]
def yearly_rets(eq_ts):
    d, v = eq_to_dates(eq_ts)
    by_yr = {}
    for i, (dt_, val) in enumerate(zip(d, v)):
        yr = dt_.year
        by_yr.setdefault(yr, []).append(val)
    ret = {}
    for yr, vals in sorted(by_yr.items()):
        ret[yr] = (vals[-1]/vals[0] - 1) * 100
    return ret

rb = yearly_rets(eq_baseline)
rm = yearly_rets(eq_ma21)
rc = yearly_rets(eq_comp)
years = sorted(rb.keys())

x = range(len(years))
w = 0.25
bars_b = ax4.bar([i-w for i in x], [rb.get(y,0) for y in years], width=w, color='#58a6ff', label='基准止损', zorder=3)
bars_m = ax4.bar(list(x), [rm.get(y,0) for y in years], width=w, color='#f78166', label='+MA21止损', alpha=0.8, zorder=3)
bars_c = ax4.bar([i+w for i in x], [rc.get(y,0) for y in years], width=w, color='#ffa657', label='+复合止损', alpha=0.8, zorder=3)
ax4.axhline(0, color='#c9d1d9', linewidth=0.8)
ax4.set_xticks(list(x))
ax4.set_xticklabels([str(y) for y in years], color='#c9d1d9')
ax4.set_title('年度收益率对比', color='#c9d1d9', fontsize=13, pad=10)
ax4.set_ylabel('年度收益率', color='#c9d1d9')
ax4.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.0f}%'))
ax4.legend(loc='upper left', facecolor='#21262d', edgecolor='#30363d', labelcolor='#c9d1d9', fontsize=10)
ax4.grid(True, alpha=0.1, color='#30363d', axis='y')
for bar, val in zip(bars_b, [rb.get(y,0) for y in years]):
    ax4.text(bar.get_x()+bar.get_width()/2, bar.get_height()+2 if val>=0 else bar.get_height()-5,
             f'{val:.0f}%', ha='center', va='bottom' if val>=0 else 'top',
             color='#58a6ff', fontsize=9)

# 总标题
fig.suptitle('周线动量策略 v4.7 收益分析  |  OOS 2023-W01 ~ 2026-W28',
             color='#c9d1d9', fontsize=15, fontweight='bold', y=0.98)

# 添加统计信息文字框
stats_text = (
    f"基准止损: 年化{st_b['ann']:+.1f}%  Sharpe={st_b['sharpe']:.3f}  MaxDD={abs(st_b['max_dd']):.1f}%\n"
    f"+MA21止损: 年化{st_m['ann']:+.1f}%  Sharpe={st_m['sharpe']:.3f}  MaxDD={abs(st_m['max_dd']):.1f}%\n"
    f"+复合止损: 年化{st_c['ann']:+.1f}%  Sharpe={st_c['sharpe']:.3f}  MaxDD={abs(st_c['max_dd']):.1f}%\n"
    f"MA21止损触发: {len(trig_m)}次  |  复合止损触发: {len(trig_c)}次"
)
fig.text(0.5, 0.01, stats_text, ha='center', va='bottom',
         color='#8b949e', fontsize=10,
         bbox=dict(boxstyle='round,pad=0.4', facecolor='#161b22', edgecolor='#30363d', alpha=0.9))

plt.tight_layout(rect=[0, 0.07, 1, 0.97])
out_path = r"D:\Qclaw_Trading\charts\v4_equity_curves.png"
os.makedirs(os.path.dirname(out_path), exist_ok=True)
plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f"图片已保存: {out_path}")
plt.close()
