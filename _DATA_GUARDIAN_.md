# _DATA_GUARDIAN_.md — ETF 数据守护规则

> 上次更新：2026-06-29

---

## 核心规则

### 交易日校验（2026-06-29 新增）

**所有数据读写必须校验交易日**，禁止直接信任 API 返回的日期。

判断函数：`maintain_etf_data.py` 中的 `is_trading_day(dt: date)`

```
规则：
  weekday >= 5 (周六/周日) → 非交易日
  HOLIDAYS[year] → 非交易日（节假日）
  COMPENSATORY_DAYS[year] → 交易日（调休上班日）
```

**已覆盖节假日（2024-2027）**：元旦、春节、清明、劳动节、端午、中秋国庆。
**调休上班日**：已声明（如2026-02-22/02-28/04-26等）。

**过滤函数**：`filter_trading_days(records)` → 去除所有非交易日记录。

### 数据更新规范

增量更新（追加最新记录）：`python maintain_etf_data.py incremental`
- 自动过滤非交易日
- 只追加 `date > 本地最后日期` 的记录
- 自动同步周线

---

## 核心规则

### 周线聚合逻辑（必须遵守）

**正确逻辑**：`history_long_v2/` 中的周线必须用以下规则生成，禁止使用其他方式：

```
week_data 装入当周交易日
触发关闭条件：
  1. dt.weekday() == 4（周五，正常收周）
  2. gap >= 2 日且 week_data 非空（假期/周末断裂，anchor=gap前日）
  3. i == last（强制收尾）
  4. just_closed 标志防止 Fri→Mon 双重关闭
```

**关键函数**：`maintain_etf_data.py` 中的 `daily_to_weekly()` + `_close_week()`

### ISO 周号必须用 isocalendar()

⚠️ 禁止：`anchor_record["date"].split("-")[1]` → 得到**月份**，不是周数！

✅ 必须：`dt.isocalendar()` → `(iso_yr, iso_wk, iso_dow)`

---

## 已修复的 Bug

### Bug 1：端午节 W25 缺失（2026-06-28 修复）

**症状**：2026-W25 周线在每周文件中不存在，导致端午那周数据空洞。

**根因**：旧 `daily_to_weekly` 只按 `weekday()==4`（周五）关闭周。端午假期 6/19 是周五，但无交易（休市），整个 W25 没有一个交易日是周五 → 永远等不到触发，周被跳过。

**修复**：
- 新增 `gap >= 2 日` 检测：跨假期间隔 ≥ 2 天时，在 gap 前一天关闭当周
- `just_closed` 标志：周五已关闭则跳过 gap 检测（避免 Fri 关闭 + Mon gap 再关一次）

### Bug 2：双重关闭导致重复条目

**症状**：每个 W 号出现 2 次，939 个重复条目（跨 195 文件）。

**根因**：周五关闭后，`gap >= 2` 在下一个周一再次触发，`_close_week` 用同一 anchor 再写一次。

**修复**：`just_closed` 标志使 gap 检测在刚关闭后跳过本次。

### Bug 3：ISO 周号用 split 得到月份

**症状**：旧代码 `iso_yr, iso_wk, iso_dow = dt.isocalendar()` 后又做 `r["date"].split("-")[1]` → 月份数字覆盖了 ISO 周数。

**修复**：统一用 `isocalendar()` 的结果生成 `"w"` 标签。

---

## 周线生成器位置

- 一次性修复脚本：`D:\QClaw_Trading\_weekly_gen.py`（运行一次即可）
- 日常维护：`D:\QClaw_Trading\maintain_etf_data.py` 的 `sync-weekly` 子命令
- 单元测试：`D:\QClaw_Trading\verify_w25.py`

---

## 修复执行记录

| 日期 | 操作 | 结果 |
|------|------|------|
| 2026-06-28 | `_weekly_gen.py` 全量重生成 | 195/195 OK，939 重复清除 |
| 2026-06-28 | `maintain_etf_data.py check` | 日线 259,561 条，周线 55,211 条，0 缺失 |
