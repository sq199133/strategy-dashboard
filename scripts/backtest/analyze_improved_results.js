/**
 * 详细分析反向信号策略的合理性
 */

const fs = require('fs');
const path = require('path');

const INDEX_HISTORY_DIR = 'D:/QClaw_Trading/data/index_history';
const RESULTS_FILE = 'D:/QClaw_Trading/scripts/backtest/improved_sharpe_results.json';
const ETF_POOL_FILE = 'D:/QClaw_Trading/data/etf_pool_v5.json';
const INDEX_NAME_MAP = require('./index_mapping.js');

// 加载数据
const etfPool = JSON.parse(fs.readFileSync(ETF_POOL_FILE, 'utf-8'));
for (const etf of etfPool) {
  etf.index_code = INDEX_NAME_MAP[etf.index] || null;
}

const results = JSON.parse(fs.readFileSync(RESULTS_FILE, 'utf-8'));

// 详细分析反向信号结果
console.log('=== 反向信号策略详细分析 ===\n');

// 按夏普排序，同时查看交易次数
const reverseSorted = results.reverse
  .filter(r => r.trades > 0)
  .sort((a, b) => b.sharpe - a.sharpe);

console.log('Top 20 反向信号结果 (含交易次数):\n');
console.log('代码         名称                    夏普    年化     回撤    交易次数  超额     跑赢BH');
console.log('─'.repeat(80));

reverseSorted.slice(0, 20).forEach(r => {
  const winSign = r.beat ? 'Y' : 'N';
  const excSign = r.excess >= 0 ? '+' : '';
  console.log(`${r.code.padEnd(12)} ${r.name.padEnd(20)} ${r.sharpe.toFixed(2).padStart(6)} ${(r.annReturn*100).toFixed(1).padStart(5)}% ${(r.maxDD*100).toFixed(1).padStart(5)}% ${String(r.trades).padStart(6)} ${excSign}${(r.excess*100).toFixed(1).padStart(5)}%   ${winSign}`);
});

// 统计交易次数分布
const tradesDistribution = {};
results.reverse.forEach(r => {
  const key = r.trades;
  tradesDistribution[key] = (tradesDistribution[key] || 0) + 1;
});

console.log('\n\n交易次数分布:');
Object.keys(tradesDistribution).sort((a, b) => a - b).forEach(k => {
  console.log(`  ${k}次交易: ${tradesDistribution[k]}个ETF`);
});

// 分析交易次数<=5的ETF（可能是异常数据）
const lowTradeETFs = results.reverse.filter(r => r.trades <= 5 && r.trades > 0);
console.log(`\n交易次数≤5的ETF: ${lowTradeETFs.length}个 (可能是异常数据)`);
console.log('这些ETF的夏普通常会被高估（因为单次大收益会放大夏普）');

// 只看交易次数>5的ETF（更可信）
const credibleResults = results.reverse.filter(r => r.trades > 5);
const avgSharpeCredible = credibleResults.reduce((a, b) => a + b.sharpe, 0) / credibleResults.length;
const sharpeGte1Credible = credibleResults.filter(r => r.sharpe >= 1.0).length;
const beatBHCredible = credibleResults.filter(r => r.beat).length;

console.log('\n\n=== 仅考虑交易次数>5的ETF ===');
console.log(`ETF数量: ${credibleResults.length}`);
console.log(`平均夏普: ${avgSharpeCredible.toFixed(3)}`);
console.log(`夏普≥1.0数量: ${sharpeGte1Credible}`);
console.log(`跑赢买入持有: ${beatBHCredible}/${credibleResults.length}`);

console.log('\n可信的Top10:');
const credibleSorted = credibleResults.sort((a, b) => b.sharpe - a.sharpe).slice(0, 10);
console.log('代码         名称                    夏普    年化     回撤    交易次数  超额     跑赢BH');
console.log('─'.repeat(80));
credibleSorted.forEach(r => {
  const winSign = r.beat ? 'Y' : 'N';
  const excSign = r.excess >= 0 ? '+' : '';
  console.log(`${r.code.padEnd(12)} ${r.name.padEnd(20)} ${r.sharpe.toFixed(2).padStart(6)} ${(r.annReturn*100).toFixed(1).padStart(5)}% ${(r.maxDD*100).toFixed(1).padStart(5)}% ${String(r.trades).padStart(6)} ${excSign}${(r.excess*100).toFixed(1).padStart(5)}%   ${winSign}`);
});

// 对比所有策略（只看交易次数>5）
console.log('\n\n=== 所有策略对比 (仅交易次数>5的ETF) ===\n');

const strategies = ['reverse', 'ma20_only', 'ma20_sharpe', 'macd_only', 'macd_sharpe', 'combined', 'multi_window'];
const strategyNames = {
  reverse: '反向信号',
  ma20_only: 'MA20趋势',
  ma20_sharpe: 'MA20+夏普',
  macd_only: 'MACD金叉',
  macd_sharpe: 'MACD+夏普',
  combined: '综合策略',
  multi_window: '多窗口共振'
};

strategies.forEach(s => {
  const arr = results[s];
  const credible = arr.filter(r => r.trades > 5);
  if (credible.length === 0) {
    console.log(`${strategyNames[s]}: 无可信数据 (交易次数都≤5)`);
    return;
  }
  
  const avgSharpe = credible.reduce((a, b) => a + b.sharpe, 0) / credible.length;
  const avgReturn = credible.reduce((a, b) => a + b.annReturn, 0) / credible.length;
  const avgDD = credible.reduce((a, b) => a + b.maxDD, 0) / credible.length;
  const sharpeGte1 = credible.filter(r => r.sharpe >= 1.0).length;
  
  console.log(`${strategyNames[s]} (${credible.length}个ETF)`);
  console.log(`  平均夏普: ${avgSharpe.toFixed(3)} | 平均年化: ${(avgReturn*100).toFixed(1)}% | 平均回撤: ${(avgDD*100).toFixed(1)}% | 夏普≥1.0: ${sharpeGte1}`);
});

// 找出所有策略中夏普≥1.0的ETF（交易次数>5）
console.log('\n\n=== 所有策略中夏普≥1.0的ETF（交易次数>5） ===\n');

const excellentETFs = [];
strategies.forEach(s => {
  const arr = results[s];
  arr.filter(r => r.sharpe >= 1.0 && r.trades > 5).forEach(r => {
    excellentETFs.push({ ...r, strategy: strategyNames[s] });
  });
});

// 去重并按夏普排序
const uniqueExcellent = {};
excellentETFs.forEach(e => {
  const key = `${e.code}_${e.strategy}`;
  uniqueExcellent[key] = e;
});

const sortedExcellent = Object.values(uniqueExcellent).sort((a, b) => b.sharpe - a.sharpe);
console.log(`共${sortedExcellent.length}个策略-ETF组合达到夏普≥1.0\n`);

if (sortedExcellent.length > 0) {
  console.log('代码         名称                    策略         夏普    年化     回撤    交易次数');
  console.log('─'.repeat(80));
  sortedExcellent.slice(0, 15).forEach(r => {
    console.log(`${r.code.padEnd(12)} ${r.name.padEnd(20)} ${r.strategy.padEnd(10)} ${r.sharpe.toFixed(2).padStart(6)} ${(r.annReturn*100).toFixed(1).padStart(5)}% ${(r.maxDD*100).toFixed(1).padStart(5)}% ${String(r.trades).padStart(6)}`);
  });
}

// 保存详细报告
const reportPath = 'D:/QClaw_Trading/scripts/backtest/improved_sharpe_report.txt';
let reportContent = '=== Improved Sharpe Strategy Analysis ===\n\n';
reportContent += 'Date: ' + new Date().toISOString().slice(0, 10) + '\n';
reportContent += 'ETF Pool: ' + etfPool.length + ' ETFs\n';
reportContent += 'Tested Indices: 47 (Skipped: 24 due to insufficient data)\n\n';

reportContent += '=== Strategy Summary (All ETFs) ===\n';
strategies.forEach(s => {
  const arr = results[s];
  const avgSharpe = arr.reduce((a, b) => a + (b.sharpe || 0), 0) / arr.length;
  const sharpeGte1 = arr.filter(r => r.sharpe >= 1.0).length;
  reportContent += `${strategyNames[s]}: AvgSharpe=${avgSharpe.toFixed(3)}, Sharpe>=1=${sharpeGte1}\n`;
});

reportContent += '\n=== Strategy Summary (Trades>5 only) ===\n';
strategies.forEach(s => {
  const arr = results[s].filter(r => r.trades > 5);
  if (arr.length > 0) {
    const avgSharpe = arr.reduce((a, b) => a + b.sharpe, 0) / arr.length;
    const sharpeGte1 = arr.filter(r => r.sharpe >= 1.0).length;
    reportContent += `${strategyNames[s]} (${arr.length} ETFs): AvgSharpe=${avgSharpe.toFixed(3)}, Sharpe>=1=${sharpeGte1}\n`;
  } else {
    reportContent += `${strategyNames[s]}: No credible data\n`;
  }
});

reportContent += '\n=== Top ETFs (Sharpe>=1.0, Trades>5) ===\n';
sortedExcellent.forEach(r => {
  reportContent += `${r.code}(${r.name})[${r.strategy}]: Sharpe=${r.sharpe.toFixed(2)}, Ann=${(r.annReturn*100).toFixed(1)}%, DD=${(r.maxDD*100).toFixed(1)}%, Trades=${r.trades}\n`;
});

fs.writeFileSync(reportPath, reportContent);
console.log(`\n[Report saved: ${reportPath}]`);