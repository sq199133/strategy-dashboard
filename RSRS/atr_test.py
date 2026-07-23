"""
ATR增强测试
"""
import sys, os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))
from rsrs_final_strategy import (load_etf, build_panel, compute_rsrs, compute_vol_scaling)

POOL = {"510050":"SH50","510300":"HS300","510500":"ZZ500",
        "512100":"ZZ1000","159915":"CYB","588000":"KC50",
        "513500":"SP500","513100":"NSDQ","518880":"GOLD","162411":"OIL"}
HIST = r"D:\QClaw_Trading\data\history"

# Load OHLCV data
raw = {}
for code in POOL:
    with open(f"{HIST}\\{code}.json","r",encoding="utf-8") as f:
        d = json.load(f)
    df = pd.DataFrame(d["records"])
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    raw[code] = df

# Compute ATR for each ETF
def compute_atr(df, period=14):
    hl = df["high"] - df["low"]
    hc = abs(df["high"] - df["close"].shift(1))
    lc = abs(df["low"] - df["close"].shift(1))
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean()
    return atr, tr

atr_data = {}
for code, df in raw.items():
    atr, tr = compute_atr(df, 14)
    atr_pct = atr / df["close"] * 100  # ATR as % of price
    atr_data[code] = {
        "atr": atr,
        "atr_pct": atr_pct,
        "atr_ma21": atr.rolling(21).mean(),
        "atr_ma63": atr.rolling(63).mean(),
    }

# Build panel
dates = sorted(set(d for code in raw for d in raw[code].index))
panel = pd.DataFrame(index=dates)
for code in POOL:
    panel[code] = raw[code]["close"].reindex(dates)

# Momentum
mom63 = {}
for code, df in raw.items():
    mom63[code] = df["close"].pct_change(63)

# Signal
df_sig = load_etf("510300")
sc = compute_vol_scaling(df_sig, panel.index, 70, 0.16)
sig_raw, zs_raw, _ = compute_rsrs(df_sig, 18, 900, 0.7, -1.0)
sig_s = pd.Series(sig_raw, index=pd.to_datetime(df_sig["date"].values))

def run(use_atr="none", atr_thr=0.5, lock=42):
    """
    use_atr:
      "none"          - 原版
      "atr_filter"    - ATR%高于阈值的不买(太波动), ATR%低于0.1%的不买(太死)
      "atr_risk_adj"  - 动量/ATR% 排序(单位风险收益)
      "atr_trend"     - ATR上升趋势确认(Atr_ma21 > Atr_ma63)
      "atr_combined"  - 动量*(ATR上升) 排序
    """
    pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    hold, lr, lku = [], None, None
    for dt in panel.index:
        if dt not in sig_s.index: continue
        raw_s = float(sig_s.loc[dt])
        eff = raw_s
        if lock > 0 and lku and dt <= lku and raw_s == 0: eff = 1.0
        if eff == 0: hold, lku = [], None; continue
        if lock > 0 and raw_s == 1 and lku is None: lku = dt + pd.Timedelta(days=lock)
        if lr is None or (dt - lr).days >= 63:
            cand = []
            for c in POOL:
                if dt not in mom63[c].index or np.isnan(mom63[c].loc[dt]): continue
                mom = float(mom63[c].loc[dt])
                if mom <= 0: continue  # base filter
                
                atrp = float(atr_data[c]["atr_pct"].loc[dt]) if dt in atr_data[c]["atr_pct"].index else 0
                atr21 = float(atr_data[c]["atr_ma21"].loc[dt]) if dt in atr_data[c]["atr_ma21"].index else 0
                atr63 = float(atr_data[c]["atr_ma63"].loc[dt]) if dt in atr_data[c]["atr_ma63"].index else 1
                atr_trend_up = atr21 > atr63 if atr63 > 0 else True
                
                cand.append((c, mom, atrp, atr_trend_up))
            if not cand: hold = []; continue
            
            if use_atr == "none":
                cand.sort(key=lambda x: -x[1])
                hold = [cand[0][0]]
            elif use_atr == "atr_filter":
                # 过滤: 剔除ATR%过高(>thr%)或过低(<0.1%)的
                valid = [x for x in cand if x[2] < atr_thr and x[2] > 0.1]
                if not valid: hold = []; continue
                valid.sort(key=lambda x: -x[1])
                hold = [valid[0][0]]
            elif use_atr == "atr_risk_adj":
                # 动量/ATR% 排序 = 单位波动收益
                scored = [(c, mom/atrp if atrp > 0 else 0) for c,mom,atrp,_ in cand]
                scored.sort(key=lambda x: -x[1])
                hold = [scored[0][0]]
            elif use_atr == "atr_trend":
                # ATR上升趋势确认
                valid = [x for x in cand if x[3]]  # atr_trend_up == True
                if not valid: hold = []; continue
                valid.sort(key=lambda x: -x[1])
                hold = [valid[0][0]]
            elif use_atr == "atr_combined":
                # 动量 * (1 + ATR_trend_up) 加分
                scored = [(c, mom * (1.2 if x[3] else 1.0)) for c,mom,_,x[3] in [(c,mom,atrp,atu)
                                                                               for c,mom,atrp,atu in cand]]
                # Actually let me redo this
                cand_only = cand
                scored = []
                for c,mom,atrp,atu in cand_only:
                    score = mom * (1.3 if atu else 1.0)
                    scored.append((c, score))
                scored.sort(key=lambda x: -x[1])
                hold = [scored[0][0]]
            
            lr = dt
        if hold:
            w = float(sc.loc[dt]) if dt in sc.index else 1.0
            if hold[0] in pos.columns: pos.loc[dt, hold[0]] = w
    
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig["date"].iloc[900])
    ret = ret[ret.index >= fs]
    if len(ret) < 20: return None
    eq = (1 + ret).cumprod()
    annual = {}
    for yr in sorted(set(d.year for d in ret.index)):
        m = ret.index.year == yr
        nd = m.sum()
        if nd < 5: continue
        annual[yr] = round(((1+ret[m]).cumprod().iloc[-1] - 1) * 100, 1)
    cagr = round((eq.iloc[-1]**(252/len(ret))-1)*100, 1)
    sp = round(np.sqrt(252)*ret.mean()/ret.std(), 2) if ret.std()>1e-10 else 0
    mdd = round(((eq-eq.cummax())/eq.cummax()).min()*100, 1)
    calmar = round(cagr/abs(mdd), 2) if mdd < 0 else 0
    pr = round((pos.sum(axis=1)>0).mean()*100, 1)
    total_ret = round((eq.iloc[-1] - 1) * 100, 1)
    return {"CAGR":cagr,"Sharpe":sp,"MDD":mdd,"Calmar":calmar,"Pos%":pr,"Total":total_ret,"Annual":annual}

SEP = "="*95
print(SEP)
print("  ATR增强测试")
print(SEP)

# Test each ATR mode
atr_modes = [
    ("原版基线", "none", 0),
    ("ATR过滤(剔除过波动/过平静)", "atr_filter", 1.5),
    ("ATR过滤(更严格)", "atr_filter", 1.0),
    ("ATR过滤(极严格)", "atr_filter", 0.7),
    ("ATR单位风险调整(动量/ATR%)", "atr_risk_adj", 0),
    ("ATR趋势确认(上升趋势才买)", "atr_trend", 0),
    ("ATR综合(动量*ATR趋势加权)", "atr_combined", 0),
]

for name, mode, thr in atr_modes:
    r = run(use_atr=mode, atr_thr=thr)
    if r:
        chg = round(r['CAGR'] - 12.1, 1)
        print(f"\n  {name}")
        print(f"  CAGR={r['CAGR']:>5.1f}%(Δ{chg:+.1f})  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  Calmar={r['Calmar']:.2f}  仓位={r['Pos%']:.0f}%")

# ═══ ATR + 动量窗口组合测试 ═══
print(f"\n{SEP}")
print("  ATR + 不同动量窗口")
print(SEP)

# Quick ATR filter + different momentum
for mw in [21, 42, 63]:
    m_mom = {}
    for code, df in raw.items():
        m_mom[code] = df["close"].pct_change(mw)
    
    pos = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    hold, lr, lku = [], None, None
    for dt in panel.index:
        if dt not in sig_s.index: continue
        raw_s = float(sig_s.loc[dt])
        eff = raw_s
        if lock > 0 and lku and dt <= lku and raw_s == 0: eff = 1.0
        if eff == 0: hold, lku = [], None; continue
        if lock > 0 and raw_s == 1 and lku is None: lku = dt + pd.Timedelta(days=42)
        if lr is None or (dt - lr).days >= 63:
            cand = []
            for c in POOL:
                if dt not in m_mom[c].index or np.isnan(m_mom[c].loc[dt]): continue
                mom = float(m_mom[c].loc[dt])
                if mom <= 0: continue
                atrp = float(atr_data[c]["atr_pct"].loc[dt]) if dt in atr_data[c]["atr_pct"].index else 0
                cand.append((c, mom, atrp))
            if not cand: hold = []; continue
            # Only remove very high vol (>2%), but keep all others
            valid = [x for x in cand if x[2] < 2.0]
            if not valid: hold = []; continue
            valid.sort(key=lambda x: -x[1])
            hold = [valid[0][0]]
            lr = dt
        if hold:
            w = float(sc.loc[dt]) if dt in sc.index else 1.0
            if hold[0] in pos.columns: pos.loc[dt, hold[0]] = w
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df_sig["date"].iloc[900])
    ret = ret[ret.index >= fs]
    if len(ret) < 20: continue
    eq = (1 + ret).cumprod()
    cagr = round((eq.iloc[-1]**(252/len(ret))-1)*100, 1)
    sp = round(np.sqrt(252)*ret.mean()/ret.std(), 2) if ret.std()>1e-10 else 0
    mdd = round(((eq-eq.cummax())/eq.cummax()).min()*100, 1)
    calmar = round(cagr/abs(mdd), 2) if mdd < 0 else 0
    chg = round(cagr - 12.1, 1)
    print(f"  ATR过滤+mom={mw:>2}d: CAGR={cagr:>5.1f}%(Δ{chg:+.1f})  Sharpe={sp:.2f}  MDD={mdd:>5.1f}%  Calmar={calmar:.2f}")

# ═══ ATR针对原油特殊处理 ═══
print(f"\n{SEP}")
print("  原油ATR特别高的问题检查")
print(SEP)
for code in ["518880","162411","513100","510300"]:
    atrp = atr_data[code]["atr_pct"]
    mean_atrp = atrp.mean()
    max_atrp = atrp.max()
    p95_atrp = atrp.quantile(0.95)
    print(f"  {code} {POOL[code]:<8}: 平均ATR={mean_atrp:.2f}%  P95={p95_atrp:.2f}%  最大ATR={max_atrp:.2f}%", end="")
    # Check if oil has particularly high ATR
    oil_atrp = atr_data["162411"]["atr_pct"]
    zhong_atrp = atr_data["510300"]["atr_pct"]
    ratio = (atrp / zhong_atrp).mean()
    print(f"  (vs沪深300倍数: {ratio:.1f}x)")

print(f"\n{SEP}")
print("  完成")
print(SEP)
