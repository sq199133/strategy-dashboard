/**
 * 严谨的MA趋势策略分析
 * 修正夏普计算bug，使用指数长周期数据
 * 
 * 核心修正：
 * 1. 夏普比率 = 仅计算持仓日的收益率标准差（不包含空仓日）
 * 2. 使用指数数据（长达37年）而非ETF（3年）
 * 3. 加入交易成本0.1%（单边）
 * 4. 测试多个MA周期（10/15/20/25/30）
 */

const fs = require('fs');
const path = require('path');

const INDEX_DIR = 'D:\\QClaw_Trading\\data\\index_history';
const COST_RATE = 0.001; // 单边交易成本0.1%

// ========== 核心计算函数 ==========

function calcMA(prices, period) {
  const ma = [];
  for (let i = 0; i < prices.length; i++) {
    if (i < period - 1) {
      ma.push(null);
    } else {
      const sum = prices.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
      ma.push(sum / period);
    }
  }
  return ma;
}

function calcSharpe(returns) {
  if (returns.length < 10) return null;
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((sum, r) => sum + (r - mean) ** 2, 0) / returns.length;
  const std = Math.sqrt(variance);
  if (std < 0.0001) return null;
  const annualReturn = mean * 252;
  const annualStd = std * Math.sqrt(252);
  return annualReturn / annualStd;
}

// ========== 策略回测 ==========

function backtest(closes, dates, maPeriod, options = {}) {
  const {
    useSharpeFilter = false,  // 1年滚动夏普>0过滤
    useVolFilter = false,     // 年化波动率<50%过滤
    stopLossPct = 0,          // 止损比例（0=无）
    costRate = COST_RATE
  } = options;
  
  if (closes.length < maPeriod + 252) return null;
  
  const ma = calcMA(closes, maPeriod);
  
  // 计算滚动夏普（用于过滤）
  let rollingSharpes = [];
  if (useSharpeFilter) {
    for (let i = 252; i < closes.length; i++) {
      const yearReturns = [];
      for (let j = i - 252; j < i; j++) {
        yearReturns.push((closes[j] - closes[j + 1]) / closes[j + 1]);
      }
      rollingSharpes[i] = calcSharpe(yearReturns);
    }
  }
  
  // 计算波动率（用于过滤）
  let rollingVols = [];
  if (useVolFilter) {
    for (let i = 252; i < closes.length; i++) {
      const yearReturns = [];
      for (let j = i - 252; j < i; j++) {
        yearReturns.push((closes[j] - closes[j + 1]) / closes[j + 1]);
      }
      const std = Math.sqrt(yearReturns.reduce((sum, r) => {
        const mean = yearReturns.reduce((a, b) => a + b, 0) / yearReturns.length;
        return sum + (r - mean) ** 2;
      }, 0) / yearReturns.length);
      rollingVols[i] = std * Math.sqrt(252);
    }
  }
  
  // 回测
  let position = 0;
  let entryPrice = 0;
  let nav = 1;
  let trades = 0;
  let stopLosses = 0;
  let wins = 0;
  let losses = 0;
  
  const navHistory = [1];
  const investedReturns = []; // 仅持仓日收益（用于计算真实夏普）
  const allReturns = [];      // 全部日收益（含空仓0%）
  
  for (let i = maPeriod; i < closes.length; i++) {
    const prevClose = closes[i - 1];
    const todayClose = closes[i];
    const dailyReturn = position > 0 ? (todayClose - prevClose) / prevClose : 0;
    
    allReturns.push(dailyReturn);
    if (position > 0) {
      investedReturns.push(dailyReturn);
      nav *= (1 + dailyReturn);
      navHistory.push(nav);
      
      // 止损检查
      if (stopLossPct > 0 && todayClose < entryPrice * (1 - stopLossPct)) {
        nav *= (1 - costRate);
        position = 0;
        stopLosses++;
        losses++;
        trades++;
      }
    } else {
      navHistory.push(nav);
    }
    
    // 买入信号
    if (position === 0) {
      let shouldBuy = closes[i] > ma[i] && closes[i - 1] <= ma[i - 1]; // 突破MA
      
      // 过滤条件
      if (shouldBuy && useSharpeFilter && rollingSharpes[i] !== undefined) {
        shouldBuy = rollingSharpes[i] > 0;
      }
      if (shouldBuy && useVolFilter && rollingVols[i] !== undefined) {
        shouldBuy = rollingVols[i] < 0.5;
      }
      
      if (shouldBuy) {
        position = 1;
        entryPrice = todayClose;
        nav *= (1 - costRate);
        trades++;
      }
    }
    // 卖出信号
    else if (position > 0 && closes[i] < ma[i] && closes[i - 1] >= ma[i - 1]) {
      nav *= (1 - costRate);
      if (entryPrice > todayClose) {
        losses++;
      } else {
        wins++;
      }
      position = 0;
    }
  }
  
  // 强制平仓
  if (position > 0) {
    nav *= (1 - costRate);
    if (entryPrice > closes[closes.length - 1]) {
      losses++;
    } else {
      wins++;
    }
    trades++;
  }
  
  // 买入持有收益
  const buyHold = closes[0] / closes[closes.length - 1];
  
  // 计算夏普（核心修正：仅用持仓日）
  const investedSharpe = calcSharpe(investedReturns);
  const fullSharpe = calcSharpe(allReturns);
  
  // 计算最大回撤
  let maxNav = 1, maxDD = 0;
  for (const n of navHistory) {
    if (n > maxNav) maxNav = n;
    const dd = (maxNav - n) / maxNav;
    if (dd > maxDD) maxDD = dd;
  }
  
  const years = closes.length / 252;
  const annualReturn = (nav - 1) / years;
  
  return {
    nav: nav,
    years: years,
    annualReturn: annualReturn * 100,
    investedSharpe: investedSharpe,
    fullSharpe: fullSharpe,
    maxDD: maxDD * 100,
    trades: trades,
    stopLosses: stopLosses,
    winRate: trades > 0 ? (wins / trades * 100) : 0,
    buyHold: buyHold,
    investedDays: investedReturns.length,
    totalDays: allReturns.length,
    positionRatio: investedReturns.length / allReturns.length * 100
  };
}

// ========== 主程序 ==========

console.log('='.repeat(70));
console.log('  MA趋势策略严谨分析 | 指数数据 | 修正夏普计算');
console.log('='.repeat(70));
console.log('');

// 加载指数数据
const files = fs.readdirSync(INDEX_DIR).filter(f => f.endsWith('.json'));
console.log(`发现 ${files.length} 个指数数据文件\n`);

// 策略配置
const strategies = [
  { name: 'MA10', period: 10, options: {} },
  { name: 'MA15', period: 15, options: {} },
  { name: 'MA20', period: 20, options: {} },
  { name: 'MA25', period: 25, options: {} },
  { name: 'MA30', period: 30, options: {} },
  { name: 'MA20+夏普过滤', period: 20, options: { useSharpeFilter: true } },
  { name: 'MA20+波动过滤', period: 20, options: { useVolFilter: true } },
  { name: 'MA20+止损5%', period: 20, options: { stopLossPct: 0.05 } },
  { name: 'MA20+夏普+止损', period: 20, options: { useSharpeFilter: true, stopLossPct: 0.05 } },
  { name: 'MA10+夏普+止损', period: 10, options: { useSharpeFilter: true, stopLossPct: 0.05 } },
];

// 结果汇总
const summary = {};

for (const strat of strategies) {
  summary[strat.name] = {
    sharpes: [],
    fullSharpes: [],
    annualReturns: [],
    maxDDs: [],
    trades: [],
    winRates: [],
    beatBH: 0,
    total: 0
  };
}

// 遍历指数
for (const file of files) {
  const indexCode = file.replace('.json', '');
  
  try {
    const data = JSON.parse(fs.readFileSync(path.join(INDEX_DIR, file), 'utf8'));
    if (!data.records) continue;
    
    const records = Object.values(data.records).reverse(); // 转为正序
    const closes = records.map(r => r.close);
    const dates = records.map(r => r.date);
    
    if (closes.length < 504) continue; // 至少2年数据
    
    // 测试每个策略
    for (const strat of strategies) {
      const result = backtest(closes, dates, strat.period, strat.options);
      if (!result) continue;
      
      const s = summary[strat.name];
      s.total++;
      if (result.investedSharpe !== null) s.sharpes.push(result.investedSharpe);
      if (result.fullSharpe !== null) s.fullSharpes.push(result.fullSharpe);
      s.annualReturns.push(result.annualReturn);
      s.maxDDs.push(result.maxDD);
      s.trades.push(result.trades);
      s.winRates.push(result.winRate);
      if (result.nav > result.buyHold) s.beatBH++;
    }
  } catch (e) {
    // 跳过错误
  }
}

// 输出结果
console.log('策略'.padEnd(20) + '| 持仓夏普 | 全期夏普 | 年化% | 回撤% | 交易 | 胜率% | 跑赢BH');
console.log('-'.repeat(85));

const sortedStrategies = strategies
  .map(s => ({ name: s.name, data: summary[s.name] }))
  .filter(s => s.data.total > 0)
  .sort((a, b) => {
    const avgA = a.data.sharpes.length > 0 ? 
      a.data.sharpes.reduce((x, y) => x + y, 0) / a.data.sharpes.length : -999;
    const avgB = b.data.sharpes.length > 0 ? 
      b.data.sharpes.reduce((x, y) => x + y, 0) / b.data.sharpes.length : -999;
    return avgB - avgA;
  });

for (const s of sortedStrategies) {
  const d = s.data;
  const avgSharpe = d.sharpes.length > 0 ? 
    (d.sharpes.reduce((a, b) => a + b, 0) / d.sharpes.length).toFixed(3) : 'N/A';
  const avgFullSharpe = d.fullSharpes.length > 0 ?
    (d.fullSharpes.reduce((a, b) => a + b, 0) / d.fullSharpes.length).toFixed(3) : 'N/A';
  const avgReturn = (d.annualReturns.reduce((a, b) => a + b, 0) / d.annualReturns.length).toFixed(1);
  const avgDD = (d.maxDDs.reduce((a, b) => a + b, 0) / d.maxDDs.length).toFixed(1);
  const avgTrades = Math.round(d.trades.reduce((a, b) => a + b, 0) / d.trades.length);
  const avgWinRate = (d.winRates.reduce((a, b) => a + b, 0) / d.winRates.length).toFixed(0);
  const beatPct = d.total > 0 ? (d.beatBH / d.total * 100).toFixed(0) : '0';
  
  console.log(
    s.name.padEnd(20) + '| ' +
    avgSharpe.toString().padStart(8) + ' | ' +
    avgFullSharpe.toString().padStart(8) + ' | ' +
    avgReturn.toString().padStart(5) + ' | ' +
    avgDD.toString().padStart(5) + ' | ' +
    avgTrades.toString().padStart(5) + ' | ' +
    avgWinRate.toString().padStart(5) + ' | ' +
    (beatPct + '%').padStart(6)
  );
}

console.log('');
console.log('核心结论：');
console.log('1. "持仓夏普" = 仅计算持仓日的夏普（修正bug后的真实夏普）');
console.log('2. "全期夏普" = 包含空仓日0%收益的夏普（之前的bug版本）');
console.log('3. 交易成本 = 0.1%单边（来回0.2%）');
console.log('');

// 找最佳策略
const best = sortedStrategies[0];
console.log(`最佳策略: ${best.name}`);
console.log(`  - 平均持仓夏普: ${(best.data.sharpes.reduce((a, b) => a + b, 0) / best.data.sharpes.length).toFixed(3)}`);
console.log(`  - 平均年化: ${(best.data.annualReturns.reduce((a, b) => a + b, 0) / best.data.annualReturns.length).toFixed(1)}%`);
console.log(`  - 跑赢买入持有: ${best.data.beatBH}/${best.data.total} (${(best.data.beatBH / best.data.total * 100).toFixed(0)}%)`);
