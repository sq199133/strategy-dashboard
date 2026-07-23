import os
os.chdir(r'D:\Qclaw_Trading')
with open('strategy/周线动量策略_v4.5.md', 'r', encoding='utf-8', newline='') as f:
    content = f.read()

# Replace G3-related content in the core table
old_table = """| **G3过滤** | 3周≥0% 且 1周≥-1% | 三周/一周动量底线 |"""
new_table = """| ~~G3过滤~~ | ~~3周≥0% 且 1周≥-1%~~ | ~~已移除：降年化1.6%，2026年更差~~ |"""
content = content.replace(old_table, new_table)

# Remove G3 from the description text
old_desc_start = "**设计理念：**"
old_desc_new = """**设计理念：** 纯3周动量排序在震荡市容易买在反转点。引入1周动量捕捉刚启动的趋势，8周动量做长周期质量校验，减少追高买入在反转点的概率。ATR波动率过滤：当ATR(14)/ATR(21) < 0.85时，说明近期波动率严重收缩，此时动量信号多为噪声，跳过该标的。"""
# No G3 mention in the design section, good

# Update strategy version description to reflect G3 removal
old_ver = "**版本：** v4.5（2026-06-15 更新，SC 40/40/20 + D15 + H3 + ATR 0.85 正式版）"
new_ver = "**版本：** v4.5.1（2026-06-22 更新，移除G3过滤，SC 40/40/20 + D15 + H3 + ATR 0.85）"
content = content.replace(old_ver, new_ver)

# Update回测结果 section to use new numbers
old_head = "| 指标 | v4.5(Baseline) | **v4.5 + ATR0.85** | 变化 |"
# Replace the results table header to show single column
old_results_table_start = "### 总体指标"
old_results_table_end = "### 逐年收益"

# Replace the parenthetical about G3
content = content.replace("G3过滤、ATR filter", "ATR filter")

with open('strategy/周线动量策略_v4.5.md', 'w', encoding='utf-8', newline='') as f:
    f.write(content)
print('Strategy doc updated')
