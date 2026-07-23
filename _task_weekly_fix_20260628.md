# 周线 W25 修复 - 2026-06-28

## 问题

2026-W25（端午节周）在 `history_long_v2/` 所有文件中缺失：
- 6/15-18 四个交易日 → ISO W25
- 6/19(端午,周五) 休市，无周五触发
- 旧聚合器只认 `weekday()==4` → 永远等不到周五，整周被跳过

## 根因

旧 `daily_to_weekly` 逻辑：`weekday()==4` 关闭当周 → 6/19 休市无交易 → 无触发 → W25 消失。

## 修复

### 1. 聚合算法升级（`daily_to_weekly`）
- 新增 `gap >= 2 calendar days` 检测：跨假期断裂时，在 gap 前一天关闭
- `just_closed` 标志：避免 Fri 关闭 + Mon gap 再关一次（双重关闭）
- ISO 周号统一用 `isocalendar()`，不再用 `split("-")[1]`（后者得月份）

### 2. 一次性全量重生成
- 脚本：`D:\QClaw_Trading\_weekly_gen.py`
- 结果：195/195 全部修复，939 个重复条目清除
- 每只 ETF 从 ~1271 条压缩到 ~655 条（去除重复）

### 3. 同步更新 `maintain_etf_data.py`
- `daily_to_weekly()` 替换为新逻辑
- 新增 `_close_week()` 辅助函数
- `sync_weekly_for_code()` 加入去重逻辑

### 4. 文档
- `_DATA_GUARDIAN_.md` 更新，记录所有 bug 和修复方式

## 验证

```
【周线】
  已覆盖:      195
  周数不足:    0
  缺失:        0
  总记录数:    55,211

159928 W24/W25/W26:
  2026-W24 date=2026-06-12 close=0.657
  2026-W25 date=2026-06-18 close=0.623  ← 修复后新增
  2026-W26 date=2026-06-26 close=0.603
```
