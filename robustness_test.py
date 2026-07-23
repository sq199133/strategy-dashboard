import sys, os, json, math, time, subprocess, re
from datetime import datetime

HISTORY_DIR = r"D:\QClaw_Trading\data\history_long_v2"
POOL_FILE   = r"D:\QClaw_Trading\data\etf_pool_V1_full.json"
BT_FILE     = r"D:\QClaw_Trading\backtest_integrated_v3.py"

# === 读取基准源码 ===
def read_src():
    with open(BT_FILE, "r", encoding="utf-8") as f:
        return f.read()
def patch_and_run(is_patch, is_s, is_e, oos_patch, oos_s, oos_e, no_dedup=True):
    """
    修改 backtest_integrated_v3.py 源码参数后运行回测，完成后恢复
    is_patch / oos_patch: dict of "DEF_SC_W1 = 0.32" style lines
    如果 is_patch == oos_patch 则只跑一次（用同一个patch覆盖IS和OOS）
    """
    # Save original source
    orig_src = read_src()

    def apply_patch(src, patch):
        s = src
        for key, val in patch.items():
            # Try simple line-start match first (single var)
            pattern = rf'^{re.escape(key)}\s*=\s*[\d.]+'
            new_s = re.sub(pattern, f'{key} = {val}', s, flags=re.MULTILINE)
            if new_s == s:
                # Tuple assignment: "DEF_SC_W1, DEF_SC_W3 = 0.40, 0.40"
                # Find the line containing key, then do positional replacement
                for line in s.split('\n'):
                    if key in line and '=' in line and ',' in line.split('=', 1)[1]:
                        # It's a tuple assignment
                        lhs = [x.strip() for x in line.split('=')[0].split(',')]
                        rhs = [x.strip() for x in line.split('=')[1].split(',')]
                        if key in lhs:
                            idx = lhs.index(key)
                            if idx < len(rhs):
                                rhs[idx] = val
                                new_line = '='.join([','.join(lhs), ','.join(rhs)])
                                s = s.replace(line, new_line, 1)
                        break
            else:
                s = new_s
        return s

    is_src = apply_patch(orig_src, is_patch)
    oos_src = apply_patch(orig_src, oos_patch)

    # Write patched module(s)
    if is_patch == oos_patch:
        # Single module for both periods
        with open(BT_FILE, "w", encoding="utf-8") as f:
            f.write(is_src)
        script = (
            f"import sys,json\n"
            f"sys.path.insert(0,r'D:\\QClaw_Trading')\n"
            f"from backtest_integrated_v3 import load_all_data,run_oos\n"
            f"etfs,series,ohlc,code_cat,all_weeks,atr=load_all_data()\n"
            f"r1=run_oos(etfs,series,ohlc,code_cat,all_weeks,atr,{is_s},{is_e},True,no_dedup={str(no_dedup)})\n"
            f"r2=run_oos(etfs,series,ohlc,code_cat,all_weeks,atr,{oos_s},{oos_e},True,no_dedup={str(no_dedup)})\n"
            f"print(json.dumps({{'is':r1,'oos':r2}}))\n"
        )
    else:
        # Two different modules - need two separate runs
        with open(BT_FILE, "w", encoding="utf-8") as f:
            f.write(is_src)
        r1_result = subprocess.run(
            ["python", "-c",
             f"import sys,json; sys.path.insert(0,r'D:\\QClaw_Trading'); "
             f"from backtest_integrated_v3 import load_all_data,run_oos; "
             f"etfs,series,ohlc,code_cat,all_weeks,atr=load_all_data(); "
             f"r1=run_oos(etfs,series,ohlc,code_cat,all_weeks,atr,{is_s},{is_e},True,no_dedup={str(no_dedup)}); "
             f"print(json.dumps({{'is':r1,'oos':None}}))\n"
            ],
            capture_output=True, text=True, encoding="utf-8",
            cwd=r"D:\QClaw_Trading", timeout=120
        )
        # Restore original before next patch
        with open(BT_FILE, "w", encoding="utf-8") as f:
            f.write(oos_src)
        r2_result = subprocess.run(
            ["python", "-c",
             f"import sys,json; sys.path.insert(0,r'D:\\QClaw_Trading'); "
             f"from backtest_integrated_v3 import load_all_data,run_oos; "
             f"etfs,series,ohlc,code_cat,all_weeks,atr=load_all_data(); "
             f"r2=run_oos(etfs,series,ohlc,code_cat,all_weeks,atr,{oos_s},{oos_e},True,no_dedup={str(no_dedup)}); "
             f"print(json.dumps({{'is':None,'oos':r2}}))\n"
            ],
            capture_output=True, text=True, encoding="utf-8",
            cwd=r"D:\QClaw_Trading", timeout=120
        )
        # Restore original
        with open(BT_FILE, "w", encoding="utf-8") as f:
            f.write(orig_src)
        try:
            r1 = json.loads(r1_result.stdout.strip()) if r1_result.returncode == 0 else {"is": None}
            r2 = json.loads(r2_result.stdout.strip()) if r2_result.returncode == 0 else {"oos": None}
            return {"is": r1.get("is"), "oos": r2.get("oos"),
                    "error": (r1_result.stderr+r2_result.stderr)[:200] if r1_result.returncode != 0 or r2_result.returncode != 0 else None}
        except:
            return {"is": None, "oos": None, "error": (r1_result.stdout+r2_result.stdout)[:200]}

    test_script = r"D:\QClaw_Trading\_bt_test.py"
    with open(test_script, "w", encoding="utf-8") as f:
        f.write(script)
    try:
        result = subprocess.run(
            ["python", test_script],
            capture_output=True, text=True, encoding="utf-8",
            cwd=r"D:\QClaw_Trading", timeout=120
        )
        # Restore original source
        with open(BT_FILE, "w", encoding="utf-8") as f:
            f.write(orig_src)
        if result.returncode != 0:
            return {"is": None, "oos": None, "error": result.stderr[:300]}
        try:
            return json.loads(result.stdout.strip())
        except:
            return {"is": None, "oos": None, "error": result.stdout[:300]}
    finally:
        if os.path.exists(test_script):
            try: os.remove(test_script)
            except: pass

# === 主流程 ===
print("="*60)
print("  稳健性 & 防过拟合综合评测 v3")
print("  策略: 周线动量ETF v4.6.3")
print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("="*60)

# Load data to get indices
sys.path.insert(0, r"D:\QClaw_Trading")
from backtest_integrated_v3 import load_all_data
etfs, series, ohlc, code_cat, all_weeks, atr = load_all_data()
years = sorted(set(w[:4] for w in all_weeks))
print(f"数据: {len(series)}只ETF, {len(all_weeks)}周 ({all_weeks[0]} ~ {all_weeks[-1]})")
print(f"覆盖年份: {years[0]}~{years[-1]}")

def wi(y):
    for i,w in enumerate(all_weeks):
        if w.startswith(str(y)): return i
is_start = wi(2017); is_end = wi(2023); oos_start = is_end; oos_end = len(all_weeks)
print(f"IS: {all_weeks[is_start][:10]} ~ {all_weeks[is_end-1][:10]}")
print(f"OOS: {all_weeks[oos_start][:10]} ~ {all_weeks[-1][:10]}")
print()

# === 基准测试 ===
print("获取基准...")
base = patch_and_run({}, is_start, is_end, {}, oos_start, oos_end, no_dedup=True)
base_is = base["is"]; base_oos = base["oos"]
if base_is is None:
    print(f"基准失败: {base.get('error', 'unknown')}")
    sys.exit(1)
print(f"基准 IS:  年化={base_is['ann_ret']:+.2f}% DD={base_is['max_dd']:.1f}% 夏普={base_is['sharpe']:.3f}")
print(f"基准 OOS: 年化={base_oos['ann_ret']:+.2f}% DD={base_oos['max_dd']:.1f}% 夏普={base_oos['sharpe']:.3f}")

# ============================================================
# 检验1: 参数扰动
# ============================================================
print("\n" + "="*60)
print("检验1: 参数扰动 (Parameter Perturbation)")
print("="*60)

param_cases = [
    ("基准",              {}),
    ("w1-20%",            {"DEF_SC_W1": "0.32", "DEF_SC_W3": "0.44", "DEF_SC_W8": "0.24"}),
    ("w1+20%",            {"DEF_SC_W1": "0.48", "DEF_SC_W3": "0.36", "DEF_SC_W8": "0.16"}),
    ("w3-20%",            {"DEF_SC_W1": "0.44", "DEF_SC_W3": "0.32", "DEF_SC_W8": "0.24"}),
    ("w3+20%",            {"DEF_SC_W1": "0.36", "DEF_SC_W3": "0.48", "DEF_SC_W8": "0.16"}),
    ("w8-20%",            {"DEF_SC_W1": "0.44", "DEF_SC_W3": "0.44", "DEF_SC_W8": "0.16"}),
    ("w8+20%",            {"DEF_SC_W1": "0.36", "DEF_SC_W3": "0.36", "DEF_SC_W8": "0.24"}),
    ("LB=2",              {"DEF_LB": "2"}),
    ("LB=4",              {"DEF_LB": "4"}),
    ("dev=10%",           {"DEF_MAX_DEV": "0.10"}),
    ("dev=20%",           {"DEF_MAX_DEV": "0.20"}),
    ("ATR=0.75",          {"DEF_ATR_F": "0.75"}),
    ("ATR=0.95",          {"DEF_ATR_F": "0.95"}),
    # vol_skip 参数由 weekly_scan_v4.py 单独处理，此处不适用
    ("top=2",             {"DEF_TOP_N": "2"}),
    ("top=4",             {"DEF_TOP_N": "4"}),
]

results1 = []
print(f"\n{'场景':<18} {'IS年化':>8} {'IS-DD':>7} {'IS夏普':>7} {'OOS年化':>8} {'OOS-DD':>7} {'OOS夏普':>8}")
print("-" * 72)
for label, patch in param_cases:
    t0 = time.time()
    r = patch_and_run(patch, is_start, is_end, patch, oos_start, oos_end, no_dedup=True)
    t1 = time.time()
    if r["is"] is None:
        print(f"{label:<18} ERROR: {r.get('error', 'unknown')[:50]}")
        continue
    ri = r["is"]; ro = r["oos"]
    results1.append({"label": label, **ri, **ro})
    print(f"{label:<18} {ri['ann_ret']:>+8.2f} {ri['max_dd']:>7.1f}% {ri['sharpe']:>7.3f} "
          f"{ro['ann_ret']:>+8.2f} {ro['max_dd']:>7.1f}% {ro['sharpe']:>8.3f}  ({t1-t0:.0f}s)")

oos_anns = [r["ann_ret"] for r in results1[1:]]
oos_pos = sum(1 for a in oos_anns if a > 0)
oos_rate = oos_pos / len(oos_anns) * 100
min_oos = min(oos_anns)
drop = (base_oos['ann_ret'] - min_oos) / abs(base_oos['ann_ret']) * 100 if base_oos['ann_ret'] != 0 else 0
print(f"\nOOS正收益: {oos_pos}/{len(oos_anns)} = {oos_rate:.0f}%")
print(f"OOS最大回落: {min_oos:+.2f}% (基准{base_oos['ann_ret']:+.2f}%, 降{drop:.1f}%)")
if oos_rate >= 90 and drop < 50:
    print("结论: [OK] PASS - 参数扰动下稳健")
elif oos_rate >= 70:
    print("结论: [!!]  MARGINAL - 大部分参数仍正收益")
else:
    print("结论: [NG] FAIL - 参数扰动下大面积失效")

# ============================================================
# 检验2: 赛道去重 vs 无去重
# ============================================================
print("\n" + "="*60)
print("检验2: 赛道去重价值 (Dedup Impact)")
print("="*60)
r_dedup = patch_and_run({}, is_start, is_end, {}, oos_start, oos_end, no_dedup=False)
r_nodedup = patch_and_run({}, is_start, is_end, {}, oos_start, oos_end, no_dedup=True)
if r_dedup["is"] and r_nodedup["is"]:
    print(f"\n有去重 IS:  年化={r_dedup['is']['ann_ret']:+.2f}% DD={r_dedup['is']['max_dd']:.1f}% 夏普={r_dedup['is']['sharpe']:.3f}")
    print(f"有去重 OOS: 年化={r_dedup['oos']['ann_ret']:+.2f}% DD={r_dedup['oos']['max_dd']:.1f}% 夏普={r_dedup['oos']['sharpe']:.3f}")
    print(f"无去重 IS:  年化={r_nodedup['is']['ann_ret']:+.2f}% DD={r_nodedup['is']['max_dd']:.1f}% 夏普={r_nodedup['is']['sharpe']:.3f}")
    print(f"无去重 OOS: 年化={r_nodedup['oos']['ann_ret']:+.2f}% DD={r_nodedup['oos']['max_dd']:.1f}% 夏普={r_nodedup['oos']['sharpe']:.3f}")
    diff = r_nodedup['oos']['ann_ret'] - r_dedup['oos']['ann_ret']
    print(f"\n无去重 vs 有去重 OOS差值: {diff:+.2f}%")
    if diff > 3:
        print("结论: [OK] 无去重显著更优，保持v4.6.3无去重设置")
    elif diff > 0:
        print("结论: [!!]  无去重略优")
    else:
        print("结论: [!!]  有去重更优，需重新评估")
else:
    print(f"去重测试失败: {r_dedup.get('error', '')} {r_nodedup.get('error', '')}")

# ============================================================
# 检验3: 年度分段绩效
# ============================================================
print("\n" + "="*60)
print("检验3: 年度分段绩效 (Yearly Performance)")
print("="*60)
results3 = []
print(f"\n{'年份':>6} {'周数':>4} {'年化':>8} {'最大DD':>7} {'夏普':>6} {'买入':>4} {'胜率':>6} {'状态'}")
print("-" * 58)
loss_yrs = 0
for yr in years:
    si = wi(yr)
    if si is None: continue
    ei = si
    while ei < len(all_weeks) and all_weeks[ei].startswith(str(yr)):
        ei += 1
    if ei - si < 20: continue
    r = patch_and_run({}, si, ei if ei < len(all_weeks) - 1 else ei - 1, {}, si, ei, no_dedup=True)
    if r["is"] is None: continue
    ri = r["is"]
    status = "[OK]" if ri["ann_ret"] > 0 else "[NG]"
    if ri["ann_ret"] <= 0: loss_yrs += 1
    results3.append({"year": yr, **ri})
    print(f"{yr:>6} {ri['n_weeks']:>4} {ri['ann_ret']:>+8.2f} {ri['max_dd']:>7.1f}% "
          f"{ri['sharpe']:>6.3f} {ri['n_buys']:>4} {ri['win_rate']:>6.1f}% {status}")

loss_rate = loss_yrs / len(results3) * 100 if results3 else 100
print(f"\n总年份: {len(results3)}年, 亏损年份: {loss_yrs}年 ({loss_rate:.0f}%)")
if loss_rate <= 20:
    print("结论: [OK] PASS - 亏损年份≤20%，跨环境稳健")
elif loss_rate <= 35:
    print("结论: [!!]  MARGINAL - 亏损年份比例偏高")
else:
    print("结论: [NG] FAIL - 亏损年份过多")

# ============================================================
# 检验4: Walk Forward
# ============================================================
print("\n" + "="*60)
print("检验4: 滚动Walk Forward")
print("="*60)
train_wks = 52; val_wks = 26; step_wks = 13
wf_results = []
print(f"\n{'训练期':>22} {'验证期':>22} {'训练年化':>9} {'验证年化':>9} {'验证夏普':>8} {'状态'}")
print("-" * 82)
idx = 0
while idx + train_wks + val_wks <= len(all_weeks):
    t_end = idx + train_wks
    v_end = min(t_end + val_wks, len(all_weeks) - 1)
    if v_end <= t_end: break
    tr_label = f"{all_weeks[idx][:7]}~{all_weeks[t_end-1][:7]}"
    va_label = f"{all_weeks[t_end][:7]}~{all_weeks[v_end-1][:7]}"
    r_tr = patch_and_run({}, idx, t_end, {}, idx, t_end, no_dedup=True)
    r_va = patch_and_run({}, t_end, v_end, {}, t_end, v_end, no_dedup=True)
    if r_tr["is"] is None or r_va["is"] is None:
        idx += step_wks; continue
    status = "[OK]" if r_va["is"]["ann_ret"] > 0 else "[NG]"
    wf_results.append({"train": tr_label, "val": va_label,
                       **r_tr["is"], **r_va["is"]})
    print(f"{tr_label:<22} {va_label:<22} {r_tr['is']['ann_ret']:>+9.2f} "
          f"{r_va['is']['ann_ret']:>+9.2f} {r_va['is']['sharpe']:>8.3f} {status}")
    idx += step_wks

val_pos = sum(1 for r in wf_results if r["ann_ret"] > 0)
val_rate = val_pos / len(wf_results) * 100 if wf_results else 0
print(f"\n验证期正收益: {val_pos}/{len(wf_results)} = {val_rate:.0f}%")
if val_rate >= 70:
    print("结论: [OK] PASS - 滚动样本外验证稳健")
elif val_rate >= 50:
    print("结论: [!!]  MARGINAL - 部分滚动区间亏损")
else:
    print("结论: [NG] FAIL - 样本外大面积失效")

# ============================================================
# 检验5: 参数高原 (w1 vs w3)
# ============================================================
print("\n" + "="*60)
print("检验5: 参数高原 (w1 vs w3 网格)")
print("="*60)
w1s = [0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
w3s = [0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
hdr5 = "w1\\w3"
print(f"\n{hdr5:>8}", end="")
for w3 in w3s: print(f" {w3:>7}", end="")
print()
print("-" * 55)
grid = []
for w1 in w1s:
    row = []
    print(f"{w1:>8.2f}", end="")
    for w3 in w3s:
        w8 = round(1 - w1 - w3, 2)
        if w8 < 0 or w8 > 0.5:
            print(f" {'N/A':>7}", end="")
            row.append(None); continue
        r = patch_and_run({"DEF_SC_W1": str(w1), "DEF_SC_W3": str(w3), "DEF_SC_W8": str(w8)},
                          is_start, is_end,
                          {"DEF_SC_W1": str(w1), "DEF_SC_W3": str(w3), "DEF_SC_W8": str(w8)},
                          oos_start, oos_end, no_dedup=True)
        ann = r["oos"]["ann_ret"] if r["oos"] else None
        print(f" {ann:>+7.1f}" if ann is not None else f" {'--':>7}", end="")
        row.append(ann)
    grid.append(row)
    print()

flat = [v for row in grid for v in row if v is not None]
if flat:
    mx = max(flat)
    plateau = sum(1 for v in flat if v >= mx * 0.9)
    avg = sum(flat) / len(flat)
    psi = mx / avg if avg > 0 else 0
    print(f"最优OOS年化: {mx:+.2f}%")
    print(f"高原区(≥90%最优): {plateau}/{len(flat)} ({plateau/len(flat)*100:.0f}%)")
    print(f"PSI指数(最优/均值): {psi:.2f}")
    if plateau / len(flat) >= 0.4 and psi < 2.5:
        print("结论: [OK] PASS - 存在明显高原区，参数非尖锐峰值")
    elif plateau / len(flat) >= 0.25:
        print("结论: [!!]  MARGINAL - 部分高原区，局部有敏感区域")
    else:
        print("结论: [NG] FAIL - 仅有尖锐峰值，参数高度敏感")

# ============================================================
# 检验6: 交易成本（估算）
# ============================================================
print("\n" + "="*60)
print("检验6: 交易成本估算 (Cost Estimation)")
print("="*60)
n_buys_is = base_is.get("n_buys", 0)
n_buys_oos = base_oos.get("n_buys", 0)
n_weeks_is = base_is.get("n_weeks", 1)
n_weeks_oos = base_oos.get("n_weeks", 1)
buy_per_wk_is = n_buys_is / n_weeks_is if n_weeks_is > 0 else 0
buy_per_wk_oos = n_buys_oos / n_weeks_oos if n_weeks_oos > 0 else 0

print(f"\n基准交易频率: IS {buy_per_wk_is:.2f}次/周, OOS {buy_per_wk_oos:.2f}次/周")
print(f"基准总买入次数: IS {n_buys_is}次, OOS {n_buys_oos}次")

for slip_bp in [3, 5, 8, 10, 15]:
    slip = slip_bp / 10000
    # 单次买卖总成本 ≈ 2 * slip (买+卖)
    cost_per_trade = 2 * slip
    annual_cost_is = buy_per_wk_is * 52 * cost_per_trade * 100  # % of capital
    annual_cost_oos = buy_per_wk_oos * 52 * cost_per_trade * 100
    adj_is = base_is["ann_ret"] - annual_cost_is
    adj_oos = base_oos["ann_ret"] - annual_cost_oos
    flag = " ← 失效" if adj_oos <= 0 else ""
    print(f"滑点{slip_bp:>3}bp(年化-IS{-annual_cost_is:>5.1f}%, -OOS{-annual_cost_oos:>5.1f}%): "
          f"IS_adj={adj_is:>+6.2f}% OOS_adj={adj_oos:>+6.2f}%{flag}")

# 找临界滑点
max_slip = 0
for slip_bp in range(1, 100):
    slip = slip_bp / 10000
    cost_per_trade = 2 * slip
    annual_cost_oos = buy_per_wk_oos * 52 * cost_per_trade * 100
    if base_oos["ann_ret"] - annual_cost_oos > 0:
        max_slip = slip_bp
print(f"\nOOS极限滑点容忍: ~{max_slip}bp (约±{max_slip/10:.1f}‰)")
if max_slip >= 15:
    print("结论: [OK] PASS - 可承受15bp+滑点，实盘稳健")
elif max_slip >= 8:
    print("结论: [!!]  MARGINAL - 8-15bp滑点边际，注意执行质量")
else:
    print("结论: [NG] FAIL - 滑点边际过薄(<8bp)")

# ============================================================
# 综合汇总
# ============================================================
print("\n" + "="*60)
print("  综合稳健性汇总")
print("="*60)
print(f"""
┌────────────────────┬──────────────────────────────────────────────┐
│ 基准绩效            │ IS: {base_is['ann_ret']:>+6.2f}% / {base_is['sharpe']:.3f}sharpe / DD{base_is['max_dd']:>5.1f}% │
│                    │ OOS:{base_oos['ann_ret']:>+6.2f}% / {base_oos['sharpe']:.3f}sharpe / DD{base_oos['max_dd']:>5.1f}% │
├────────────────────┼──────────────────────────────────────────────┤
│ 参数扰动            │ OOS正收益: {oos_pos}/{len(oos_anns)}={oos_rate:.0f}% / 最大回落: {drop:.1f}% │
│ 年度绩效            │ 亏损年份: {loss_yrs}/{len(results3)}={loss_rate:.0f}%                       │
│ Walk Forward       │ 验证正收益: {val_pos}/{len(wf_results)}={val_rate:.0f}%                      │
│ 参数高原            │ 高原区{plateau}/{len(flat)}={plateau/len(flat)*100:.0f}% / PSI{psi:.2f}               │
│ 成本容忍            │ 极限滑点 ~{max_slip}bp                              │
│ 赛道去重            │ 无vs有 OOS差: {r_nodedup['oos']['ann_ret']-r_dedup['oos']['ann_ret']:+.2f}%(估算)             │
└────────────────────┴──────────────────────────────────────────────┘
""")
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
out = rf"D:\QClaw_Trading\review\robustness_v3_{ts}.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump({
        "timestamp": ts, "strategy": "v4.6.3",
        "base": {"is": base_is, "oos": base_oos},
        "param_perturbation": [{"label": r["label"], "is_ann": r["ann_ret"], "oos_ann": r["ann_ret"]} for r in results1],
        "yearly": [{"year": r["year"], "ann_ret": r["ann_ret"]} for r in results3],
        "walk_forward": [{"train": r["train"], "val": r["val"], "oos_ann": r["ann_ret"]} for r in wf_results],
        "grid_plateau": [[round(v, 2) if v else None for v in row] for row in grid],
        "max_slip_bp": max_slip,
        "dedup_diff": r_nodedup['oos']['ann_ret'] - r_dedup['oos']['ann_ret']
    }, f, ensure_ascii=False, indent=2, default=str)
print(f"结果已保存: {out}")
print("\n[OK] 全部检验完成！")
