// 综合核实结论 + 生成最终持仓文件
// 
// 核实结果汇总（2026-04-17）：
//
// 【持仓代码核实结论】
// 159681 SZ ✅ = 创业板50ETF鹏华（实时确认，EM数据13.8亿）
// 512770 SH ❌ = 战略新兴ETF华夏（非生物医药，原池错误）
// 512220 SH ❌ = TMTETF景顺（非军工，原池错误）
// 516390 SH ❌ = 新能源车ETF汇添富（名称核实OK，但EM无任何历史K线→疑似已退市/改名）
// 513100 SH ✅ = 纳指ETF国泰（名称核实）
//
// 【当日实际行为】
// 4月17日开盘确实按计划买入了上述5只（含512770/512220/516390）
// 4月17日收盘：
//   512770 战略新兴ETF华夏 2.395→2.395 = ¥0.00 (0.00%)
//   512220 TMTETF景顺 3.235→3.296 = +¥372.10 (+1.88%)
//   516390 新能源车ETF汇添富 1.094→1.093 = -¥18.20 (-0.09%)
//   EM确认该代码2026年无任何K线数据 → 实为异常持仓
//
// 【持仓处理建议】
// 4月18日（周五）继续检查，如516390仍无数据则下周替换为正确的515700
// 512770/512220 策略上按当前实际品种继续跟踪，但需记录真实名称
//
// 【真实名称修正后持仓（最终确认）】
// SZ159681 创业板50ETF鹏华     1.717 开盘 → 1.729 收盘  +0.70%
// SH512770 战略新兴ETF华夏     2.395 开盘 → 2.395 收盘   0.00%
// SH512220 TMTETF景顺         3.235 开盘 → 3.296 收盘  +1.88%
// SH516390 新能源车ETF汇添富   1.094 开盘 → 1.093 收盘  -0.09%
// SH513100 纳指ETF国泰         1.902 开盘 → 1.892 收盘  -0.55%
//
// 【ETF池v4.0修正】
// 512770 → 从池中删除（原为错误名称），生物医药实际应为512290
// 512220 → 从池中删除（原为错误名称），军工实际应为512660
// 516390 → 池中保留但标记⚠️（名称核实有但EM无K线）
// 513100 → 池中标记✅（代码正确，名称记录有误）
// 515700 → 新能源车正确标的（新能源车ETF平安，18.7亿）

const fs = require('fs');
const path = require('path');

const portfolio = {
  updated: '2026-04-17 核实后更新',
  note: '注意：持仓中512770/512220/516390为原池错误代码，详见corrections',
  holdings: [
    {
      code: '159681', market: 'SZ', name: '创业板50ETF鹏华',
      buyDate: '2026-04-17', buyPrice: 1.717, closePrice: 1.729,
      shares: 11600, buyCost: 19917.20, closeValue: 20052.40,
      pnl: 135.20, pnlPct: 0.70,
      status: '⭐⭐买入', note: '核实✅，名称正确，EM规模13.8亿'
    },
    {
      code: '512770', market: 'SH', name: '战略新兴ETF华夏',
      buyDate: '2026-04-17', buyPrice: 2.395, closePrice: 2.395,
      shares: 8300, buyCost: 19878.50, closeValue: 19878.50,
      pnl: 0.00, pnlPct: 0.00,
      status: '⭐⭐买入', note: '⚠️原池误名为生物医药，实际为战略新兴ETF华夏(规模2.5亿)，需关注是否为错误建仓'
    },
    {
      code: '512220', market: 'SH', name: 'TMTETF景顺',
      buyDate: '2026-04-17', buyPrice: 3.235, closePrice: 3.296,
      shares: 6100, buyCost: 19733.50, closeValue: 20105.60,
      pnl: 372.10, pnlPct: 1.88,
      status: '⭐⭐买入', note: '⚠️原池误名为军工ETF，实际为TMTETF景顺(规模1.7亿)，通信+科技主题'
    },
    {
      code: '516390', market: 'SH', name: '新能源车ETF汇添富',
      buyDate: '2026-04-17', buyPrice: 1.094, closePrice: 1.093,
      shares: 18200, buyCost: 19910.80, closeValue: 19892.60,
      pnl: -18.20, pnlPct: -0.09,
      status: '⭐⭐买入', note: '❌名称核实为新能源车ETF汇添富，但东方财富2026年无任何K线数据，疑似退市/改名，优先替换为515700'
    },
    {
      code: '513100', market: 'SH', name: '纳指ETF国泰',
      buyDate: '2026-04-17', buyPrice: 1.902, closePrice: 1.892,
      shares: 10500, buyCost: 19971.00, closeValue: 19866.00,
      pnl: -105.00, pnlPct: -0.53,
      status: '⭐⭐买入', note: '✅代码正确，名称原记录为纳指100ETF，实际为纳指ETF国泰（跟踪纳斯达克100指数）'
    }
  ],
  summary: {
    initialCapital: 100000,
    availableCash: 589.00,
    positionValue: 99795.10,
    totalAssets: 100384.10,
    totalPnl: 384.10,
    totalPnlPct: 0.38,
    positions: 5,
    buyErrors: ['512770(战略新兴非生物医药)', '512220(TMT非军工)', '516390(疑似退市)']
  }
};

fs.writeFileSync(path.join(__dirname, 'portfolio_v2.json'), JSON.stringify(portfolio, null, 2));
console.log('持仓文件已保存 portfolio_v2.json');
console.log(JSON.stringify(portfolio.summary, null, 2));
