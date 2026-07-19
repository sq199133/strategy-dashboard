# QClaw_Trading — 量化交易工作目录

## 分支策略

```
main            ← 核心代码 + 策略脚本（默认分支，标签版本）
├── data-main   ← 历史行情数据（LFS，仅每周更新时合入data-main）
│   └── data/history/*.json (LFS)
│   └── data/history_long_v2/*.json (LFS)
├── rsrs-engine ← RSRS策略引擎
└── features/*  ← 实验性策略分支
```

### 规则

- **main**: 稳定可运行的代码 + 文档。push前必须能跑通
- **data-main**: 仅存储历史数据文件，不存代码。从initial commit分叉出来
- **rsrs-engine**: RSRS引擎模块（`rsrs_engine.py`, `rsrs_daily_output.py`, `signals/`）

### 更新机制

- `data.main` 分支闭源，与 `main` 解耦。数据更新时只合入 `data-main`
- `main` 分支的代码通过绝对路径 `D:\QClaw_Trading\data\history\` 访问数据，不依赖git LFS
