#!/usr/bin/env python3
"""检查2025年逐周权益，找出收益偏低的原因"""
import json

fp = r"D:\QClaw_Trading\backtest_results\bt_v4_2_5_21_5_10_3_20260607_000555.json"
d = json.load(open(fp, 'r', encoding='utf-8'))

print("2025年逐周权益：")
print(f"{'Week':10} {'Equity':10} {'Hold':>5}")
print("-" * 30)

for e in d['equity']:
    if e['w'].startswith('2025-W'):
        print(f"{e['w']:10} {e['eq']:10.4f} {e['nh']:>5}")

# 计算2025年收益率
eq_2025 = [e['eq'] for e in d['equity'] if e['w'].startswith('2025-W')]
if len(eq_2025) >= 2:
    ret = (eq_2025[-1] / eq_2025[0] - 1) * 100
    print(f"\n2025年收益率：{ret:+.1f}%")
    print(f"起始权益：{eq_2025[0]:.4f}")
    print(f"结束权益：{eq_2025[-1]:.4f}")
