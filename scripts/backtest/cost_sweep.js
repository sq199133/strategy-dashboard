/**
 * 加入交易成本的MA20策略验证
 * 测试不同手续费率对策略表现的影响
 * 以及不同MA周期、止损参数的参数扫描
 */

const fs = require('fs');
const path = require('path');

const INDEX_HISTORY_DIR = 'D:/QClaw_Trading/data/index_history';
const ETF_POOL_FILE = 'D:/QClaw_Trading/data/etf_pool_v5.json';
const INDEX_NAME_MAP = require('./index_mapping.js');

const etfPool = JSON.parse(fs.readFileSync(ETF_POOL_FILE, 'utf-8'));
for (const etf of etfPool) etf.index_code = INDEX_NAME_MAP[etf.index] || null;

function loadIndexData(indexCode) {
  const filePath = path.join(INDEX_HISTORY_DIR, `${indexCode}.json`);
  if (!fs.existsSync(filePath)) return null;
  try {
    const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    if (!data.records || Object.keys(data.records).length === 0) return null;
    const records = Object.values(data.records).map(r => ({
      date: r.date, open: parseFloat(r.open), close: parseFloat(r.close),
      high: parseFloat(r.high), low: parseFloat(r.low), vol: parseFloat(r.vol || 0)
    })).sort((a, b) => a.date.localeCompare(b.date));
    return { ...data, records };
  } catch (e) { return null; }
}

function calcReturns(records) {
  const returns = [];
  for (let i = 1; i < records.length; i++)
    returns.push((records[i].close - records[i-1].close) / records[i-1].close);
  return returns;
}

function calcRollingSharpe(returns, window) {
  const sharpes = [];
  for (let i = window; i <= returns.length; i++) {
    const slice = returns.slice(i - window, i);
    const mean = slice.reduce((a, b) => a + b, 0) / slice.length;
    const std = Math.sqrt(slice.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / slice.length);
    sharpes.push(std > 1e-10 ? (mean * 252) / (std * Math.sqrt(252)) : 0);
  }
  return sharpes;
}

function calcMA(records, period) {
  const result = [];
  for (let i = 0; i < records.length; i++) {
    if (i < period - 1) { result.push(null); continue; }
    result.push(records.slice(i - period + 1, i + 1).reduce((a, b) => a + b.close, 0) / period);
  }
  return result;
}

/**
 * 带交易成本的回测
 * @param {number} costRate - 单边交易成本率 (如0.001 = 0.1%)
 * @param {number} stopLoss - 止损比例
 */
function backtestWithCost(records, maPeriod, sharpeFilter, sharpes1yr, costRate, stopLoss) {
  const WINDOW_1YR = 252;
  const ma = calcMA(records, maPeriod);
  
  let position = false;
  let entryPrice = 0;
  let entryIdx = 0;
  const navSeries = [1.0];
  const dailyReturns = [];
  let trades = [];
  let maxEquity = 1.0;
  let maxDD = 0;
  let totalCost = 0;
  
  for (let i = 1; i < records.length; i++) {
    const prevNav = navSeries[navSeries.length - 1];
    
    if (!position) {
      // 检查买入信号
      if (ma[i] && ma[i-1] && records[i].close > ma[i] && records[i-1].close <= ma[i-1]) {
        // 夏普过滤
        let sharpeOk = true;
        if (sharpeFilter) {
          const s1idx = i - WINDOW_1YR;
          sharpeOk = s1idx >= 0 && s1idx < sharpes1yr.length && sharpes1yr[s1idx] > 0;
        }
        if (sharpeOk) {
          position = true;
          entryPrice = records[i].close;
          entryIdx = i;
          totalCost += entryPrice * costRate; // 买入成本
        }
      }
      dailyReturns.push(0);
      navSeries.push(prevNav);
    } else {
      // 持仓 - 计算收益
      const dayReturn = (records[i].close - records[i-1].close) / records[i-1].close;
      const unrealizedPnL = (records[i].close - entryPrice) / entryPrice;
      const stopLossHit = stopLoss > 0 && unrealizedPnL < -stopLoss;
      
      // 卖出信号
      const sellSignal = ma[i] && ma[i-1] && records[i].close < ma[i] && records[i-1].close >= ma[i-1];
      
      if (stopLossHit || sellSignal) {
        position = false;
        const pnl = (records[i].close - entryPrice) / entryPrice - costRate; // 扣除卖出成本
        totalCost += records[i].close * costRate;
        trades.push({
          entryIdx, exitIdx: i,
          entryDate: records[entryIdx].date,
          exitDate: records[i].date,
          pnl,
          reason: stopLossHit ? 'stoploss' : 'signal'
        });
        dailyReturns.push(pnl);
        navSeries.push(prevNav * (1 + pnl));
      } else {
        dailyReturns.push(dayReturn);
        navSeries.push(prevNav * (1 + dayReturn));
      }
      
      maxEquity = Math.max(maxEquity, navSeries[navSeries.length - 1]);
      maxDD = Math.max(maxDD, (maxEquity - navSeries[navSeries.length - 1]) / maxEquity);
    }
  }
  
  // 强制平仓
  if (position) {
    const lastPrice = records[records.length - 1].close;
    const pnl = (lastPrice - entryPrice) / entryPrice - costRate;
    trades.push({ entryIdx, exitIdx: records.length - 1, pnl, reason: 'force_close' });
  }
  
  // 计算指标
  const totalDays = dailyReturns.length;
  const years = totalDays / 252;
  if (years <= 0 || trades.length === 0) return null;
  
  const totalReturn = navSeries[navSeries.length - 1] / navSeries[0] - 1;
  const annReturn = Math.pow(1 + totalReturn, 1 / years) - 1;
  
  const mean = dailyReturns.reduce((a, b) => a + b, 0) / totalDays;
  const std = Math.sqrt(dailyReturns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / totalDays);
  const sharpe = std > 1e-10 ? (mean / std) * Math.sqrt(252) : 0;
  
  const winRate = trades.filter(t => t.pnl > 0).length / trades.length;
  const stopLossCount = trades.filter(t => t.reason === 'stoploss').length;
  
  return { sharpe, annReturn, maxDD, trades: trades.length, winRate, years, totalReturn, stopLossCount };
}

// 买入持有基准
function buyHold(records) {
  const returns = calcReturns(records);
  const years = records.length / 252;
  const totalReturn = (records[records.length-1].close / records[0].close) - 1;
  const annReturn = Math.pow(1 + totalReturn, 1 / years) - 1;
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const std = Math.sqrt(returns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / returns.length);
  return { sharpe: std > 1e-10 ? (mean / std) * Math.sqrt(252) : 0, annReturn, maxDD: 0 };
}

// ====== 参数扫描 ======

console.log('=== MA20 Strategy Parameter Sweep (With Transaction Costs) ===\n');

// 参数组合
const maPeriods = [10, 15, 20, 25, 30, 40, 50, 60];
const costRates = [0, 0.0005, 0.001, 0.002, 0.003]; // 0%, 0.05%, 0.1%, 0.2%, 0.3%
const sharpeFilters = [false, true]; // 无过滤 vs 1年夏普>0
const stopLosses = [0, 0.03, 0.05, 0.08]; // 无止损, 3%, 5%, 8%

// 只做关键组合
const keyCombinations = [
  { ma: 20, cost: 0, sharpeF: false, sl: 0, label: 'MA20基准(无成本)' },
  { ma: 20, cost: 0.001, sharpeF: false, sl: 0, label: 'MA20+0.1%成本' },
  { ma: 20, cost: 0.002, sharpeF: false, sl: 0, label: 'MA20+0.2%成本' },
  { ma: 20, cost: 0.003, sharpeF: false, sl: 0, label: 'MA20+0.3%成本' },
  { ma: 20, cost: 0.001, sharpeF: true, sl: 0, label: 'MA20+夏普+0.1%成本' },
  { ma: 20, cost: 0.001, sharpeF: true, sl: 0.05, label: 'MA20+夏普+5%止损+0.1%成本' },
  { ma: 25, cost: 0.001, sharpeF: true, sl: 0.05, label: 'MA25+夏普+5%止损+0.1%成本' },
  { ma: 30, cost: 0.001, sharpeF: true, sl: 0.05, label: 'MA30+夏普+5%止损+0.1%成本' },
  { ma: 15, cost: 0.001, sharpeF: true, sl: 0.05, label: 'MA15+夏普+5%止损+0.1%成本' },
  { ma: 10, cost: 0.001, sharpeF: true, sl: 0.05, label: 'MA10+夏普+5%止损+0.1%成本' },
];

// 获取指数数据
const indexDataMap = {};
for (const etf of etfPool) {
  if (!etf.index_code) continue;
  if (indexDataMap[etf.index_code]) continue;
  const data = loadIndexData(etf.index_code);
  if (data && data.records.length > 800) {
    indexDataMap[etf.index_code] = data;
  }
}

console.log(`Unique indices with 800+ days: ${Object.keys(indexDataMap).length}\n`);

// 对每个参数组合，在所有指数上测试
const sweepResults = [];

for (const combo of keyCombinations) {
  const results = [];
  
  for (const etf of etfPool) {
    if (!etf.index_code) continue;
    const indexData = indexDataMap[etf.index_code];
    if (!indexData) continue;
    
    const records = indexData.records;
    const returns = calcReturns(records);
    const sharpes1yr = calcRollingSharpe(returns, 252);
    
    const result = backtestWithCost(records, combo.ma, combo.sharpeF, sharpes1yr, combo.cost, combo.sl);
    if (!result) continue;
    
    const bh = buyHold(records);
    results.push({
      code: etf.code, name: etf.name,
      ...result,
      bhSharpe: bh.sharpe, bhReturn: bh.annReturn,
      excess: result.annReturn - bh.annReturn,
      beatBH: result.annReturn > bh.annReturn
    });
  }
  
  const avgSharpe = results.reduce((a, b) => a + b.sharpe, 0) / results.length;
  const avgReturn = results.reduce((a, b) => a + b.annReturn, 0) / results.length;
  const avgDD = results.reduce((a, b) => a + b.maxDD, 0) / results.length;
  const avgTrades = results.reduce((a, b) => a + b.trades, 0) / results.length;
  const sharpeGte1 = results.filter(r => r.sharpe >= 1.0).length;
  const sharpeGte05 = results.filter(r => r.sharpe >= 0.5).length;
  const beatBH = results.filter(r => r.beatBH).length;
  const avgExcess = results.reduce((a, b) => a + b.excess, 0) / results.length;
  
  sweepResults.push({
    label: combo.label,
    combo,
    count: results.length,
    avgSharpe, avgReturn, avgDD, avgTrades,
    sharpeGte1, sharpeGte05, beatBH, avgExcess
  });
}

// 输出
console.log('═══════════════════════════════════════════════════════════════════════════');
console.log('             PARAMETER SWEEP RESULTS (with Transaction Costs)                 ');
console.log('═══════════════════════════════════════════════════════════════════════════\n');

console.log('策略                                夏普   年化     回撤    交易数  夏普≥1  夏普≥0.5  跑赢BH  超额');
console.log('─'.repeat(100));

sweepResults.forEach(r => {
  console.log(
    `${r.label.padEnd(36)} ${r.avgSharpe.toFixed(2).padStart(5)} ${(r.avgReturn*100).toFixed(1).padStart(5)}% ${(r.avgDD*100).toFixed(1).padStart(5)}% ${r.avgTrades.toFixed(0).padStart(6)} ${String(r.sharpeGte1).padStart(5)} ${String(r.sharpeGte05).padStart(8)} ${String(r.beatBH + '/' + r.count).padStart(8)} ${(r.avgExcess*100).toFixed(1).padStart(5)}%`
  );
});

// 关键对比
console.log('\n\n=== 关键发现 ===\n');

const baseline = sweepResults[0];
const cost01 = sweepResults[1];
const cost02 = sweepResults[2];
const cost03 = sweepResults[3];

console.log(`1. 交易成本影响：`);
console.log(`   无成本:   夏普${baseline.avgSharpe.toFixed(2)} 年化${(baseline.avgReturn*100).toFixed(1)}%`);
console.log(`   0.1%成本: 夏普${cost01.avgSharpe.toFixed(2)} 年化${(cost01.avgReturn*100).toFixed(1)}% (下降${((baseline.avgSharpe-cost01.avgSharpe)/baseline.avgSharpe*100).toFixed(0)}%)`);
console.log(`   0.2%成本: 夏普${cost02.avgSharpe.toFixed(2)} 年化${(cost02.avgReturn*100).toFixed(1)}% (下降${((baseline.avgSharpe-cost02.avgSharpe)/baseline.avgSharpe*100).toFixed(0)}%)`);
console.log(`   0.3%成本: 夏普${cost03.avgSharpe.toFixed(2)} 年化${(cost03.avgReturn*100).toFixed(1)}% (下降${((baseline.avgSharpe-cost03.avgSharpe)/baseline.avgSharpe*100).toFixed(0)}%)`);

// 找最佳MA周期
const maResults = sweepResults.filter(r => r.combo.sharpeF && r.combo.sl === 0.05 && r.combo.cost === 0.001);
console.log(`\n2. MA周期对比（+夏普过滤+5%止损+0.1%成本）:`);
maResults.forEach(r => {
  console.log(`   MA${r.combo.ma.toString().padStart(2)}: 夏普${r.avgSharpe.toFixed(2)} 年化${(r.avgReturn*100).toFixed(1)}% 回撤${(r.avgDD*100).toFixed(1)}% 交易${r.avgTrades.toFixed(0)}次 夏普≥1:${r.sharpeGte1}`);
});

// 保存
fs.writeFileSync('D:/QClaw_Trading/scripts/backtest/sweep_results.json', JSON.stringify(sweepResults, null, 2));
console.log('\n[Saved: sweep_results.json]');
