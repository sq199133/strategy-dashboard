/**
 * MA10策略深度分析
 * 分析MA10+夏普过滤+5%止损策略的详细表现
 */

const fs = require('fs');
const path = require('path');

// 配置
const HISTORY_DIR = 'D:\\QClaw_Trading\\data\\index_history';
const INDEX_MAP_FILE = 'D:\\QClaw_Trading\\scripts\\backtest\\index_mapping.js';
const COST = 0.001; // 0.1%交易成本

// 加载指数映射（可选）
// const indexMap = require(INDEX_MAP_FILE);

// MA10策略参数
const MA_PERIOD = 10;
const SHARP_LOOKBACK = 252; // 1年
const STOP_LOSS = 0.05; // 5%止损

// 计算MA
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

// 计算滚动夏普
function calcRollingSharpe(returns, lookback) {
  const sharpe = [];
  for (let i = 0; i < returns.length; i++) {
    if (i < lookback - 1) {
      sharpe.push(null);
    } else {
      const slice = returns.slice(i - lookback + 1, i + 1);
      const mean = slice.reduce((a, b) => a + b, 0) / slice.length;
      const std = Math.sqrt(slice.reduce((a, b) => a + (b - mean) ** 2, 0) / slice.length);
      sharpe.push(std > 0 ? mean / std * Math.sqrt(252) : 0);
    }
  }
  return sharpe;
}

// 回测单只指数
function backtestIndex(indexCode, closes) {
  if (closes.length < 300) return null;
  
  // 反转为正序（旧→新）
  closes = [...closes].reverse();
  
  // 计算日收益率
  const returns = [];
  for (let i = 1; i < closes.length; i++) {
    returns.push((closes[i] - closes[i - 1]) / closes[i - 1]);
  }
  
  // 计算MA10
  const ma10 = calcMA(closes, MA_PERIOD);
  
  // 计算滚动夏普（用收益率）
  const rollingSharpe = calcRollingSharpe(returns, SHARP_LOOKBACK);
  
  // 交易记录
  const trades = [];
  let position = false;
  let entryPrice = 0;
  let entryDate = '';
  let peakPrice = 0;
  
  // 策略净值
  const nav = [1];
  let cash = 1;
  let holdings = 0;
  
  for (let i = MA_PERIOD; i < closes.length; i++) {
    const price = closes[i];
    const ma = ma10[i];
    const sharp = rollingSharpe[i - 1]; // 用前一天的夏普判断
    
    if (!position) {
      // 买入条件：价格上穿MA10 + 滚动夏普>0
      if (price > ma && closes[i - 1] <= ma10[i - 1] && sharp !== null && sharp > 0) {
        position = true;
        entryPrice = price;
        entryDate = i;
        peakPrice = price;
        holdings = cash * (1 - COST);
        cash = 0;
      }
      nav.push(cash + holdings);
    } else {
      // 更新峰值
      if (price > peakPrice) peakPrice = price;
      
      // 卖出条件：价格下穿MA10 或 止损触发
      const stopTriggered = (price - entryPrice) / entryPrice < -STOP_LOSS;
      const trendReversal = price < ma && closes[i - 1] >= ma10[i - 1];
      
      if (stopTriggered || trendReversal) {
        const exitPrice = stopTriggered ? entryPrice * (1 - STOP_LOSS) : price;
        const pnl = (exitPrice - entryPrice) / entryPrice;
        trades.push({
          entryDate,
          exitDate: i,
          entryPrice,
          exitPrice,
          pnl: pnl - COST * 2,
          reason: stopTriggered ? 'stop' : 'trend'
        });
        
        cash = holdings * (exitPrice / entryPrice) * (1 - COST);
        holdings = 0;
        position = false;
      }
      nav.push(cash + holdings * (price / entryPrice));
    }
  }
  
  // 强制平仓
  if (position) {
    const pnl = (closes[closes.length - 1] - entryPrice) / entryPrice;
    trades.push({
      entryDate,
      exitDate: closes.length - 1,
      entryPrice,
      exitPrice: closes[closes.length - 1],
      pnl: pnl - COST * 2,
      reason: 'end'
    });
  }
  
  // 计算夏普
  const navReturns = [];
  for (let i = 1; i < nav.length; i++) {
    navReturns.push((nav[i] - nav[i - 1]) / nav[i - 1]);
  }
  const meanNav = navReturns.reduce((a, b) => a + b, 0) / navReturns.length;
  const stdNav = Math.sqrt(navReturns.reduce((a, b) => a + (b - meanNav) ** 2, 0) / navReturns.length);
  const sharpe = stdNav > 0 ? meanNav / stdNav * Math.sqrt(252) : 0;
  
  // 计算年化收益
  const totalReturn = nav[nav.length - 1] - 1;
  const years = closes.length / 252;
  const annualReturn = Math.pow(1 + totalReturn, 1 / years) - 1;
  
  // 计算最大回撤
  let maxDD = 0;
  let peak = nav[0];
  for (let i = 1; i < nav.length; i++) {
    if (nav[i] > peak) peak = nav[i];
    const dd = (peak - nav[i]) / peak;
    if (dd > maxDD) maxDD = dd;
  }
  
  // 止损次数
  const stopTrades = trades.filter(t => t.reason === 'stop').length;
  const trendTrades = trades.filter(t => t.reason === 'trend').length;
  
  return {
    indexCode,
    sharpe,
    annualReturn,
    maxDD,
    totalTrades: trades.length,
    stopTrades,
    trendTrades,
    avgPnl: trades.length > 0 ? trades.reduce((a, t) => a + t.pnl, 0) / trades.length : 0,
    winRate: trades.length > 0 ? trades.filter(t => t.pnl > 0).length / trades.length : 0,
    avgWin: trades.filter(t => t.pnl > 0).length > 0 
      ? trades.filter(t => t.pnl > 0).reduce((a, t) => a + t.pnl, 0) / trades.filter(t => t.pnl > 0).length 
      : 0,
    avgLoss: trades.filter(t => t.pnl < 0).length > 0
      ? trades.filter(t => t.pnl < 0).reduce((a, t) => a + t.pnl, 0) / trades.filter(t => t.pnl < 0).length
      : 0,
    years,
    dataPoints: closes.length
  };
}

// 主分析
console.log('=== MA10+Sharp+StopLoss 深度分析 ===\n');

// 加载所有指数数据
const results = [];
const files = fs.readdirSync(HISTORY_DIR).filter(f => f.endsWith('.json'));

for (const file of files) {
  try {
    const data = JSON.parse(fs.readFileSync(path.join(HISTORY_DIR, file)));
    const closes = data.records ? Object.values(data.records).map(r => r.close) : [];
    const indexCode = file.replace('.json', '');
    
    const result = backtestIndex(indexCode, closes);
    if (result) {
      // 直接用指数代码作为名称
      result.etfName = indexCode;
      results.push(result);
    }
  } catch (e) {
    console.log('Error loading', file, ':', e.message);
  }
}

// 排序
results.sort((a, b) => b.sharpe - a.sharpe);

// 统计
const validResults = results.filter(r => r.totalTrades > 0);
const sharpeGte1 = validResults.filter(r => r.sharpe >= 1).length;
const sharpeGte05 = validResults.filter(r => r.sharpe >= 0.5).length;
const avgSharpe = validResults.reduce((a, r) => a + r.sharpe, 0) / validResults.length;
const avgAnnual = validResults.reduce((a, r) => a + r.annualReturn, 0) / validResults.length;
const avgDD = validResults.reduce((a, r) => a + r.maxDD, 0) / validResults.length;
const avgTrades = validResults.reduce((a, r) => a + r.totalTrades, 0) / validResults.length;
const avgStopTrades = validResults.reduce((a, r) => a + r.stopTrades, 0) / validResults.length;
const avgWinRate = validResults.reduce((a, r) => a + r.winRate, 0) / validResults.length;

console.log(`有效指数数量: ${validResults.length}`);
console.log(`夏普≥1.0数量: ${sharpeGte1} (${(sharpeGte1/validResults.length*100).toFixed(1)}%)`);
console.log(`夏普≥0.5数量: ${sharpeGte05} (${(sharpeGte05/validResults.length*100).toFixed(1)}%)`);
console.log(`平均夏普: ${avgSharpe.toFixed(3)}`);
console.log(`平均年化: ${(avgAnnual*100).toFixed(1)}%`);
console.log(`平均回撤: ${(avgDD*100).toFixed(1)}%`);
console.log(`平均交易数: ${avgTrades.toFixed(0)}次`);
console.log(`平均止损次数: ${avgStopTrades.toFixed(1)}次`);
console.log(`平均胜率: ${(avgWinRate*100).toFixed(1)}%\n`);

// 交易频率分布
const tradeBins = { '0-50': 0, '50-100': 0, '100-150': 0, '150-200': 0, '200+': 0 };
for (const r of validResults) {
  if (r.totalTrades <= 50) tradeBins['0-50']++;
  else if (r.totalTrades <= 100) tradeBins['50-100']++;
  else if (r.totalTrades <= 150) tradeBins['100-150']++;
  else if (r.totalTrades <= 200) tradeBins['150-200']++;
  else tradeBins['200+']++;
}
console.log('交易频率分布:');
for (const [bin, count] of Object.entries(tradeBins)) {
  console.log(`  ${bin}次: ${count}个指数`);
}

console.log('\n=== Top 15 夏普最高的指数 ===');
console.log('指数代码        ETF名称          夏普    年化    回撤    交易数  胜率   止损次数');
console.log('─'.repeat(85));
for (let i = 0; i < Math.min(15, validResults.length); i++) {
  const r = validResults[i];
  console.log(
    `${r.indexCode.padEnd(12)} ${(r.etfName||'Unknown').substring(0,12).padEnd(16)} ` +
    `${r.sharpe.toFixed(2).padStart(5)}  ${(r.annualReturn*100).toFixed(1).padStart(5)}%  ` +
    `${(r.maxDD*100).toFixed(1).padStart(5)}%  ${r.totalTrades.toString().padStart(5)}   ` +
    `${(r.winRate*100).toFixed(0).padStart(3)}%  ${r.stopTrades.toString().padStart(5)}`
  );
}

console.log('\n=== Bottom 10 夏普最低的指数 ===');
for (let i = Math.max(0, validResults.length - 10); i < validResults.length; i++) {
  const r = validResults[i];
  console.log(
    `${r.indexCode.padEnd(12)} ${(r.etfName||'Unknown').substring(0,12).padEnd(16)} ` +
    `${r.sharpe.toFixed(2).padStart(5)}  ${(r.annualReturn*100).toFixed(1).padStart(5)}%  ` +
    `${(r.maxDD*100).toFixed(1).padStart(5)}%  ${r.totalTrades.toString().padStart(5)}   ` +
    `${(r.winRate*100).toFixed(0).padStart(3)}%  ${r.stopTrades.toString().padStart(5)}`
  );
}

// 止损分析
const stopPnl = validResults.flatMap(r => r.totalTrades > 0 ? [] : []);
console.log('\n=== 止损机制分析 ===');
const stopRatio = avgStopTrades / avgTrades;
console.log(`止损触发比例: ${(stopRatio*100).toFixed(1)}%`);
const avgLossPct = validResults.filter(r => r.avgLoss < 0).length > 0
  ? validResults.filter(r => r.avgLoss < 0).reduce((a, r) => a + r.avgLoss, 0) / validResults.filter(r => r.avgLoss < 0).length * 100
  : 0;
console.log(`平均单次亏损: ${avgLossPct.toFixed(1)}%`);

// 年化分布
const annualBins = { '<0': 0, '0-10%': 0, '10-20%': 0, '20-30%': 0, '30-40%': 0, '40%+': 0 };
for (const r of validResults) {
  const ann = r.annualReturn * 100;
  if (ann < 0) annualBins['<0']++;
  else if (ann < 10) annualBins['0-10%']++;
  else if (ann < 20) annualBins['10-20%']++;
  else if (ann < 30) annualBins['20-30%']++;
  else if (ann < 40) annualBins['30-40%']++;
  else annualBins['40%+']++;
}
console.log('\n年化收益分布:');
for (const [bin, count] of Object.entries(annualBins)) {
  console.log(`  ${bin}: ${count}个指数`);
}

// 保存详细结果
fs.writeFileSync(
  'D:\\QClaw_Trading\\scripts\\backtest\\ma10_analysis.json',
  JSON.stringify(validResults, null, 2)
);
console.log('\n详细结果已保存至 ma10_analysis.json');