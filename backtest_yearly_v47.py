#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.7 年度回报回测"""
import os, json, glob, statistics
from datetime import datetime as dt

HIST  = r"D:\Qclaw_Trading\data\history_long_v2"
POOL  = r"D:\Qclaw_Trading\data\etf_pool_V1_full.json"
OUTD  = r"D:\Qclaw_Trading\review"
TOP_N = 1; LB = 3; ATR_F = 0.85; DEV = 20.0
W1 = 0.50; W3 = 0.50; W8 = 0.00
VS = 1.5; CAP = 100000.0


def load():
    with open(POOL, encoding="utf-8") as f:
        raw = f.read()
    d = json.loads(raw)
    etfs = d if isinstance(d, list) else d.get("data", [])
    series, ohlc, cats, weeks = {}, {}, {}, set()
    for e in etfs:
        code = e["code"]; cat = e.get("category", "") or ""
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
        except Exception:
            continue
        if not recs: continue
        wm = {}
        for r in recs:
            ds = r.get("date","") or r.get("w","")
            if not ds: continue
            try:
                y,wn = dt.strptime(ds,"%Y-%m-%d").isocalendar()[:2]
                wk = "{}-W{:02d}".format(y, wn)
                c = r.get("close",0); o = r.get("open",0)
                h = r.get("high",0); l = r.get("low",0); v = r.get("vol",0)
                if wk not in wm or ds > wm[wk][0]:
                    wm[wk] = (ds,c,o,h,l,v)
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
                f14 = sum(vs[-14:])/14; s21 = sum(vs)/21
                if s21 > 0: atrs[wkl[i]] = f14/s21
        atr[code] = atrs
    return etfs, series, ohlc, cats, all_wk, atr


def sim(etfs, series, ohlc, cats, all_wk, atr, si0, si1, new_strat, stop_mode="baseline", top_for_stop=2):
    cwkl = {c:[wk for wk,_ in s] for c,s in series.items()}
    fi = {c: next((j for j,(wk,_) in enumerate(s) if wk==all_wk[si0]), None)
          for c,s in series.items()}
    port = {}; cash = CAP; nb = ns = 0
    eq_ts = []

    for si in range(si0, max(si1-1, si0)):
        sw = all_wk[si]; ew = all_wk[si+1]; yr = int(ew.split("-W")[0])
        cands = []
        for code, s in series.items():
            fi0 = fi.get(code)
            if fi0 is None: continue
            idx = fi0 + (si - si0)
            if idx < 21 or idx >= len(s): continue
            o = ohlc.get(code, {}); sr = series.get(code, [])
            price = sr[idx][1]
            if not price or price <= 0: continue
            ma5  = sum(sr[j][1] for j in range(idx-4,idx+1)) / 5
            ma21 = sum(sr[j][1] for j in range(idx-20,idx+1)) / 21
            if ma21 == 0: continue
            dev = abs(price/ma21 - 1) * 100
            if dev > DEV: continue
            ar = atr.get(code,{}).get(sr[idx][0])
            if ar is not None and ar < ATR_F: continue
            # === NEW: MA21 hard filter ===
            if new_strat and price <= ma21: continue
            mom   = price / sr[idx-LB][1] - 1
            mom1w = price / sr[idx-1][1] - 1 if idx>=1 else mom
            mom8w = price / sr[idx-8][1] - 1 if idx>=8 else mom
            score = W1*mom1w + W3*mom + W8*mom8w
            w0 = o.get(sr[idx][0],{})
            vr = 1.0; cpat = False
            if w0 and all(w0.get(k) for k in ("c","o","h","l")):
                ci,oi,hi,li = w0["c"],w0["o"],w0["h"],w0["l"]
                body = abs(ci-oi); us = hi-max(ci,oi)
                ls = min(ci,oi)-li; s2b = us/body if body>0 else 99
                vv = [o.get(cwkl[code][j],{}).get("v",0) for j in range(max(0,idx-9),idx+1)]
                vv = [v for v in vv if v]
                avg10 = sum(vv)/len(vv) if vv else 1
                vr = w0.get("v",0)/avg10 if avg10>0 else 1
                g20 = 0
                if idx >= 20:
                    pc = o.get(cwkl[code][idx-20],{}).get("c")
                    if pc and pc>0: g20 = ci/pc-1
                cpat = (ci>oi and s2b>1.0 and ls<body*0.5
                        and vr<VS and ci>ma5>ma21 and g20<0.5)
            if vr > VS: continue
            adj = score + (0.02 if (not new_strat and cpat) else 0)
            cands.append({"code":code,"_adj":adj,"cat":cats.get(code,"")})
        cands.sort(key=lambda x: x["_adj"], reverse=True)
        used = set(); tgt = []
        for c in cands:
            if c["cat"] not in used: used.add(c["cat"]); tgt.append(c)
        tgt = tgt[:TOP_N]; tcodes = {t["code"] for t in tgt}
        for code, pos in list(port.items()):
            p = next((cl for wk,cl in series[code] if wk==sw), None)
            if p and p>port[code]["hwm"]: port[code]["hwm"] = p
        # top_for_stop ranking candidates (from unfiltered list)
        top_for_stop_codes = {c["code"] for c in cands[:top_for_stop]}
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
                        idx_now = fi0 + (si - si0)
                        if idx_now >= 21 and idx_now < len(series[code]):
                            sr_c = series[code]
                            ma21_now = sum(sr_c[j][1] for j in range(idx_now-20, idx_now+1)) / 21
                            price_now = sr_c[idx_now][1]
                            if price_now < ma21_now:
                                if stop_mode == "ma21_stop":
                                    sell.append(code)
                                elif stop_mode == "composite_stop" and code not in top_for_stop_codes:
                                    sell.append(code)
        for code in sell:
            pos = port.pop(code)
            p = next((cl for wk,cl in series[code] if wk==sw), None)
            cash += pos["weight"]*(p or pos["buy_price"]); ns += 1
        slots = TOP_N - len(port)
        if slots > 0 and cash > 0:
            bl = [t for t in tgt if t["code"] not in port]
            ta = cash + sum(p2["weight"]*p2["buy_price"] for p2 in port.values())
            bw = []
            for bc in bl[:slots]:
                px = next((cl for wk,cl in series[bc["code"]] if wk==sw), None)
                if not px or px<=0: continue
                wa = max(atr.get(bc["code"],{}).get(sw,1), 0.3)
                bw.append((bc["code"],px,wa))
            if bw:
                tw = sum(w for _,_,w in bw)
                for code,px,wa in bw:
                    sv = ta*(wa/tw); wt = sv/px; cost = wt*px
                    if cost > cash*0.98: wt = cash*0.98/px; cost = wt*px
                    if wt<=0: continue
                    cash -= cost
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
    wr2=sum(1 for r in wr if r>0)/len(wr)*100 if wr else 0
    return {"ann":ann,"sharpe":shp,"max_dd":mdd*100,"win_rate":wr2,"total":(final/init-1)*100}


def yr_stats(eq_ts):
    by = {}
    for wk,eq,yr in eq_ts:
        by.setdefault(yr,[]).append(eq)
    res = {}
    for yr,eqs in sorted(by.items()):
        if len(eqs)<2: continue
        peak=eqs[0]; mdd=0
        for eq in eqs:
            if eq>peak: peak=eq
            dd=eq/peak-1
            if dd<mdd: mdd=dd
        res[yr]={"ret":(eqs[-1]/eqs[0]-1)*100,"max_dd":mdd*100,"weeks":len(eqs)}
    return res


def main():
    t0 = dt.now()
    print("\n" + "="*90)
    print("  v4.7 年度回报回测")
    print("="*90)
    etfs, series, ohlc, cats, all_wk, atr = load()
    print("  ETF={}  周={}".format(len(series), len(all_wk)))
    if len(all_wk) < 100:
        print("ERROR: not enough weeks loaded"); return

    def idx(w): return next((i for i,ww in enumerate(all_wk) if ww==w), None)
    is0 = max(0, (idx("2017-W01") or 0) - 1)
    is1 = idx("2023-W01") or 0
    print("  IS: {} - {}  |  OOS: {} - {}".format(
        all_wk[is0], all_wk[is1-1], all_wk[is1], all_wk[-1]))

    configs = [
        ("旧策略(MA5>MA21软+c_bonus+0.02)",  False),
        ("旧策略(MA5>MA21软+无c_bonus)",      False),
        ("新策略v4.7(MA21硬+无c_bonus)",      True),
        ("新策略(MA21硬+c_bonus+0.02)",       True),
    ]
    slabels = ["旧B0","旧nopat","新v47","新+c"]

    print("\n[IS 回测]")
    is_res = []
    for i,(label,ns) in enumerate(configs):
        print("  {} ...".format(label), end="", flush=True)
        eq,nb,_ = sim(etfs,series,ohlc,cats,all_wk,atr,is0,is1,ns)
        st = stats(eq); yr = yr_stats(eq)
        is_res.append((slabels[i], eq, st, yr, nb))
        print("  Ann={:+.1f}% Sharpe={:.3f}".format(st["ann"] if st else 0, st["sharpe"] if st else 0))

    print("\n[OOS 回测]")
    oos_res = []
    for i,(label,ns) in enumerate(configs):
        print("  {} ...".format(label), end="", flush=True)
        eq,nb,_ = sim(etfs,series,ohlc,cats,all_wk,atr,is1,len(all_wk)-1,ns)
        st = stats(eq); yr = yr_stats(eq)
        oos_res.append((slabels[i], eq, st, yr, nb))
        print("  Ann={:+.1f}% Sharpe={:.3f}".format(st["ann"] if st else 0, st["sharpe"] if st else 0))

    all_yrs = sorted(set(yr for _,_,_,y,_ in (is_res+oos_res) for yr in y))

    W = 110; sep = "="*W
    print("\n" + sep)
    print("  IS 阶段年度回报 (2017-2022)")
    print(sep)
    hdr = "  {:8s}".format("年份") + "".join("  {:>12s}".format(sl) for sl in slabels)
    print(hdr + "\n  " + "-"*W)
    for yr in all_yrs:
        if yr>=2023: continue
        row = "  {:8s}".format(str(yr))
        for sl,_,_,yr_d,_ in is_res:
            d=yr_d.get(yr,{}); r=d.get("ret",0); dd=d.get("max_dd",0)
            row += "  {:>+10.1f}%{:>4.0f}DD".format(r,abs(dd))
        print(row)
    print("  " + "-"*W)
    row = "  {:8s}".format("IS汇总")
    for sl,_,st,_,_ in is_res:
        if st: row += "  {:>+10.1f}%{:>4.0f}SH".format(st["ann"],st["sharpe"])
        else: row += "  {:>14s}".format("N/A")
    print(row)

    print("\n" + sep)
    print("  OOS 阶段年度回报 (2023-2026)")
    print(sep)
    print(hdr + "\n  " + "-"*W)
    for yr in all_yrs:
        if yr<2023: continue
        row = "  {:8s}".format(str(yr))
        for sl,_,_,yr_d,_ in oos_res:
            d=yr_d.get(yr,{}); r=d.get("ret",0); dd=d.get("max_dd",0)
            row += "  {:>+10.1f}%{:>4.0f}DD".format(r,abs(dd))
        print(row)
    print("  " + "-"*W)
    row = "  {:8s}".format("OOS汇总")
    for sl,_,st,_,_ in oos_res:
        if st: row += "  {:>+10.1f}%{:>4.0f}SH".format(st["ann"],st["sharpe"])
        else: row += "  {:>14s}".format("N/A")
    print(row)

    print("\n" + sep)
    print("  关键指标对比 (OOS 2023-2026)")
    print(sep)
    print("  {:30s}  {:>10s}  {:>7s}  {:>7s}  {:>7s}  {:>6s}".format(
        "策略","年化收益","Sharpe","最大回撤","胜率","交易"))
    print("  " + "-"*W)
    for sl,_,st,_,nb in oos_res:
        if st:
            print("  {:30s}  {:>+10.2f}%  {:>7.3f}  {:>6.1f}%  {:>6.1f}%  {:>5d}".format(
                sl, st["ann"], st["sharpe"], abs(st["max_dd"]), st["win_rate"], nb))

    print("\n" + sep)
    print("  新策略 vs 旧策略年度跑赢 (OOS)")
    print(sep)
    old_y = dict(oos_res[0][3])
    new_y = dict(oos_res[2][3])
    wins = sum(1 for yr in all_yrs if yr>=2023 and yr in new_y
                and yr in old_y and new_y[yr]["ret"]>old_y[yr]["ret"])
    total = sum(1 for yr in all_yrs if yr>=2023 and yr in new_y)
    for yr in all_yrs:
        if yr<2023 or yr not in new_y: continue
        o = old_y.get(yr,{}).get("ret",0)
        n = new_y[yr]["ret"]
        d = n-o
        w = "WIN" if d>0 else "LOSE"
        print("  {}  {}: 旧={:+.1f}%  新={:+.1f}%  ({:+.1f}%)".format(w,yr,o,n,d))
    print("  -> 新策略跑赢旧策略: {}/{} 年".format(wins,total))

    ts = dt.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(OUTD, "yearly_v47_{}.json".format(ts))
    # ===== 止损模式对比（基于新v4.7策略）=====
    print("\n" + "="*90)
    print("  止损模式对比 (OOS 2023-2026，基于新策略v4.7)")
    print("="*90)
    stop_modes = [
        ("baseline",       "基准止损(-8%/-10%)"),
        ("ma21_stop",      "+MA21跌破止损"),
        ("composite_stop", "+复合止损(MA21+排名)"),
    ]
    # baseline用已有结果，ma21_stop和composite_stop重新跑
    stop_eqs = {
        "baseline":       (oos_res[2][1], oos_res[2][4]),  # eq_ts, nb
        "ma21_stop":      None,
        "composite_stop": None,
    }
    for mode, label in stop_modes:
        if mode == "baseline":
            eq, nb = stop_eqs["baseline"]
            st = stats(eq)
        else:
            print("  {} ...".format(label), end="", flush=True)
            eq, nb, _ = sim(etfs,series,ohlc,cats,all_wk,atr,is1,len(all_wk)-1,
                            new_strat=True, stop_mode=mode)
            st = stats(eq)
            stop_eqs[mode] = (eq, nb)
            print("完成")
        if st:
            print("  {:30s}  {:>+8.1f}%  Sharpe={:.3f}  MaxDD={:>6.1f}%  交易={:>3d}".format(
                label, st["ann"], st["sharpe"], abs(st["max_dd"]), nb))

    # 年度对比（仅ma21_stop和composite_stop重跑）
    print("\n  年度回报对比:")
    print("  " + "-"*80)
    hdr = "  {:6s}".format("年份") + "".join("  {:>18s}".format(label) for _,label in stop_modes)
    print(hdr)
    print("  " + "-"*80)
    yr_map = {}  # mode -> {yr: ret}
    for mode, _ in stop_modes:
        eq, nb = stop_eqs[mode]
        for wk, eq_val, yr in eq:
            yr_map.setdefault(mode, {}).setdefault(yr, []).append(eq_val)
    all_yrs_s = sorted(set(yr for d in yr_map.values() for yr in d))
    for yr in all_yrs_s:
        row = "  {:6s}".format(str(yr))
        for mode, label in stop_modes:
            vals = yr_map[mode].get(yr, [])
            if len(vals) >= 2:
                r = (vals[-1]/vals[0]-1)*100
                peak = vals[0]; mdd = 0
                for v in vals:
                    if v > peak: peak = v
                    dd = v/peak-1
                    if dd < mdd: mdd = dd
                row += "  {:>+10.1f}%{:>6.0f}DD".format(r, abs(mdd*100))
            else:
                row += "  {:>16s}".format("N/A")
        print(row)

    with open(out,"w", encoding="utf-8") as f:
        json.dump({
            "is_yearly": [(sl,dict(y)) for sl,_,_,y,_ in is_res],
            "oos_yearly": [(sl,dict(y)) for sl,_,_,y,_ in oos_res],
            "is_stats": [(sl,s) for sl,_,s,_,_ in is_res],
            "oos_stats": [(sl,s) for sl,_,s,_,_ in oos_res],
        }, f, ensure_ascii=False, indent=2)
    print("\nSaved: " + out)
    print("Time: {:.0f}s".format((dt.now()-t0).total_seconds()))


if __name__ == "__main__": main()
