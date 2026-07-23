/**
 * 严谨版改进策略回测
 * 修复：
 * 1. 逐日计算持仓净值（而非仅按交易计算）
 * 2. 正确的夏普比率计算
 * 3. 修正指数映射
 * 4. 加入止损机制
 */

const fs = require('fs');
const path = require('path');

const INDEX_HISTORY_DIR = 'D:/QClaw_Trading/data/index_history';
const ETF_POOL_FILE = 'D:/QClaw_Trading/data/etf_pool_v5.json';
const RESULTS_FILE = 'D:/QClaw_Trading/scripts/backtest/rigorous_results.json';

const INDEX_NAME_MAP = require('./index_mapping.js');

// 加载ETF池
const etfPool = JSON.parse(fs.readFileSync(ETF_POOL_FILE, 'utf-8'));
for (const etf of etfPool) {
  etf.index_code = INDEX_NAME_MAP[etf.index] || null;
}

// 加载指数数据
function loadIndexData(indexCode) {
  const filePath = path.join(INDEX_HISTORY_DIR, `${indexCode}.json`);
  if (!fs.existsSync(filePath)) return null;
  try {
    const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    if (!data.records || Object.keys(data.records).length === 0) return null;
    const records = Object.values(data.records).map(r => ({
      date: r.date,
      open: parseFloat(r.open),
      close: parseFloat(r.close),
      high: parseFloat(r.high),
      low: parseFloat(r.low),
      vol: parseFloat(r.vol || 0)
    })).sort((a, b) => a.date.localeCompare(b.date));
    return { ...data, records };
  } catch (e) { return null; }
}

// 计算日收益率
function calcReturns(records) {
  const returns = [];
  for (let i = 1; i < records.length; i++) {
    returns.push((records[i].close - records[i-1].close) / records[i-1].close);
  }
  return returns;
}

// 滚动夏普（年化）
function calcRollingSharpe(returns, window) {
  const sharpes = [];
  for (let i = window; i <= returns.length; i++) {
    const slice = returns.slice(i - window, i);
    const mean = slice.reduce((a, b) => a + b, 0) / slice.length;
    const std = Math.sqrt(slice.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / slice.length);
    const sharpe = std > 1e-10 ? (mean * 252) / (std * Math.sqrt(252)) : 0;
    sharpes.push(sharpe);
  }
  return sharpes;
}

// MA计算
function calcMA(records, period) {
  const result = [];
  for (let i = 0; i < records.length; i++) {
    if (i < period - 1) { result.push(null); continue; }
    const sum = records.slice(i - period + 1, i + 1).reduce((a, b) => a + b.close, 0);
    result.push(sum / period);
  }
  return result;
}

// EMA计算
function ema(data, period) {
  const k = 2 / (period + 1);
  const result = [data.slice(0, period).reduce((a, b) => a + b, 0) / period];
  for (let i = period; i < data.length; i++) {
    result.push(data[i] * k + result[result.length - 1] * (1 - k));
  }
  return result;
}

// MACD计算
function calcMACD(records) {
  const closes = records.map(r => r.close);
  const ema12 = ema(closes, 12);
  const ema26 = ema(closes, 26);
  const minLen = Math.min(ema12.length, ema26.length);
  const dif = [];
  for (let i = 0; i < minLen; i++) {
    dif.push(ema12[ema12.length - minLen + i] - ema26[ema26.length - minLen + i]);
  }
  const dea = ema(dif, 9);
  const macdHist = [];
  for (let i = 0; i < dea.length; i++) {
    macdHist.push((dif[i + 8] - dea[i]) * 2);
  }
  return { dif, dea, macdHist, offset: 8 };
}

/**
 * 逐日回测引擎
 * 记录每天的持仓市值，用于精确计算夏普
 */
function rigorousBacktest(records, strategyFn, stopLossPct = 0.05) {
  // 逐日净值
  const navSeries = [1.0];
  const dailyReturns = [];
  let position = false;
  let entryPrice = 0;
  let entryIdx = 0;
  let trades = [];
  let maxEquity = 1.0;
  let maxDD = 0;
  
  for (let i = 1; i < records.length; i++) {
    const prevNav = navSeries[navSeries.length - 1];
    
    if (!position) {
      // 空仓 - 检查买入信号
      const signal = strategyFn(i, records, true);
      if (signal.buy) {
        position = true;
        entryPrice = records[i].close;
        entryIdx = i;
      }
      // 空仓日收益为0
      dailyReturns.push(0);
      navSeries.push(prevNav);
    } else {
      // 持仓 - 计算当日收益
      const dayReturn = (records[i].close - records[i-1].close) / records[i-1].close;
      
      // 止损检查
      const unrealizedPnL = (records[i].close - entryPrice) / entryPrice;
      const stopLossHit = unrealizedPnL < -stopLossPct;
      
      // 卖出信号
      const signal = strategyFn(i, records, false);
      
      if (stopLossHit || signal.sell) {
        position = false;
        const pnl = (records[i].close - entryPrice) / entryPrice;
        const sellReason = stopLossHit ? 'stoploss' : 'signal';
        trades.push({
          entryIdx,
          exitIdx: i,
          entryDate: records[entryIdx].date,
          exitDate: records[i].date,
          entryPrice,
          exitPrice: records[i].close,
          pnl,
          reason: sellReason
        });
        dailyReturns.push(pnl); // 卖出当天的完整收益
        navSeries.push(prevNav * (1 + pnl));
      } else {
        dailyReturns.push(dayReturn);
        navSeries.push(prevNav * (1 + dayReturn));
      }
      
      // 追踪最大回撤
      maxEquity = Math.max(maxEquity, navSeries[navSeries.length - 1]);
      maxDD = Math.max(maxDD, (maxEquity - navSeries[navSeries.length - 1]) / maxEquity);
    }
  }
  
  // 强制平仓
  if (position) {
    const lastPrice = records[records.length - 1].close;
    const pnl = (lastPrice - entryPrice) / entryPrice;
    trades.push({
      entryIdx, exitIdx: records.length - 1,
      entryDate: records[entryIdx].date,
      exitDate: records[records.length - 1].date,
      entryPrice, exitPrice: lastPrice,
      pnl, reason: 'force_close'
    });
  }
  
  // 计算绩效指标
  const totalDays = dailyReturns.length;
  const years = totalDays / 252;
  const totalReturn = navSeries[navSeries.length - 1] / navSeries[0] - 1;
  const annReturn = years > 0 ? Math.pow(1 + totalReturn, 1 / years) - 1 : 0;
  
  // 真实夏普比率
  const meanDailyReturn = dailyReturns.reduce((a, b) => a + b, 0) / totalDays;
  const stdDailyReturn = Math.sqrt(dailyReturns.reduce((a, b) => a + Math.pow(b - meanDailyReturn, 2), 0) / totalDays);
  const sharpe = stdDailyReturn > 1e-10 ? (meanDailyReturn / stdDailyReturn) * Math.sqrt(252) : 0;
  
  // 只用持仓日的夏普
  const holdingReturns = dailyReturns.filter(r => r !== 0);
  const meanHolding = holdingReturns.length > 0 ? holdingReturns.reduce((a, b) => a + b, 0) / holdingReturns.length : 0;
  const stdHolding = holdingReturns.length > 1 ? Math.sqrt(holdingReturns.reduce((a, b) => a + Math.pow(b - meanHolding, 2), 0) / holdingReturns.length) : 0;
  const sharpeHolding = stdHolding > 1e-10 ? (meanHolding / stdHolding) * Math.sqrt(252) : 0;
  
  const winTrades = trades.filter(t => t.pnl > 0).length;
  const winRate = trades.length > 0 ? winTrades / trades.length : 0;
  
  return {
    sharpe,           // 全周期夏普（含空仓日=0收益）
    sharpeHolding,    // 仅持仓日夏普
    annReturn,        // 年化收益率
    maxDD,            // 最大回撤
    trades: trades.length,
    winRate,
    totalReturn,
    years,
    stopLossTrades: trades.filter(t => t.reason === 'stoploss').length,
    signalTrades: trades.filter(t => t.reason === 'signal').length
  };
}

// 买入持有基准
function buyHoldResult(records) {
  const returns = calcReturns(records);
  const years = records.length / 252;
  const totalReturn = (records[records.length-1].close / records[0].close) - 1;
  const annReturn = Math.pow(1 + totalReturn, 1 / years) - 1;
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const std = Math.sqrt(returns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / returns.length);
  const sharpe = std > 1e-10 ? (mean / std) * Math.sqrt(252) : 0;
  let maxP = records[0].close, maxDD = 0;
  for (const r of records) {
    maxP = Math.max(maxP, r.close);
    maxDD = Math.max(maxDD, (maxP - r.close) / maxP);
  }
  return { sharpe, annReturn, maxDD, years };
}

// ====== 策略定义 ======

const WINDOW_1YR = 252;
const WINDOW_3YR = 756;

const strategyDefs = [
  {
    name: 'S0_Original',
    desc: '3yr Sharpe>1 buy, <1 sell',
    startIdx: WINDOW_3YR,
    fn: (i, recs, sharpes1yr, sharpes3yr, ma20, macdData) => {
      const s3idx = i - WINDOW_3YR;
      if (s3idx < 0 || s3idx >= sharpes3yr.length) return { buy: false, sell: false };
      const s3 = sharpes3yr[s3idx];
      return { buy: s3 > 1.0, sell: s3 < 1.0 };
    }
  },
  {
    name: 'S1_Reverse',
    desc: '3yr Sharpe<0 buy, >0.5 sell',
    startIdx: WINDOW_3YR,
    fn: (i, recs, sharpes1yr, sharpes3yr, ma20, macdData) => {
      const s3idx = i - WINDOW_3YR;
      if (s3idx < 0 || s3idx >= sharpes3yr.length) return { buy: false, sell: false };
      const s3 = sharpes3yr[s3idx];
      return { buy: s3 < 0, sell: s3 > 0.5 };
    }
  },
  {
    name: 'S2_MA20',
    desc: 'Price > MA20 buy, < MA20 sell',
    startIdx: 21,
    fn: (i, recs, s1, s3, ma20, macdData) => {
      if (!ma20[i]) return { buy: false, sell: false };
      return {
        buy: recs[i].close > ma20[i] && recs[i-1].close <= ma20[i-1],
        sell: recs[i].close < ma20[i] && recs[i-1].close >= ma20[i-1]
      };
    }
  },
  {
    name: 'S3_MA20_SharpF',
    desc: 'MA20 cross + 1yr Sharpe>0 filter',
    startIdx: Math.max(21, WINDOW_1YR),
    fn: (i, recs, sharpes1yr, s3, ma20, macdData) => {
      if (!ma20[i]) return { buy: false, sell: false };
      const s1idx = i - WINDOW_1YR;
      if (s1idx < 0 || s1idx >= sharpes1yr.length) return { buy: false, sell: false };
      const sharpe1 = sharpes1yr[s1idx];
      return {
        buy: recs[i].close > ma20[i] && recs[i-1].close <= ma20[i-1] && sharpe1 > 0,
        sell: recs[i].close < ma20[i] && recs[i-1].close >= ma20[i-1]
      };
    }
  },
  {
    name: 'S4_Combined',
    desc: 'MA20 above + MACD red + 1yr Sharpe>0',
    startIdx: Math.max(30, WINDOW_1YR),
    fn: (i, recs, sharpes1yr, s3, ma20, macdData) => {
      if (!ma20[i]) return { buy: false, sell: false };
      const s1idx = i - WINDOW_1YR;
      if (s1idx < 0 || s1idx >= sharpes1yr.length) return { buy: false, sell: false };
      const sharpe1 = sharpes1yr[s1idx];
      const { dif, dea, macdHist, offset } = macdData;
      const macdIdx = i - offset;
      if (macdIdx < 1 || macdIdx >= dif.length) return { buy: false, sell: false };
      const macdPositive = dif[macdIdx] > dea[macdIdx - offset]; // DIF > DEA
      const macdNegative = dif[macdIdx] < dea[macdIdx - offset];
      
      return {
        buy: recs[i].close > ma20[i] && macdPositive && sharpe1 > 0,
        sell: recs[i].close < ma20[i] || macdNegative
      };
    }
  },
  {
    name: 'S5_MultiWindow',
    desc: '1yr Sharpe>0.5 + 3yr Sharpe>0 + MA20 above',
    startIdx: Math.max(21, WINDOW_3YR),
    fn: (i, recs, sharpes1yr, sharpes3yr, ma20, macdData) => {
      if (!ma20[i]) return { buy: false, sell: false };
      const s1idx = i - WINDOW_1YR;
      const s3idx = i - WINDOW_3YR;
      if (s1idx < 0 || s1idx >= sharpes1yr.length || s3idx < 0 || s3idx >= sharpes3yr.length) {
        return { buy: false, sell: false };
      }
      return {
        buy: sharpes1yr[s1idx] > 0.5 && sharpes3yr[s3idx] > 0 && recs[i].close > ma20[i],
        sell: sharpes1yr[s1idx] < 0 || sharpes3yr[s3idx] < 0
      };
    }
  },
  {
    name: 'S6_ReverseMA',
    desc: '3yr Sharpe<0 + MA20 cross up (contrarian+momentum)',
    startIdx: Math.max(21, WINDOW_3YR),
    fn: (i, recs, sharpes1yr, sharpes3yr, ma20, macdData) => {
      if (!ma20[i]) return { buy: false, sell: false };
      const s3idx = i - WINDOW_3YR;
      if (s3idx < 0 || s3idx >= sharpes3yr.length) return { buy: false, sell: false };
      return {
        buy: sharpes3yr[s3idx] < 0 && recs[i].close > ma20[i],  // 底部+趋势反转
        sell: recs[i].close < ma20[i]  // MA20以下止损
      };
    }
  },
  {
    name: 'S7_Optimal',
    desc: 'MA20 cross + MACD golden + 1yr Sharpe>0 + stop 5%',
    startIdx: Math.max(30, WINDOW_1YR),
    fn: (i, recs, sharpes1yr, s3, ma20, macdData) => {
      if (!ma20[i]) return { buy: false, sell: false };
      const s1idx = i - WINDOW_1YR;
      if (s1idx < 0 || s1idx >= sharpes1yr.length) return { buy: false, sell: false };
      const sharpe1 = sharpes1yr[s1idx];
      const { dif, dea, macdHist, offset } = macdData;
      const macdIdx = i - offset;
      if (macdIdx < 1 || macdIdx >= dif.length) return { buy: false, sell: false };
      
      // 金叉：DIF上穿DEA
      const goldenCross = dif[macdIdx] > dea[macdIdx - offset] && dif[macdIdx-1] <= dea[macdIdx - offset - 1];
      // 死叉：DIF下穿DEA
      const deathCross = dif[macdIdx] < dea[macdIdx - offset] && dif[macdIdx-1] >= dea[macdIdx - offset - 1];
      
      return {
        buy: recs[i].close > ma20[i] && goldenCross && sharpe1 > 0,
        sell: deathCross || recs[i].close < ma20[i]
      };
    }
  }
];

// ====== 主测试 ======

console.log('=== Rigorous Strategy Backtest ===\n');
console.log(`ETF Pool: ${etfPool.length} ETFs`);
console.log(`Strategies: ${strategyDefs.length}\n`);

const allResults = {};
strategyDefs.forEach(s => allResults[s.name] = []);

let tested = 0;

for (const etf of etfPool) {
  if (!etf.index_code) continue;
  
  const indexData = loadIndexData(etf.index_code);
  if (!indexData || indexData.records.length < WINDOW_3YR + 50) continue;
  
  const records = indexData.records;
  const returns = calcReturns(records);
  const sharpes1yr = calcRollingSharpe(returns, WINDOW_1YR);
  const sharpes3yr = calcRollingSharpe(returns, WINDOW_3YR);
  const ma20 = calcMA(records, 20);
  const macdData = calcMACD(records);
  const bhResult = buyHoldResult(records);
  
  tested++;
  
  for (const strat of strategyDefs) {
    const signalFn = (i, recs, isBuyCheck) => {
      return strat.fn(i, recs, sharpes1yr, sharpes3yr, ma20, macdData);
    };
    
    const result = rigorousBacktest(records, signalFn, 0.05);
    
    allResults[strat.name].push({
      code: etf.code,
      name: etf.name,
      index: etf.index,
      indexCode: etf.index_code,
      ...result,
      bhSharpe: bhResult.sharpe,
      bhReturn: bhResult.annReturn,
      bhDD: bhResult.maxDD,
      excess: result.annReturn - bhResult.annReturn,
      beatBH: result.annReturn > bhResult.annReturn
    });
  }
}

console.log(`Tested: ${tested} indices\n`);

// ====== 输出结果 ======

console.log('═══════════════════════════════════════════════════════════════════════════');
console.log('                          STRATEGY COMPARISON (Rigorous)                      ');
console.log('═══════════════════════════════════════════════════════════════════════════\n');

for (const strat of strategyDefs) {
  const arr = allResults[strat.name];
  const valid = arr.filter(r => r.trades > 0);
  const sharpeGte1 = valid.filter(r => r.sharpe >= 1.0).length;
  const sharpeGte05 = valid.filter(r => r.sharpe >= 0.5).length;
  const avgSharpe = valid.length > 0 ? valid.reduce((a, b) => a + b.sharpe, 0) / valid.length : 0;
  const avgReturn = valid.length > 0 ? valid.reduce((a, b) => a + b.annReturn, 0) / valid.length : 0;
  const avgDD = valid.length > 0 ? valid.reduce((a, b) => a + b.maxDD, 0) / valid.length : 0;
  const beatBH = valid.filter(r => r.beatBH).length;
  const avgExcess = valid.length > 0 ? valid.reduce((a, b) => a + b.excess, 0) / valid.length : 0;
  const avgTrades = valid.length > 0 ? valid.reduce((a, b) => a + b.trades, 0) / valid.length : 0;
  
  console.log(`${strat.name}: ${strat.desc}`);
  console.log(`  ETFs: ${valid.length}/${arr.length} | AvgSharpe: ${avgSharpe.toFixed(3)} | AvgAnn: ${(avgReturn*100).toFixed(1)}% | AvgDD: ${(avgDD*100).toFixed(1)}%`);
  console.log(`  Sharpe>=1.0: ${sharpeGte1} | Sharpe>=0.5: ${sharpeGte05} | Beat BH: ${beatBH}/${valid.length} | AvgExcess: ${(avgExcess*100).toFixed(1)}% | AvgTrades: ${avgTrades.toFixed(1)}`);
  
  // Top 3
  const top3 = valid.sort((a, b) => b.sharpe - a.sharpe).slice(0, 3);
  if (top3.length > 0) {
    console.log(`  Top 3:`);
    top3.forEach((r, i) => {
      const excSign = r.excess >= 0 ? '+' : '';
      console.log(`    ${i+1}. ${r.code}(${r.name}): Sharpe=${r.sharpe.toFixed(2)} Ann=${(r.annReturn*100).toFixed(1)}% DD=${(r.maxDD*100).toFixed(1)}% Trades=${r.trades} Excess=${excSign}${(r.excess*100).toFixed(1)}%`);
    });
  }
  console.log('');
}

// 总排名
console.log('═══════════════════════════════════════════════════════════════════════════');
console.log('                          FINAL RANKING                                       ');
console.log('═══════════════════════════════════════════════════════════════════════════\n');

const rankings = strategyDefs.map(strat => {
  const valid = allResults[strat.name].filter(r => r.trades > 0);
  const avgSharpe = valid.length > 0 ? valid.reduce((a, b) => a + b.sharpe, 0) / valid.length : -999;
  const sharpeGte1 = valid.filter(r => r.sharpe >= 1.0).length;
  const beatBH = valid.filter(r => r.beatBH).length;
  return { name: strat.name, desc: strat.desc, avgSharpe, sharpeGte1, beatBH: `${beatBH}/${valid.length}`, validCount: valid.length };
}).sort((a, b) => b.avgSharpe - a.avgSharpe);

rankings.forEach((r, i) => {
  console.log(`  ${i+1}. ${r.name.padEnd(18)} | AvgSharpe: ${r.avgSharpe.toFixed(3).padStart(7)} | Sharpe>=1: ${r.sharpeGte1} | Beat BH: ${r.beatBH} | ETFs: ${r.validCount}`);
});

// 夏普≥1.0的所有ETF
console.log('\n═══════════════════════════════════════════════════════════════════════════');
console.log('             ALL ETFs WITH Sharpe >= 1.0 (Any Strategy)                       ');
console.log('═══════════════════════════════════════════════════════════════════════════\n');

const excellent = [];
for (const strat of strategyDefs) {
  allResults[strat.name].filter(r => r.sharpe >= 1.0 && r.trades >= 3).forEach(r => {
    excellent.push({ ...r, strategy: strat.name });
  });
}

// 按ETF去重，只保留最佳策略
const bestByETF = {};
excellent.forEach(e => {
  if (!bestByETF[e.code] || e.sharpe > bestByETF[e.code].sharpe) {
    bestByETF[e.code] = e;
  }
});

const sortedExcellent = Object.values(bestByETF).sort((a, b) => b.sharpe - a.sharpe);
if (sortedExcellent.length > 0) {
  console.log('代码         名称                    策略            夏普   年化     回撤    交易  超额     胜率');
  console.log('─'.repeat(90));
  sortedExcellent.forEach(r => {
    const excSign = r.excess >= 0 ? '+' : '';
    console.log(`${r.code.padEnd(12)} ${r.name.padEnd(20)} ${r.strategy.padEnd(16)} ${r.sharpe.toFixed(2).padStart(5)} ${(r.annReturn*100).toFixed(1).padStart(4)}% ${(r.maxDD*100).toFixed(1).padStart(5)}% ${String(r.trades).padStart(5)} ${excSign}${(r.excess*100).toFixed(1).padStart(5)}% ${(r.winRate*100).toFixed(0).padStart(3)}%`);
  });
} else {
  console.log('No ETFs achieved Sharpe >= 1.0 with >= 3 trades.');
}

// 保存
fs.writeFileSync(RESULTS_FILE, JSON.stringify(allResults, null, 2));
console.log(`\n[Saved: ${RESULTS_FILE}]`);
