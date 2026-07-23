# PER分位择时策略说明

## 策略思路

### 核心逻辑
PER（市盈率）分位择时策略基于一个核心假设：**估值回归**。

- **低估时买入**：当PER处于历史低分位（如<20%），市场被低估，加仓
- **高估时卖出**：当PER处于历史高分位（如>80%），市场被高估，减仓

### 策略类型

#### 1. 阈值策略（离散）
```
PER分位     仓位
≤10%       100%
10-20%      80%
20-50%      50%
50-80%      20%
80-90%      10%
>90%        0%
```

#### 2. 线性策略（连续）
```
仓位 = (100 - PER分位) / 100
```

#### 3. Sigmoid策略（平滑过渡）
```
仓位 = 1 / (1 + e^((PER分位 - 50) / 20))
```
- 分位50%时，仓位50%
- 分位越低，仓位越高，平滑过渡

### 适用标的

| 类型 | 代表ETF | 适用性 | 说明 |
|------|---------|--------|------|
| 宽基A股 | 沪深300、中证500、中证1000 | ✅ 最佳 | 历史长、估值中枢相对稳定 |
| 红利策略 | 红利ETF、红利低波 | ✅ 好 | 估值逻辑清晰 |
| 行业ETF | 科技、医药、消费 | ⚠️ 谨慎 | 需考虑行业周期，PE中枢可能漂移 |
| 周期行业 | 有色、化工、银行 | ❌ 不适用 | 盈利波动大，PE可能反向 |
| 跨境QDII | 纳斯达克、德国DAX | ⚠️ 谨慎 | 需用对应市场指数估值 |
| 商品ETF | 黄金、原油 | ❌ 不适用 | 无PE概念 |

## 数据需求

### 必需数据

#### 1. ETF历史价格数据（已有）
- 路径: `D:/QClaw_Trading/data/history/` 或 `history_long/`
- 格式: JSON
- 字段: date, open, close, high, low, vol, amount, chg

#### 2. PE估值数据（需获取）
- 路径: `D:/QClaw_Trading/data/pe_data/`
- 格式: JSON
- 字段: date, pe, pb (可选)

### PE数据获取途径

#### 方案一：中证指数公司（官方，推荐）
- 网址: https://www.csindex.com.cn/zh-CN/indices/index-list
- 提供数据: 指数PE、PB、股息率
- 优点: 权威、免费
- 缺点: 需手动下载

#### 方案二：乐咕乐股
- 网址: https://legulegu.com/stockdata/market-pe
- 提供数据: 市场PE、PB分位图
- 优点: 可视化好，数据直观
- 缺点: 需注册

#### 方案三：果仁网
- 网址: https://guorn.com/
- 提供数据: 指数估值、回测
- 优点: 数据全面
- 缺点: 部分功能付费

#### 方案四：第三方API
- 聚宽、米筐、掘金等量化平台
- 优点: 数据接口完善
- 缺点: 需付费

### PE数据文件示例

```json
[
    {"date": "2020-01-02", "pe": 12.5, "pb": 1.45},
    {"date": "2020-01-03", "pe": 12.6, "pb": 1.46},
    {"date": "2020-01-06", "pe": 12.4, "pb": 1.44},
    ...
]
```

文件命名: `sh000300_pe.json`（对应沪深300指数）

## 策略参数

### 分位阈值
```python
PER_LOW_THRESHOLD = 20      # 低分位阈值
PER_HIGH_THRESHOLD = 80     # 高分位阈值
PER_EXTREME_LOW = 10        # 极低分位
PER_EXTREME_HIGH = 90       # 极高分位
```

### 滚动窗口
```python
PERCENTILE_WINDOW = 252     # 1年（252交易日）
PERCENTILE_WINDOW_LONG = 756  # 3年
```

选择建议：
- **1年窗口**：适合捕捉中期估值波动，信号更灵活
- **3年窗口**：更稳定，但信号滞后
- **5年窗口**：适合大周期择时

### 交易参数
```python
TRANSACTION_COST = 0.0003   # 交易成本（万三）
SLIPPAGE = 0.0001           # 滑点
POSITION_SIZE = 0.3         # 单次调仓比例
```

## 使用方法

### 1. 准备数据
```bash
# 创建PE数据目录
mkdir D:\QClaw_Trading\data\pe_data

# 放置PE数据文件
# sh000300_pe.json  (沪深300)
# sh000905_pe.json  (中证500)
# sh000852_pe.json  (中证1000)
```

### 2. 运行策略
```bash
cd D:\QClaw_Trading\strategies
python per_percentile_strategy.py
```

### 3. 策略调用
```python
from per_percentile_strategy import DataLoader, SignalGenerator

# 加载数据
loader = DataLoader()
price_df = loader.load_etf_history('510300')
pe_df = loader.load_pe_data('sh000300')

# 计算分位
from per_percentile_strategy import PERPercentileCalculator
calculator = PERPercentileCalculator(window=252)
pe_stats = calculator.get_pe_stats(pe_df['pe'])

# 生成信号
generator = SignalGenerator()
position = generator.generate_position_signal(pe_stats['percentile'])
```

## 回测指标

策略回测输出以下指标：

| 指标 | 说明 |
|------|------|
| 总收益率 | 策略期间总收益 |
| 年化收益率 | 换算年化收益 |
| 波动率 | 年化波动率 |
| 夏普比率 | 风险调整后收益 |
| 最大回撤 | 最大亏损幅度 |
| 交易次数 | 调仓次数 |
| 超额收益 | 相对基准超额收益 |

## 注意事项

### 1. PER的局限性

#### 周期性行业
- 银行、有色、化工等行业盈利波动大
- 盈利高点PE可能反而在低点
- **不适合用PE分位择时**

#### 成长股
- 科技、医药等高成长行业
- PE中枢可能持续上移
- 建议结合PEG使用

#### 负盈利
- 指数成分股可能亏损
- PE为负值时需特殊处理

### 2. 分位漂移问题

- **历史分位不代表未来**
- 估值中枢可能随市场环境变化
- 建议：
  - 使用较长时间窗口（3-5年）
  - 结合其他指标（PB、股息率）
  - 定期校准阈值

### 3. 交易成本

- 过于频繁调仓会侵蚀收益
- 建议设置最小调仓阈值（如5%仓位变化）
- 或使用Sigmoid策略平滑过渡

## 策略增强方向

### 1. 多因子融合
- PE分位 + PB分位
- PE分位 + 动量因子
- PE分位 + 宏观因子（利率、流动性）

### 2. 多标轮动
- 沪深300、中证500、中证1000轮动
- 选择估值更低、动量更强的标的

### 3. 止损止盈
- 设置最大回撤止损
- 设置估值修复止盈

### 4. 仓位管理
- Kelly公式优化仓位
- 风险平价配置

## 常见问题

**Q: PE数据哪里下载？**
A: 推荐中证指数公司官网，或乐咕乐股网站。

**Q: 为什么周期行业不适用？**
A: 周期行业盈利波动大，PE与股价可能反向。高PE反而是买点，低PE是卖点。

**Q: 分位窗口选多长？**
A: 建议3-5年，覆盖完整牛熊周期。窗口太短信号不稳定，太长反应滞后。

**Q: 可以用于个股吗？**
A: 可以，但个股受业绩影响大，需结合盈利质量、成长性等指标。

---

作者: 策略测算
更新: 2026-05-11
