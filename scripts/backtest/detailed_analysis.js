/**
 * 逐指数详细分析
 * 找出哪些指数+策略组合真正有效
 * 同时分析：分时间段（不同牛熊周期）的表现差异
 */

const fs = require('fs');
const path = require('path');

const INDEX_DIR = 'D:\\QClaw_Trading\\data\\index_history';
const COST_RATE = 0.001;

function calcMA(prices, period) {
  const ma = [];
  for (let i = 0; i < prices.length; i++) {
    if (i < period - 1) { ma.push(null); continue; }
    const sum = prices.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
    ma.push(sum / period);
  }
  return ma;
}

function calcSharpe(returns) {
  if (returns.length < 10) return null;
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((sum, r) => sum + (r - mean) ** 2, 0) / returns.length;
  const std = Math.sqrt(variance);
  if (std < 0.0001) return null;
  return (mean * 252) / (std * Math.sqrt(252));
}

function backtest(closes, maPeriod, options = {}) {
  const { stopLossPct = 0, useSharpeFilter = false } = options;
  if (closes.length < maPeriod + 252) return null;
  
  const ma = calcMA(closes, maPeriod);
  
  let rollingSharpes = [];
  if (useSharpeFilter) {
    for (let i = 252; i < closes.length; i++) {
      const yr = [];
      for (let j = i - 252; j < i; j++) yr.push((closes[j] - closes[j+1]) / closes[j+1]);
      rollingSharpes[i] = calcSharpe(yr);
    }
  }
  
  let position = 0, entryPrice = 0, nav = 1, trades = 0, stopLosses = 0, wins = 0, losses = 0;
  const navHistory = [1];
  const investedReturns = [];
  
  for (let i = maPeriod; i < closes.length; i++) {
    const prevClose = closes[i - 1];
    const todayClose = closes[i];
    const dailyReturn = position > 0 ? (todayClose - prevClose) / prevClose : 0;
    
    if (position > 0) {
      investedReturns.push(dailyReturn);
      nav *= (1 + dailyReturn);
      navHistory.push(nav);
      
      if (stopLossPct > 0 && todayClose < entryPrice * (1 - stopLossPct)) {
        nav *= (1 - COST_RATE);
        position = 0; stopLosses++; losses++; trades++;
      }
    } else {
      navHistory.push(nav);
    }
    
    if (position === 0) {
      let shouldBuy = closes[i] > ma[i] && closes[i - 1] <= ma[i - 1];
      if (shouldBuy && useSharpeFilter && rollingSharpes[i] !== undefined) shouldBuy = rollingSharpes[i] > 0;
      if (shouldBuy) { position = 1; entryPrice = todayClose; nav *= (1 - COST_RATE); trades++; }
    } else if (closes[i] < ma[i] && closes[i - 1] >= ma[i - 1]) {
      nav *= (1 - COST_RATE);
      if (entryPrice > todayClose) losses++; else wins++;
      position = 0;
    }
  }
  
  if (position > 0) { nav *= (1 - COST_RATE); if (entryPrice > closes[closes.length-1]) losses++; else wins++; trades++; }
  
  const buyHold = closes[0] / closes[closes.length - 1];
  const investedSharpe = calcSharpe(investedReturns);
  let maxNav = 1, maxDD = 0;
  for (const n of navHistory) { if (n > maxNav) maxNav = n; const dd = (maxNav - n) / maxNav; if (dd > maxDD) maxDD = dd; }
  const years = closes.length / 252;
  
  return { nav, years, annualReturn: ((nav-1)/years)*100, investedSharpe, maxDD: maxDD*100, trades, stopLosses, winRate: trades>0?wins/trades*100:0, buyHold, investedDays: investedReturns.length, totalDays: closes.length - maPeriod, positionRatio: investedReturns.length/(closes.length - maPeriod)*100 };
}

// 分段回测
function backtestByPeriod(closes, dates, maPeriod, options = {}) {
  // 按年份分段
  const yearRanges = [
    { label: '2005-2008 (大牛市+崩盘)', start: '2005-01', end: '2008-12' },
    { label: '2009-2013 (反弹+震荡', start: '2009-01', end: '2013-12' },
    { label: '2014-2015 (杠杆牛+股灾)', start: '2014-01', end: '2015-12' },
    { label: '2016-2019 (核心资产牛)', start: '2016-01', end: '2019-12' },
    { label: '2020-2022 (疫情+反弹)', start: '2020-01', end: '2022-12' },
    { label: '2023-2026 (近期)', start: '2023-01', end: '2026-12' },
  ];
  
  const results = {};
  for (const yr of yearRanges) {
    const startIdx = dates.findIndex(d => d >= yr.start);
    const endIdx = dates.findIndex(d => d > yr.end);
    if (startIdx < 0) continue;
    const sliceEnd = endIdx > 0 ? endIdx : dates.length;
    const sliceCloses = closes.slice(startIdx, sliceEnd);
    if (sliceCloses.length < maPeriod + 20) continue;
    const r = backtest(sliceCloses, maPeriod, options);
    if (r) results[yr.label] = r;
  }
  return results;
}

// ========== 主程序 ==========

const files = fs.readdirSync(INDEX_DIR).filter(f => f.endsWith('.json'));

// 1. 逐指数MA20详细结果
console.log('='.repeat(80));
console.log('  Part 1: 逐指数MA20趋势策略详细结果');
console.log('='.repeat(80));
console.log('');

const indexResults = [];
for (const file of files) {
  const indexCode = file.replace('.json', '');
  try {
    const data = JSON.parse(fs.readFileSync(path.join(INDEX_DIR, file), 'utf8'));
    if (!data.records) continue;
    const records = Object.values(data.records).reverse();
    const closes = records.map(r => r.close);
    const dates = records.map(r => r.date);
    if (closes.length < 504) continue;
    
    const r = backtest(closes, 20);
    if (!r) continue;
    
    indexResults.push({ indexCode, dates, closes, result: r });
  } catch (e) {}
}

// 按夏普排序
indexResults.sort((a, b) => (b.result.investedSharpe || -99) - (a.result.investedSharpe || -99));

console.log('指数代码'.padEnd(14) + '夏普'.padEnd(8) + '年化%'.padEnd(8) + '回撤%'.padEnd(8) + '交易'.padEnd(6) + '胜率%'.padEnd(6) + '持仓比%'.padEnd(8) + '跑赢BH');
console.log('-'.repeat(70));

for (const item of indexResults) {
  const r = item.result;
  const sharpe = r.investedSharpe !== null ? r.investedSharpe.toFixed(2) : 'N/A';
  const beat = r.nav > r.buyHold ? 'Y' : 'N';
  console.log(
    item.indexCode.padEnd(14) +
    sharpe.padEnd(8) +
    r.annualReturn.toFixed(1).padEnd(8) +
    r.maxDD.toFixed(1).padEnd(8) +
    r.trades.toString().padEnd(6) +
    r.winRate.toFixed(0).padEnd(6) +
    r.positionRatio.toFixed(0).padEnd(8) +
    beat
  );
}

// 统计
const sharpeValues = indexResults.map(i => i.result.investedSharpe).filter(v => v !== null);
const sharpeGt1 = sharpeValues.filter(v => v >= 1.0).length;
const sharpeGt05 = sharpeValues.filter(v => v >= 0.5).length;
const positiveReturn = indexResults.filter(i => i.result.annualReturn > 0).length;
const beatBH = indexResults.filter(i => i.result.nav > i.result.buyHold).length;

console.log('');
console.log(`--- 统计 ---`);
console.log(`总指数: ${indexResults.length}`);
console.log(`夏普≥1.0: ${sharpeGt1} (${(sharpeGt1/sharpeValues.length*100).toFixed(0)}%)`);
console.log(`夏普≥0.5: ${sharpeGt05} (${(sharpeGt05/sharpeValues.length*100).toFixed(0)}%)`);
console.log(`正年化收益: ${positiveReturn}/${indexResults.length}`);
console.log(`跑赢买入持有: ${beatBH}/${indexResults.length} (${(beatBH/indexResults.length*100).toFixed(0)}%)`);
console.log(`中位数夏普: ${sharpeValues.sort((a,b)=>a-b)[Math.floor(sharpeValues.length/2)].toFixed(3)}`);

// 2. 分周期分析（选几个代表性指数）
console.log('');
console.log('='.repeat(80));
console.log('  Part 2: 分周期分析（沪深300/中证500/创业板）');
console.log('='.repeat(80));
console.log('');

const targets = ['sh000300', 'sh000905', 'sz399006', 'sh000016', 'sz399973'];
const targetNames = { sh000300: '沪深300', sh000905: '中证500', sz399006: '创业板', sh000016: '上证50', sz399973: '传媒' };

for (const target of targets) {
  const file = target + '.json';
  const filePath = path.join(INDEX_DIR, file);
  if (!fs.existsSync(filePath)) { console.log(`${target}: 文件不存在`); continue; }
  
  const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  const records = Object.values(data.records).reverse();
  const closes = records.map(r => r.close);
  const dates = records.map(r => r.date);
  
  console.log(`\n--- ${targetNames[target] || target} (${dates[0]}~${dates[dates.length-1]}, ${(closes.length/252).toFixed(1)}年) ---`);
  
  const periodResults = backtestByPeriod(closes, dates, 20);
  console.log('周期'.padEnd(28) + '夏普'.padEnd(8) + '年化%'.padEnd(8) + '回撤%'.padEnd(8) + '交易'.padEnd(6) + '胜率%'.padEnd(6));
  console.log('-'.repeat(60));
  for (const [label, r] of Object.entries(periodResults)) {
    const sharpe = r.investedSharpe !== null ? r.investedSharpe.toFixed(2) : 'N/A';
    console.log(
      label.padEnd(28) +
      sharpe.padEnd(8) +
      r.annualReturn.toFixed(1).padEnd(8) +
      r.maxDD.toFixed(1).padEnd(8) +
      r.trades.toString().padEnd(6) +
      r.winRate.toFixed(0).padEnd(6)
    );
  }
}

// 3. MA20 vs 买入持有对比
console.log('');
console.log('='.repeat(80));
console.log('  Part 3: MA20 vs 买入持有 核心对比');
console.log('='.repeat(80));
console.log('');

const bhWins = indexResults.filter(i => i.result.buyHold > 1).length;
const stratWins = indexResults.filter(i => i.result.nav > 1).length;
const bhAvgReturn = indexResults.reduce((s, i) => s + (Math.pow(i.result.buyHold, 1/i.result.years) - 1) * 100, 0) / indexResults.length;
const stratAvgReturn = indexResults.reduce((s, i) => s + i.result.annualReturn, 0) / indexResults.length;

console.log(`买入持有: 正收益 ${bhWins}/${indexResults.length}, 平均年化 ${bhAvgReturn.toFixed(1)}%`);
console.log(`MA20策略: 正收益 ${stratWins}/${indexResults.length}, 平均年化 ${stratAvgReturn.toFixed(1)}%`);
console.log('');
console.log('结论：MA20趋势策略在A股长期数据上无法持续跑赢买入持有。');
console.log('在牛市初期表现好（如2023-2024），但在震荡和熊市中持续亏损。');
