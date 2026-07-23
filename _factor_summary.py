#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""因子有效性检验 - 结果汇总"""
import os
from datetime import datetime as dt

# IS: 2017-2022 | OOS: 2023-2026
data = [
    # label,                             ISA,   ISS,   ISD,  OOSA,   OSS,   OSD, BUYS, NOTE
    ("B0_baseline (v4.7)",           27.17,  0.952, -21.6,  21.99, 0.696, -43.6, 250, "[BASELINE]"),
    ("F1_RSI_30-70",                 25.77,  0.905, -23.2,   0.48, 0.104, -47.5, 229, "[X] RSI too narrow"),
    ("F1_RSI_40-80",                 24.22,  0.878, -26.0,  21.06, 0.690, -40.0, 238, "[~] No improvement"),
    ("F2_MACD_bull",                 34.30,  1.186, -22.4,  32.33, 1.038, -21.3, 225, "[OK] MACD>0 quality"),
    ("F2_MACD_gc",                   -0.32, -0.615, -10.0,  -4.58,-0.763, -15.9,   8, "[X] Signal too rare"),
    ("F3_vol_surge_skip",             28.89,  0.999, -23.3,  21.99, 0.696, -43.6, 244, "[~] Rare events"),
    ("F4_ma21_trend",                 32.20,  1.122, -28.2,  41.70, 1.169, -27.8, 231, "[STAR] Best OOS"),
    ("F5_RSI+MA",                    31.13,  1.119, -19.5,  31.35, 0.963, -37.6, 222, "[OK] MA21 primary"),
    ("F6_RSI+MACD",                  38.68,  1.364, -16.4,  23.35, 0.828, -28.8, 215, "[!] IS>OOS overfit"),
]

sep = "=" * 125
print("\n" + sep)
print("  Factor Effectiveness Test  |  IS=2017-2022  OOS=2023-2026  (top=1, w1=0.5/w3=0.5/w8=0.0, dev=20%)")
print(sep)
print("  {:35s}  {:>8}  {:>8}  {:>7}  {:>9}  {:>9}  {:>7}  {:>5}  {}".format(
      "Config", "IS Ann%", "IS Shp", "IS-DD%", "OOS Ann%", "OOS Shp", "OOS-DD%", "Buys", "Assessment"))
print("  " + "-" * 125)
for row in data:
    label, isa, iss, isd, oosa, oss, osd, buys, note = row
    def fmt(v, width=8, sign=True, suffix="%", decimals=2):
        if v is None: return "N/A".rjust(width)
        if isinstance(v, str): return v.rjust(width)
        fmtstr = "{:+" if sign else "{:"
        fmtstr += "{}f}{}".format(width-1, suffix)
        return fmtstr.format(v)
    def fmt_int(v, width=5):
        if v is None: return "N/A".rjust(width)
        return str(int(v)).rjust(width)
    print("  {label:<35s}  {ann:>+8s}  {shp:>8s}  {idd:>7s}  {oann:>+9s}  {oshp:>9s}  {odd:>7s}  {buys:>5s}  {note}".format(
        label=label,
        ann=fmt(isa, 8, True, "%", 2),
        shp="N/A" if isinstance(iss, str) else "{:.3f}".format(iss),
        idd=fmt(abs(isd), 7, False, "%", 1),
        oann=fmt(oosa, 9, True, "%", 2),
        oshp="N/A" if isinstance(oss, str) else "{:.3f}".format(oss),
        odd=fmt(abs(osd), 7, False, "%", 1),
        buys=str(int(buys)).rjust(5),
        note=note))

print()
print(sep)
print("  Key Conclusions")
print(sep)
for c in [
    "[STAR] F4_ma21_trend (MA21 trend filter) is the BEST: OOS Sharpe=1.169, Ann=+41.7%, DD=-27.8%",
    "   -> Logic: Require price > 20-week MA; eliminates false momentum in downtrends",
    "   -> Result vs Baseline: OOS Ann +19.7pp, Sharpe +0.47, DD -15.8pp (43.6%->27.8%)",
    "",
    "[OK] F2_MACD_bull (MACD>0 filter): OOS Sharpe=1.038, Ann=+32.3%, DD=-21.3%",
    "   -> Only selects ETFs with MACD>0 (mid-term trend UP); avoids rallies in bear markets",
    "   -> DD significantly better than baseline (-21.3% vs -43.6%)",
    "",
    "[X] F1_RSI_30-70: OOS Ann only +0.48% -- momentum strategy already picks winners; RSI<30 or >70",
    "     is not the right filter for this strategy type",
    "",
    "[X] F2_MACD_gc: Only 8 trades, no statistical significance; weekly MACD golden cross too rare",
    "",
    "[!] F6_RSI+MACD: IS Sharpe=1.364 but OOS Sharpe=0.828 -- overfitting risk with too many factors",
    "     Single factor (F4) is more robust than multi-factor combo",
    "",
    "[DATA] PE/PB percentile: Cannot test - no PE/PB fields in pool; needs akshare real-time data",
    "[DATA] Crowding factor: Cannot test - needs real-time institutional flow data",
]:
    print("  " + c)

print()
print(sep)
print("  Recommended Actions")
print(sep)
for a in [
    "1. MA21 trend filter: Require price > 20-week MA in addition to dev<20%",
    "   This is the most impactful new factor (F4 result: OOS Sharpe from 0.696 -> 1.169)",
    "2. MACD>0 filter: Add as quality filter; skip ETFs where mid-term trend not started",
    "3. PE/PB percentile: Needs data source integration (akshare index PE data)",
    "4. Crowding: Needs real-time data; current workaround: monitor sector volume share",
]:
    print("  " + a)

# Save
ts = dt.now().strftime("%Y%m%d_%H%M%S")
out = os.path.join(r"D:\Qclaw_Trading\review", "factor_test_summary_{}.md".format(ts))
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    f.write("# Factor Effectiveness Test Report\n\n")
    f.write("**Generated:** {}\n\n".format(ts))
    f.write("## Backtest: IS=2017-2022, OOS=2023-2026 | Baseline: v4.7 (w1=0.5/w3=0.5/w8=0.0, top=1, dev=20%, ATR=0.85)\n\n")
    f.write("| Config | IS Ann% | IS Sharpe | IS-DD% | OOS Ann% | OOS Sharpe | OOS-DD% | Trades | Assessment |\n")
    f.write("|--------|---------|-----------|--------|-----------|------------|---------|--------|------------|\n")
    for row in data:
        label, isa, iss, isd, oosa, oss, osd, buys, note = row
        f.write("| {} | {:+.2f} | {:.3f} | {:.1f}% | {:+.2f} | {:.3f} | {:.1f}% | {} | {} |\n".format(
            label, isa, iss, abs(isd), oosa, oss, abs(osd), buys, note))
    f.write("\n## Key Conclusions\n\n")
    f.write("- **[STAR] F4_ma21_trend**: OOS Sharpe=1.169, Ann=+41.7%, DD=-27.8% -- Best single factor\n")
    f.write("- **[OK] F2_MACD_bull**: OOS Sharpe=1.038, Ann=+32.3%, DD=-21.3% -- Good risk control\n")
    f.write("- **[X] F1_RSI filters**: Not effective for momentum strategy (OOS nearly zero)\n")
    f.write("- **[X] F2_MACD_gc**: Signal too rare (only 8 trades)\n")
    f.write("- **[!] F6_RSI+MACD**: IS strong but OOS shrinks -- overfitting risk\n")
    f.write("- **[DATA] PE/PB, crowding**: Cannot test without real-time data source\n")
    f.write("\n## Recommended Actions\n\n")
    f.write("1. **MA21 trend filter**: Add to v4.7 strategy (most impactful)\n")
    f.write("2. **MACD>0 filter**: Add as quality filter\n")
    f.write("3. **PE/PB percentile**: Needs akshare integration\n")
    f.write("4. **Crowding**: Needs real-time data source\n")
print("\nSaved: " + out)
