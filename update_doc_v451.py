import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

with open('strategy/周线动量策略_v4.5.md', 'r', encoding='utf-8') as f:
    doc = f.read()

# Replace the baseline results table header
old_header = "| 指标 | v4.5(Baseline) | **v4.5 + ATR0.85** | 变化 |"
new_header = "| 指标 | v4.5(有G3) | **v4.5.1(无G3)** | 变化 |"
doc = doc.replace(old_header, new_header)

# Fix results row
old_row1 = "| 总收益 | +1237% | **+1241%** | 持平 |"
new_row1 = "| 总收益 | +1245% | **+1465%** | +220%（放弃G3） |"
doc = doc.replace(old_row1, new_row1)

old_row2 = "| 年化 | +18.5% | **+18.6%** | — |"
new_row2 = "| 年化 | +18.5% | **+19.7%** | +1.2% |"
doc = doc.replace(old_row2, new_row2)

old_row3 = "| 最大回撤 | -16.4% | **-16.4%** | 持平 |"
new_row3 = "| 最大回撤 | -16.4% | **-21.3%** | +4.9%（回撤可控） |"
doc = doc.replace(old_row3, new_row3)

old_row4 = "| 夏普 | 1.03 | **1.03** | — |"
new_row4 = "| 夏普 | 1.03 | **1.06** | +0.03 |"
doc = doc.replace(old_row4, new_row4)

# Fix the results section
old_results_start = "### 总体指标\n\n| 指标 | v4.5(有G3) | **v4.5.1(无G3)** | 变化 |"
new_results_start = "### 总体指标（2026-06-22更新：移除G3过滤）\n\n| 指标 | v4.5(有G3) | **v4.5.1(无G3)** | 变化 |"
doc = doc.replace(old_results_start, new_results_start)

# Update逐年收益 table
old_2025 = "| 2025 | +83.1% | **+83.1%** | -- |"
new_2025 = "| 2025 | +83.1% | **+100.7%** | 牛市释放 |"
doc = doc.replace(old_2025, new_2025)

old_2026 = "| 2026 | +7.1% | **+7.1%** | -- |"
new_2026 = "| 2026 | +7.1% | **+7.9%** | 震荡表现略优 |"
doc = doc.replace(old_2026, new_2026)

# Update backtest 4.5 column to 4.5.1 in yearly table
doc = doc.replace("**v4.5 + ATR0.85**", "**v4.5.1(无G3)**")

with open('strategy/周线动量策略_v4.5.md', 'w', encoding='utf-8', newline='') as f:
    f.write(doc)
print('Strategy doc updated with correct v4.5.1 numbers')
