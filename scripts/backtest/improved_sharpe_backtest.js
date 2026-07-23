/**
 * 夏普策略改进版回测
 * 测试方向：
 * 1. 反向信号：夏普<0时买入（抄底）
 * 2. 夏普过滤 + MA20/MACD趋势框架
 * 3. 多窗口共振（1年+3年）
 * 4. 行业轮动
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const INDEX_HISTORY_DIR = 'D:/QClaw_Trading/data/index_history';
const ETF_POOL_FILE = 'D:/QClaw_Trading/data/etf_pool_v5.json';
const RESULTS_FILE = 'D:/QClaw_Trading/scripts/backtest/improved_sharpe_results.json';

// 加载指数名称到代码的映射
const INDEX_NAME_MAP = require('./index_mapping.js');

// 加载ETF池
let etfPool = [];
try {
  etfPool = JSON.parse(fs.readFileSync(ETF_POOL_FILE, 'utf-8'));
  console.log(`Loaded ${etfPool.length} ETFs from pool`);
} catch (e) {
  console.error('Failed to load ETF pool:', e.message);
  process.exit(1);
}

// 为每个ETF添加指数代码
for (const etf of etfPool) {
  const indexName = etf.index || etf.idxName;
  etf.index_code = INDEX_NAME_MAP[indexName] || null;
}

// 加载指数数据
function loadIndexData(indexCode) {
  const filePath = path.join(INDEX_HISTORY_DIR, `${indexCode}.json`);
  if (!fs.existsSync(filePath)) return null;
  
  try {
    const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    if (!data.records || Object.keys(data.records).length === 0) return null;
    
    // 转换为数组并排序（时间正序）
    const records = Object.values(data.records).map(r => ({
      date: r.date,
      open: parseFloat(r.open),
      close: parseFloat(r.close),
      high: parseFloat(r.high),
      low: parseFloat(r.low),
      vol: parseFloat(r.vol || 0)
    })).sort((a, b) => a.date.localeCompare(b.date));
    
    return { ...data, records };
  } catch (e) {
    return null;
  }
}

// 计算收益率序列
function calcReturns(records) {
  const returns = [];
  for (let i = 1; i < records.length; i++) {
    const ret = (records[i].close - records[i-1].close) / records[i-1].close;
    returns.push(ret);
  }
  return returns;
}

// 计算滚动夏普
function calcRollingSharpe(returns, window) {
  const sharpes = [];
  for (let i = window; i <= returns.length; i++) {
    const slice = returns.slice(i - window, i);
    const mean = slice.reduce((a, b) => a + b, 0) / slice.length;
    const std = Math.sqrt(slice.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / slice.length);
    const sharpe = std > 0 ? (mean * 252) / (std * Math.sqrt(252)) : 0; // 年化
    sharpes.push(sharpe);
  }
  return sharpes;
}

// 计算MA
function calcMA(records, period) {
  const mas = [];
  for (let i = period - 1; i < records.length; i++) {
    const sum = records.slice(i - period + 1, i + 1).reduce((a, b) => a + b.close, 0);
    mas.push(sum / period);
  }
  return mas;
}

// 计算MACD
function calcMACD(records) {
  const closes = records.map(r => r.close);
  
  // EMA计算
  function ema(data, period) {
    const k = 2 / (period + 1);
    const emas = [data.slice(0, period).reduce((a, b) => a + b, 0) / period];
    for (let i = period; i < data.length; i++) {
      emas.push(data[i] * k + emas[emas.length - 1] * (1 - k));
    }
    return emas;
  }
  
  const ema12 = ema(closes, 12);
  const ema26 = ema(closes, 26);
  const minLen = Math.min(ema12.length, ema26.length);
  
  const dif = [];
  for (let i = 0; i < minLen; i++) {
    dif.push(ema12[ema12.length - minLen + i] - ema26[ema26.length - minLen + i]);
  }
  
  const dea = ema(dif, 9);
  const macd = dif.slice(8).map((d, i) => (d - dea[i]) * 2);
  
  return { dif: dif.slice(8), dea, macd };
}

// 回测策略
function backtest(records, strategy) {
  const returns = calcReturns(records);
  const trades = [];
  let position = false;
  let entryPrice = 0;
  let entryDate = '';
  let equity = 1;
  
  for (let i = strategy.startIdx; i < records.length; i++) {
    const signal = strategy.getSignal(i, records, returns);
    const price = records[i].close;
    const date = records[i].date;
    
    if (!position && signal.buy) {
      position = true;
      entryPrice = price;
      entryDate = date;
    } else if (position && signal.sell) {
      position = false;
      const pnl = (price - entryPrice) / entryPrice;
      equity *= (1 + pnl);
      trades.push({
        entryDate,
        exitDate: date,
        entryPrice,
        exitPrice: price,
        pnl,
        equity: equity
      });
    }
  }
  
  // 强制平仓
  if (position) {
    const lastRecord = records[records.length - 1];
    const pnl = (lastRecord.close - entryPrice) / entryPrice;
    equity *= (1 + pnl);
    trades.push({
      entryDate,
      exitDate: lastRecord.date,
      entryPrice,
      exitPrice: lastRecord.close,
      pnl,
      equity
    });
  }
  
  // 计算绩效
  if (trades.length === 0) {
    return { trades: 0, sharpe: 0, annReturn: 0, maxDD: 0, winRate: 0, years: 0, equity: 1 };
  }
  
  const years = (new Date(records[records.length-1].date) - new Date(records[0].date)) / (365.25 * 24 * 3600 * 1000);
  const annReturn = Math.pow(equity, 1/years) - 1;
  
  // 最大回撤
  let maxEquity = 1;
  let maxDD = 0;
  let curEquity = 1;
  for (const trade of trades) {
    curEquity = trade.equity;
    maxEquity = Math.max(maxEquity, curEquity);
    maxDD = Math.max(maxDD, (maxEquity - curEquity) / maxEquity);
  }
  
  const winRate = trades.filter(t => t.pnl > 0).length / trades.length;
  
  // 计算夏普
  const dailyReturns = [];
  for (let i = 1; i < trades.length; i++) {
    const days = (new Date(trades[i].exitDate) - new Date(trades[i-1].exitDate)) / (24 * 3600 * 1000);
    if (days > 0) {
      dailyReturns.push((trades[i].equity / trades[i-1].equity - 1) / days);
    }
  }
  const avgRet = dailyReturns.reduce((a, b) => a + b, 0) / dailyReturns.length;
  const stdRet = Math.sqrt(dailyReturns.reduce((a, b) => a + Math.pow(b - avgRet, 2), 0) / dailyReturns.length);
  const sharpe = stdRet > 0 ? (avgRet * 252) / (stdRet * Math.sqrt(252)) : 0;
  
  return { trades: trades.length, sharpe, annReturn, maxDD, winRate, years, equity };
}

// 买入持有基准
function buyHold(records) {
  const years = (new Date(records[records.length-1].date) - new Date(records[0].date)) / (365.25 * 24 * 3600 * 1000);
  const totalReturn = (records[records.length-1].close - records[0].close) / records[0].close;
  const annReturn = Math.pow(1 + totalReturn, 1/years) - 1;
  
  // 最大回撤
  let maxPrice = records[0].close;
  let maxDD = 0;
  for (const r of records) {
    maxPrice = Math.max(maxPrice, r.close);
    maxDD = Math.max(maxDD, (maxPrice - r.close) / maxPrice);
  }
  
  // 夏普
  const returns = calcReturns(records);
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const std = Math.sqrt(returns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / returns.length);
  const sharpe = std > 0 ? (mean * 252) / (std * Math.sqrt(252)) : 0;
  
  return { sharpe, annReturn, maxDD, years };
}

// 主测试
console.log('=== Improved Sharpe Strategy Backtest ===\n');

const WINDOW_1YR = 252;
const WINDOW_3YR = 756;

// 收集结果
const results = {
  reverse: [],     // 反向信号
  ma20_only: [],    // MA20趋势
  ma20_sharpe: [],  // MA20 + 夏普过滤
  macd_only: [],    // MACD金叉
  macd_sharpe: [],  // MACD + 夏普过滤
  combined: [],     // AMA20+MACD+夏普
  multi_window: []  // 多窗口共振
};

let tested = 0;
let skipped = 0;

for (const etf of etfPool) {
  const indexCode = etf.index_code || etf.idxCode;
  if (!indexCode) continue;
  
  const indexData = loadIndexData(indexCode);
  if (!indexData || indexData.records.length < WINDOW_3YR + 50) {
    skipped++;
    continue;
  }
  
  const records = indexData.records;
  const returns = calcReturns(records);
  const sharpes3yr = calcRollingSharpe(returns, WINDOW_3YR);
  const sharpes1yr = calcRollingSharpe(returns, WINDOW_1YR);
  const ma20 = calcMA(records, 20);
  const macd = calcMACD(records);
  
  tested++;
  
  // ===== 策略1: 反向信号 (夏普<0时买入，>0时卖出) =====
  const reverseStrategy = {
    startIdx: WINDOW_3YR,
    getSignal: (i, recs, rets) => {
      const sharpIdx = i - WINDOW_3YR;
      if (sharpIdx < 0 || sharpIdx >= sharpes3yr.length) return { buy: false, sell: false };
      const sharpe3 = sharpes3yr[sharpIdx];
      return {
        buy: sharpe3 < 0,  // 抄底
        sell: sharpe3 > 0.5  // 止盈
      };
    }
  };
  
  const reverseResult = backtest(records, reverseStrategy);
  const bhResult = buyHold(records);
  
  results.reverse.push({
    code: etf.code,
    name: etf.name,
    indexCode,
    sharpe: reverseResult.sharpe,
    annReturn: reverseResult.annReturn,
    maxDD: reverseResult.maxDD,
    trades: reverseResult.trades,
    bhSharpe: bhResult.sharpe,
    bhReturn: bhResult.annReturn,
    bhDD: bhResult.maxDD,
    years: reverseResult.years,
    excess: reverseResult.annReturn - bhResult.annReturn,
    beat: reverseResult.annReturn > bhResult.annReturn
  });
  
  // ===== 策略2: MA20趋势法则 =====
  const ma20Strategy = {
    startIdx: 21,
    getSignal: (i, recs) => {
      if (i < ma20.length) return { buy: false, sell: false };
      const maIdx = i - 20;
      return {
        buy: recs[i].close > ma20[maIdx] && recs[i-1].close <= ma20[maIdx - 1],
        sell: recs[i].close < ma20[maIdx] && recs[i-1].close >= ma20[maIdx - 1]
      };
    }
  };
  
  const ma20Result = backtest(records, ma20Strategy);
  results.ma20_only.push({
    code: etf.code, name: etf.name,
    sharpe: ma20Result.sharpe, annReturn: ma20Result.annReturn,
    maxDD: ma20Result.maxDD, trades: ma20Result.trades
  });
  
  // ===== 策略3: MA20 + 夏普过滤 (只在夏普>0时交易) =====
  const ma20SharpeStrategy = {
    startIdx: Math.max(21, WINDOW_1YR),
    getSignal: (i, recs) => {
      if (i < ma20.length || i - WINDOW_1YR >= sharpes1yr.length) return { buy: false, sell: false };
      const maIdx = i - 20;
      const sharpIdx = i - WINDOW_1YR;
      const sharpe1 = sharpes1yr[sharpIdx];
      const aboveMA = recs[i].close > ma20[maIdx];
      const wasBelow = recs[i-1].close <= ma20[maIdx - 1];
      const belowMA = recs[i].close < ma20[maIdx];
      const wasAbove = recs[i-1].close >= ma20[maIdx - 1];
      
      return {
        buy: aboveMA && wasBelow && sharpe1 > 0,  // 只在夏普>0时买入
        sell: belowMA && wasAbove
      };
    }
  };
  
  const ma20SharpeResult = backtest(records, ma20SharpeStrategy);
  results.ma20_sharpe.push({
    code: etf.code, name: etf.name,
    sharpe: ma20SharpeResult.sharpe, annReturn: ma20SharpeResult.annReturn,
    maxDD: ma20SharpeResult.maxDD, trades: ma20SharpeResult.trades
  });
  
  // ===== 策略4: MACD金叉 =====
  const macdStrategy = {
    startIdx: records.length - macd.macd.length + 1,
    getSignal: (i, recs) => {
      const macdIdx = records.length - 1 - i;
      if (macdIdx < 1 || macdIdx >= macd.macd.length) return { buy: false, sell: false };
      const currMacd = macd.macd[macd.macd.length - 1 - macdIdx];
      const prevMacd = macd.macd[macd.macd.length - macdIdx];
      return {
        buy: prevMacd < 0 && currMacd > 0,  // 金叉
        sell: prevMacd > 0 && currMacd < 0  // 死叉
      };
    }
  };
  
  const macdResult = backtest(records, macdStrategy);
  results.macd_only.push({
    code: etf.code, name: etf.name,
    sharpe: macdResult.sharpe, annReturn: macdResult.annReturn,
    maxDD: macdResult.maxDD, trades: macdResult.trades
  });
  
  // ===== 策略5: MACD + 夏普过滤 =====
  const macdSharpeStrategy = {
    startIdx: Math.max(records.length - macd.macd.length + 1, WINDOW_1YR),
    getSignal: (i, recs) => {
      const macdIdx = records.length - 1 - i;
      const sharpIdx = i - WINDOW_1YR;
      if (macdIdx < 1 || macdIdx >= macd.macd.length || sharpIdx < 0) return { buy: false, sell: false };
      const currMacd = macd.macd[macd.macd.length - 1 - macdIdx];
      const prevMacd = macd.macd[macd.macd.length - macdIdx];
      const sharpe1 = sharpes1yr[sharpIdx];
      
      return {
        buy: prevMacd < 0 && currMacd > 0 && sharpe1 > 0,  // 金叉+夏普>0
        sell: prevMacd > 0 && currMacd < 0
      };
    }
  };
  
  const macdSharpeResult = backtest(records, macdSharpeStrategy);
  results.macd_sharpe.push({
    code: etf.code, name: etf.name,
    sharpe: macdSharpeResult.sharpe, annReturn: macdSharpeResult.annReturn,
    maxDD: macdSharpeResult.maxDD, trades: macdSharpeResult.trades
  });
  
  // ===== 策略6: 综合策略 (MA20+MACD+夏普) =====
  const combinedStrategy = {
    startIdx: Math.max(30, WINDOW_1YR),
    getSignal: (i, recs) => {
      if (i < ma20.length || i - WINDOW_1YR >= sharpes1yr.length) return { buy: false, sell: false };
      const maIdx = i - 20;
      const sharpIdx = i - WINDOW_1YR;
      const sharpe1 = sharpes1yr[sharpIdx];
      const macdIdx = records.length - 1 - i;
      
      const aboveMA = recs[i].close > ma20[maIdx];
      const belowMA = recs[i].close < ma20[maIdx];
      
      let macdSignal = 0;
      if (macdIdx >= 0 && macdIdx < macd.macd.length) {
        const currMacd = macd.macd[macd.macd.length - 1 - macdIdx];
        macdSignal = currMacd > 0 ? 1 : (currMacd < 0 ? -1 : 0);
      }
      
      // 买入：价格在MA20上方 + MACD红柱 + 1年夏普>0
      const buySignal = aboveMA && macdSignal > 0 && sharpe1 > 0;
      // 卖出：价格跌破MA20 或 MACD死叉
      const sellSignal = belowMA || macdSignal < 0;
      
      return { buy: buySignal, sell: sellSignal };
    }
  };
  
  const combinedResult = backtest(records, combinedStrategy);
  results.combined.push({
    code: etf.code, name: etf.name,
    sharpe: combinedResult.sharpe, annReturn: combinedResult.annReturn,
    maxDD: combinedResult.maxDD, trades: combinedResult.trades
  });
  
  // ===== 策略7: 多窗口共振 (1年夏普>0.5 且 3年夏普>0) =====
  const multiWindowStrategy = {
    startIdx: WINDOW_3YR,
    getSignal: (i, recs) => {
      const sharpIdx1 = i - WINDOW_1YR;
      const sharpIdx3 = i - WINDOW_3YR;
      if (sharpIdx1 < 0 || sharpIdx1 >= sharpes1yr.length || sharpIdx3 < 0 || sharpIdx3 >= sharpes3yr.length) {
        return { buy: false, sell: false };
      }
      
      const sharpe1 = sharpes1yr[sharpIdx1];
      const sharpe3 = sharpes3yr[sharpIdx3];
      const maIdx = i - 20;
      
      // 买入：双窗口夏普共振 + 价格在MA20上方
      const buySignal = sharpe1 > 0.5 && sharpe3 > 0 && recs[i].close > ma20[maIdx];
      // 卖出：任一夏普转负
      const sellSignal = sharpe1 < 0 || sharpe3 < 0;
      
      return { buy: buySignal, sell: sellSignal };
    }
  };
  
  const multiResult = backtest(records, multiWindowStrategy);
  results.multi_window.push({
    code: etf.code, name: etf.name,
    sharpe: multiResult.sharpe, annReturn: multiResult.annReturn,
    maxDD: multiResult.maxDD, trades: multiResult.trades
  });
}

// 汇总统计
function summarize(arr, key) {
  const valid = arr.filter(r => r.trades > 0 || r.sharpe !== undefined);
  const sharpes = valid.map(r => r.sharpe).filter(s => isFinite(s));
  const returns = valid.map(r => r.annReturn).filter(r => isFinite(r));
  const dds = valid.map(r => r.maxDD).filter(d => isFinite(d));
  const beats = valid.filter(r => r.beat !== undefined ? r.beat : r.annReturn > 0).length;
  
  return {
    count: valid.length,
    avgSharpe: sharpes.length ? (sharpes.reduce((a,b) => a+b, 0) / sharpes.length).toFixed(3) : 'N/A',
    avgReturn: returns.length ? (returns.reduce((a,b) => a+b, 0) / returns.length * 100).toFixed(1) + '%' : 'N/A',
    avgDD: dds.length ? (dds.reduce((a,b) => a+b, 0) / dds.length * 100).toFixed(1) + '%' : 'N/A',
    sharpeGte1: sharpes.filter(s => s >= 1.0).length,
    sharpeGte05: sharpes.filter(s => s >= 0.5).length,
    beatsDesc: arr === results.reverse ? `${beats}/${valid.length} beat BH` : `${beats}/${valid.length} positive`
  };
}

// 打印结果
console.log(`Tested: ${tested} indices, Skipped: ${skipped} (insufficient data)\n`);

console.log('═══════════════════════════════════════════════════════════════');
console.log('                      STRATEGY COMPARISON                        ');
console.log('═══════════════════════════════════════════════════════════════\n');

// 策略1: 反向信号
const r1 = summarize(results.reverse, 'reverse');
console.log('策略1: 反向信号 (3年夏普<0时买入，>0.5时卖出)');
console.log(`  ─────────────────────────────────────────────────────────────`);
console.log(`  测试数量: ${r1.count} | 平均夏普: ${r1.avgSharpe} | 平均年化: ${r1.avgReturn} | 平均回撤: ${r1.avgDD}`);
console.log(`  夏普≥1.0: ${r1.sharpeGte1} | 夏普≥0.5: ${r1.sharpeGte05} | ${r1.beatsDesc}`);

// 找出表现最好的
const topReverse = results.reverse.filter(r => r.trades > 0).sort((a, b) => b.sharpe - a.sharpe).slice(0, 5);
if (topReverse.length > 0) {
  console.log('\n  Top 5 反向信号:');
  topReverse.forEach((r, i) => {
    const excSign = r.excess >= 0 ? '+' : '';
    console.log(`    ${i+1}. ${r.code}(${r.name}): 夏普${r.sharpe.toFixed(2)} 年化${(r.annReturn*100).toFixed(1)}% 回撤${(r.maxDD*100).toFixed(1)}% 超额${excSign}${(r.excess*100).toFixed(1)}%`);
  });
}

// 策略2: MA20趋势
const r2 = summarize(results.ma20_only);
console.log('\n\n策略2: MA20趋势法则 (价格上穿MA20买入，下穿卖出)');
console.log(`  ─────────────────────────────────────────────────────────────`);
console.log(`  测试数量: ${r2.count} | 平均夏普: ${r2.avgSharpe} | 平均年化: ${r2.avgReturn} | 平均回撤: ${r2.avgDD}`);
console.log(`  夏普≥1.0: ${r2.sharpeGte1} | 夏普≥0.5: ${r2.sharpeGte05} | ${r2.beatsDesc}`);

// 策略3: MA20+夏普过滤
const r3 = summarize(results.ma20_sharpe);
console.log('\n\n策略3: MA20趋势 + 夏普过滤 (只在1年夏普>0时买入)');
console.log(`  ─────────────────────────────────────────────────────────────`);
console.log(`  测试数量: ${r3.count} | 平均夏普: ${r3.avgSharpe} | 平均年化: ${r3.avgReturn} | 平均回撤: ${r3.avgDD}`);
console.log(`  夏普≥1.0: ${r3.sharpeGte1} | 夏普≥0.5: ${r3.sharpeGte05} | ${r3.beatsDesc}`);
console.log(`  vs 策略2: ${r3.avgSharpe > r2.avgSharpe ? '✓ 提升' : '✗ 降低'} 夏普 ${r2.avgSharpe} → ${r3.avgSharpe}`);

// 策略4: MACD金叉
const r4 = summarize(results.macd_only);
console.log('\n\n策略4: MACD金叉/死叉');
console.log(`  ─────────────────────────────────────────────────────────────`);
console.log(`  测试数量: ${r4.count} | 平均夏普: ${r4.avgSharpe} | 平均年化: ${r4.avgReturn} | 平均回撤: ${r4.avgDD}`);
console.log(`  夏普≥1.0: ${r4.sharpeGte1} | 夏普≥0.5: ${r4.sharpeGte05} | ${r4.beatsDesc}`);

// 策略5: MACD+夏普过滤
const r5 = summarize(results.macd_sharpe);
console.log('\n\n策略5: MACD金叉 + 夏普过滤 (只在1年夏普>0时买入)');
console.log(`  ─────────────────────────────────────────────────────────────`);
console.log(`  测试数量: ${r5.count} | 平均夏普: ${r5.avgSharpe} | 平均年化: ${r5.avgReturn} | 平均回撤: ${r5.avgDD}`);
console.log(`  夏普≥1.0: ${r5.sharpeGte1} | 夏普≥0.5: ${r5.sharpeGte05} | ${r5.beatsDesc}`);
console.log(`  vs 策略4: ${r5.avgSharpe > r4.avgSharpe ? '✓ 提升' : '✗ 降低'} 夏普 ${r4.avgSharpe} → ${r5.avgSharpe}`);

// 策略6: 综合策略
const r6 = summarize(results.combined);
console.log('\n\n策略6: 综合策略 (MA20上方 + MACD红柱 + 1年夏普>0)');
console.log(`  ─────────────────────────────────────────────────────────────`);
console.log(`  测试数量: ${r6.count} | 平均夏普: ${r6.avgSharpe} | 平均年化: ${r6.avgReturn} | 平均回撤: ${r6.avgDD}`);
console.log(`  夏普≥1.0: ${r6.sharpeGte1} | 夏普≥0.5: ${r6.sharpeGte05} | ${r6.beatsDesc}`);

// 策略7: 多窗口共振
const r7 = summarize(results.multi_window);
console.log('\n\n策略7: 多窗口共振 (1年夏普>0.5 且 3年夏普>0 + MA20上方)');
console.log(`  ─────────────────────────────────────────────────────────────`);
console.log(`  测试数量: ${r7.count} | 平均夏普: ${r7.avgSharpe} | 平均年化: ${r7.avgReturn} | 平均回撤: ${r7.avgDD}`);
console.log(`  夏普≥1.0: ${r7.sharpeGte1} | 夏普≥0.5: ${r7.sharpeGte05} | ${r7.beatsDesc}`);

// 找出最佳策略
const allStrategies = [
  { name: '反向信号', data: r1 },
  { name: 'MA20趋势', data: r2 },
  { name: 'MA20+夏普', data: r3 },
  { name: 'MACD金叉', data: r4 },
  { name: 'MACD+夏普', data: r5 },
  { name: '综合策略', data: r6 },
  { name: '多窗口共振', data: r7 }
];

const avgSharpes = allStrategies.map(s => ({
  name: s.name,
  sharpe: parseFloat(s.data.avgSharpe) || 0,
  count: s.data.sharpeGte1,
  positive: s.data.sharpeGte05
})).sort((a, b) => b.sharpe - a.sharpe);

console.log('\n\n═══════════════════════════════════════════════════════════════');
console.log('                      策略排名 (按平均夏普)                        ');
console.log('═══════════════════════════════════════════════════════════════\n');

avgSharpes.forEach((s, i) => {
  console.log(`  ${i+1}. ${s.name.padEnd(12)} | 平均夏普 ${(s.sharpe).toFixed(3)} | 夏普≥1.0数量: ${s.count} | 夏普≥0.5数量: ${s.positive}`);
});

// 保存结果
fs.writeFileSync(RESULTS_FILE, JSON.stringify(results, null, 2));
console.log(`\n[Saved: ${RESULTS_FILE}]`);

// 详细输出夏普≥1.0的ETF
console.log('\n\n═══════════════════════════════════════════════════════════════');
console.log('          夏普≥1.0 的优异表现ETF (所有策略)                         ');
console.log('═══════════════════════════════════════════════════════════════\n');

const excellentEFTs = [];
for (const strategy of allStrategies) {
  const arr = results[strategy.name.toLowerCase().replace(/[^\w]/g, '_')];
  if (!arr) continue;
  arr.filter(r => r.sharpe >= 1.0).forEach(r => {
    excellentEFTs.push({ ...r, strategy: strategy.name });
  });
}

const uniqueExcellent = {};
excellentEFTs.forEach(e => {
  if (!uniqueExcellent[e.code] || e.sharpe > uniqueExcellent[e.code].sharpe) {
    uniqueExcellent[e.code] = e;
  }
});

Object.values(uniqueExcellent)
  .sort((a, b) => b.sharpe - a.sharpe)
  .slice(0, 10)
  .forEach((e, i) => {
    console.log(`  ${i+1}. ${e.code}(${e.name}) [${e.strategy}]: 夏普${e.sharpe.toFixed(2)} 年化${(e.annReturn*100).toFixed(1)}% 回撤${(e.maxDD*100).toFixed(1)}%`);
  });
