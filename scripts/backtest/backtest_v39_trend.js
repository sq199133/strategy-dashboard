// ============================================================
// MA20+MACD策略 v3.9 趋势强度过滤
// 新增：根据MA50/MA200判断趋势强度，动态调整买卖门槛
// ============================================================
'use strict';

const fs = require('fs');
const path = require('path');

// ════════════════════════════════════════════════════════════
// 技术指标
// ════════════════════════════════════════════════════════════

function SMA(prices, n) {
  const out = new Array(prices.length).fill(null);
  for (let i = n - 1; i < prices.length; i++) {
    let sum = 0;
    for (let j = i - n + 1; j <= i; j++) sum += prices[j];
    out[i] = sum / n;
  }
  return out;
}

function EMA(prices, n) {
  const k = 2 / (n + 1);
  const out = new Array(prices.length).fill(null);
  out[n - 1] = prices.slice(0, n).reduce((a, b) => a + b, 0) / n;
  for (let i = n; i < prices.length; i++) {
    out[i] = prices[i] * k + out[i - 1] * (1 - k);
  }
  return out;
}

function MACD(prices, fast = 12, slow = 26, signal = 9) {
  const emaFast = EMA(prices, fast);
  const emaSlow = EMA(prices, slow);
  const dif = new Array(prices.length).fill(null);
  for (let i = slow - 1; i < prices.length; i++) dif[i] = emaFast[i] - emaSlow[i];
  const sig = new Array(prices.length).fill(null);
  let first = null;
  for (let i = slow - 1; i < prices.length; i++) {
    if (first === null) { first = dif[i]; sig[i] = dif[i]; }
    else { sig[i] = dif[i] * (2 / (signal + 1)) + sig[i - 1] * (1 - 2 / (signal + 1)); }
  }
  const hist = new Array(prices.length).fill(null);
  for (let i = slow - 1; i < prices.length; i++) hist[i] = dif[i] - sig[i];
  return { dif, sig, hist };
}

// ════════════════════════════════════════════════════════════
// 趋势强度判断 (v3.9核心)
// ════════════════════════════════════════════════════════════

function getTrendStrength(prices, ma20, ma50, ma200, idx) {
  if (idx < 200 || !ma50[idx] || !ma200[idx]) return { level: 'unknown', label: '数据不足' };
  
  const price = prices[idx];
  const ma50Above200 = ma50[idx] > ma200[idx];
  const priceAboveMA50 = price > ma50[idx];
  const ma20Up = ma20[idx] > ma20[idx - 1];
  
  // 🟢 强多头：MA50>MA200 + 价格>MA50 + MA20向上
  if (ma50Above200 && priceAboveMA50 && ma20Up) {
    return { level: 'strong_bull', label: '🟢强多头', buyThreshold: 3, sellConfirm: true };
  }
  // 🔴 空头：MA50<MA200 + 价格<MA50
  if (!ma50Above200 && !priceAboveMA50) {
    return { level: 'bear', label: '🔴空头', buyThreshold: 5, sellConfirm: false, maxPosition: 0.5 };
  }
  // 🟡 中性/弱多头
  return { level: 'neutral', label: '🟡中性', buyThreshold: 4, sellConfirm: false };
}

// ════════════════════════════════════════════════════════════
// 五星评分 (简化版)
// ════════════════════════════════════════════════════════════

function calcStarScore(data, idx) {
  const prices = data.map(d => d.close);
  const vols = data.map(d => d.vol);
  const ma20 = SMA(prices, 20);
  const ma50 = SMA(prices, 50);
  const ma200 = SMA(prices, 200);
  const macd = MACD(prices);
  
  if (idx < 200) return { score: 0, stars: 0 };
  if (!ma20[idx] || !macd.dif[idx]) return { score: 0, stars: 0 };
  
  const price = prices[idx];
  let score = 0;
  
  // 趋势
  if (price > ma20[idx]) score++;
  if (ma50[idx] && ma20[idx] > ma50[idx]) score++;
  if (ma200[idx] && ma20[idx] > ma50[idx] && ma50[idx] > ma200[idx]) score += 2;
  if (ma20[idx] > ma20[idx - 1]) score++;
  
  // 动量
  const d = macd.dif[idx], dPrev = macd.dif[idx - 1];
  const s = macd.sig[idx], sPrev = macd.sig[idx - 1];
  const h = macd.hist[idx], hPrev = macd.hist[idx - 1];
  const goldX = dPrev <= sPrev && d > s && d > 0 && s > 0;
  if (goldX) score += 3;
  else if (dPrev <= sPrev && d > s) score++;
  if (h > 0 && hPrev > 0) score++;
  
  // 相对强弱 (简化：只看正动量)
  const pct20 = (price - prices[idx - 20]) / prices[idx - 20] * 100;
  if (pct20 > 0) score += 2;
  const pct5 = (price - prices[idx - 5]) / prices[idx - 5] * 100;
  if (pct5 > 0) score++;
  
  // 成交量
  const volMA20 = vols.slice(idx - 19, idx + 1).reduce((a, b) => a + b, 0) / 20;
  if (vols[idx] > volMA20 * 1.5) score++;
  
  let stars = 0;
  if (score >= 10) stars = 5;
  else if (score >= 8) stars = 4;
  else if (score >= 6) stars = 3;
  else if (score >= 4) stars = 2;
  else if (score >= 1) stars = 1;
  
  return { score, stars, goldX, aboveMA20: price > ma20[idx], ma20Up: ma20[idx] > ma20[idx - 1] };
}

// ════════════════════════════════════════════════════════════
// 回测引擎
// ════════════════════════════════════════════════════════════

function runBacktest(data, initialCapital, config) {
  const { useTrendFilter } = config;
  
  const trades = [];
  const equity = [];
  let capital = initialCapital;
  let position = 0;
  let avgCost = 0;
  let peak = initialCapital;
  let maxDD = 0;
  
  const prices = data.map(d => d.close);
  const ma20 = SMA(prices, 20);
  const ma50 = SMA(prices, 50);
  const ma200 = SMA(prices, 200);
  const macd = MACD(prices);
  
  let inCashDays = 0;
  let totalDays = 0;
  
  for (let i = 200; i < data.length; i++) {
    totalDays++;
    const price = prices[i];
    const scoreInfo = calcStarScore(data, i);
    const trend = useTrendFilter ? getTrendStrength(prices, ma20, ma50, ma200, i) : { level: 'neutral', buyThreshold: 4, sellConfirm: false };
    
    // ── 买入 ──
    if (position === 0) {
      const canBuy = scoreInfo.stars >= trend.buyThreshold && 
                     scoreInfo.goldX && 
                     scoreInfo.aboveMA20 && 
                     scoreInfo.ma20Up;
      
      if (canBuy) {
        let buyAmount = capital;
        if (trend.maxPosition) buyAmount *= trend.maxPosition;
        
        const shares = Math.floor(buyAmount / price / 100) * 100;
        if (shares > 0) {
          position = shares;
          avgCost = price;
          capital -= shares * price;
          trades.push({
            type: 'BUY', date: data[i].date, price, shares,
            trend: trend.label, stars: scoreInfo.stars,
            value: shares * price
          });
        }
      } else {
        inCashDays++;
      }
    }
    // ── 卖出 ──
    else if (position > 0) {
      const belowMA20 = price < ma20[i];
      const loss5pct = (price - avgCost) / avgCost <= -0.05;
      
      // MACD死叉确认
      const macdDeath = macd.dif[i - 1] > macd.sig[i - 1] && macd.dif[i] <= macd.sig[i];
      
      let shouldSell = false;
      let reason = '';
      
      if (loss5pct) {
        shouldSell = true;
        reason = '硬性止损-5%';
      } else if (trend.sellConfirm) {
        // 强多头：需要双确认
        if (belowMA20 && macdDeath) {
          shouldSell = true;
          reason = 'MA20跌破+MACD死叉';
        }
      } else {
        // 中性/空头：跌破MA20即卖
        if (belowMA20) {
          shouldSell = true;
          reason = '跌破MA20';
        }
      }
      
      if (shouldSell) {
        capital += position * price;
        const pnl = ((price - avgCost) / avgCost * 100);
        trades.push({
          type: 'SELL', date: data[i].date, price, shares: position,
          pnl: pnl.toFixed(2) + '%', reason, trend: trend.label
        });
        position = 0;
        avgCost = 0;
      }
    }
    
    // 净值
    const totalValue = capital + position * price;
    equity.push({ date: data[i].date, value: totalValue, trend: trend.level });
    if (totalValue > peak) peak = totalValue;
    const dd = (peak - totalValue) / peak * 100;
    if (dd > maxDD) maxDD = dd;
  }
  
  // 平仓
  if (position > 0) {
    const lastPrice = data[data.length - 1].close;
    capital += position * lastPrice;
    trades.push({ type: 'SELL', date: data[data.length - 1].date, price: lastPrice, shares: position, reason: '回测结束' });
  }
  
  return { trades, equity, finalValue: capital, maxDD, peak, inCashDays, totalDays };
}

// ════════════════════════════════════════════════════════════
// 统计
// ════════════════════════════════════════════════════════════

function calcStats(equity, initialCapital, maxDD, inCashDays, totalDays) {
  const finalV = equity[equity.length - 1].value;
  const totalRet = (finalV - initialCapital) / initialCapital;
  const years = (new Date(equity[equity.length - 1].date) - new Date(equity[0].date)) / (365.25 * 864e5);
  const cagr = Math.pow(finalV / initialCapital, 1 / years) - 1;
  
  const rets = [];
  for (let i = 1; i < equity.length; i++) {
    rets.push((equity[i].value - equity[i - 1].value) / equity[i - 1].value);
  }
  const avgR = rets.reduce((a, b) => a + b, 0) / rets.length;
  const stdR = Math.sqrt(rets.reduce((a, b) => a + Math.pow(b - avgR, 2), 0) / rets.length);
  const annStd = stdR * Math.sqrt(252);
  const sharpe = annStd > 0 ? (cagr - 0.03) / annStd : 0;
  
  return { finalV, totalRet, cagr, sharpe, maxDD, years, cashRatio: inCashDays / totalDays };
}

function tradeStats(trades) {
  const sells = trades.filter(t => t.type === 'SELL' && !t.reason.includes('回测'));
  const buys = trades.filter(t => t.type === 'BUY');
  if (sells.length === 0) return { count: buys.length, winRate: 0, avgWin: 0, avgLoss: 0 };
  
  const pnls = sells.map(t => parseFloat(t.pnl));
  const wins = pnls.filter(p => p > 0);
  const loses = pnls.filter(p => p <= 0);
  const winRate = wins.length / sells.length;
  const avgWin = wins.length > 0 ? wins.reduce((a, b) => a + b, 0) / wins.length : 0;
  const avgLoss = loses.length > 0 ? loses.reduce((a, b) => a + b, 0) / loses.length : 0;
  
  return { count: buys.length, wins: wins.length, losses: loses.length, winRate, avgWin, avgLoss };
}

// ════════════════════════════════════════════════════════════
// 主程序
// ════════════════════════════════════════════════════════════

async function main() {
  console.log('\n' + '='.repeat(80));
  console.log('   MA20+MACD策略 v3.9 趋势强度过滤回测');
  console.log('   新增: 根据MA50/MA200动态调整买卖门槛');
  console.log('='.repeat(80) + '\n');
  
  const histFile = path.join(__dirname, '..', '..', 'data', 'history', 'sh000300.json');
  let data;
  try {
    data = JSON.parse(fs.readFileSync(histFile, 'utf8'));
    data = data.map(d => ({ date: d.date, open: d.open, close: d.close, high: d.high, low: d.low, vol: d.volume || 0 }));
  } catch (e) {
    console.error('❌ 读取数据失败:', e.message);
    process.exit(1);
  }
  console.log(`📥 ${data.length} 条数据 (${data[0].date} ~ ${data[data.length - 1].date})\n`);
  
  const ICAP = 1000000;
  
  // v3.7 基准（无趋势过滤）
  console.log('🔄 v3.7 基准回测...');
  const r37 = runBacktest(data, ICAP, { useTrendFilter: false });
  const s37 = calcStats(r37.equity, ICAP, r37.maxDD, r37.inCashDays, r37.totalDays);
  const t37 = tradeStats(r37.trades);
  
  // v3.9 趋势过滤
  console.log('🔄 v3.9 趋势过滤回测...');
  const r39 = runBacktest(data, ICAP, { useTrendFilter: true });
  const s39 = calcStats(r39.equity, ICAP, r39.maxDD, r39.inCashDays, r39.totalDays);
  const t39 = tradeStats(r39.trades);
  
  // 买入持有
  const bhShares = Math.floor(ICAP / data[200].close);
  const bhFinal = bhShares * data[data.length - 1].close;
  const bhCAGR = Math.pow(bhFinal / (bhShares * data[200].close), 1 / s37.years) - 1;
  
  // ════════════════════════════════════════════════════════════
  // 输出
  // ════════════════════════════════════════════════════════════
  
  console.log('\n' + '='.repeat(80));
  console.log('   📊 回测结果对比');
  console.log('='.repeat(80));
  console.log(`   区间: ${data[200].date} → ${data[data.length - 1].date} (${s37.years.toFixed(1)}年)\n`);
  
  const pad = (s, n) => String(s).padEnd(n);
  
  console.log('   ┌──────────────────────────┬──────────────┬──────────────┬──────────────┐');
  console.log('   │ 指标                     │    v3.7基准   │    v3.9趋势   │   买入持有   │');
  console.log('   ├──────────────────────────┼──────────────┼──────────────┼──────────────┤');
  
  const rows = [
    ['期末资金', `¥${Math.round(s37.finalV).toLocaleString()}`, `¥${Math.round(s39.finalV).toLocaleString()}`, `¥${Math.round(bhFinal).toLocaleString()}`],
    ['总收益率', `${(s37.totalRet * 100).toFixed(2)}%`, `${(s39.totalRet * 100).toFixed(2)}%`, `${((bhFinal / (bhShares * data[200].close) - 1) * 100).toFixed(2)}%`],
    ['年化收益率', `${(s37.cagr * 100).toFixed(2)}%`, `${(s39.cagr * 100).toFixed(2)}%`, `${(bhCAGR * 100).toFixed(2)}%`],
    ['最大回撤', `${s37.maxDD.toFixed(2)}%`, `${s39.maxDD.toFixed(2)}%`, '—'],
    ['夏普比率', `${s37.sharpe.toFixed(2)}`, `${s39.sharpe.toFixed(2)}`, '—'],
    ['交易次数', `${t37.count}`, `${t39.count}`, '1'],
    ['胜率', t37.winRate > 0 ? `${(t37.winRate * 100).toFixed(1)}%` : '—', t39.winRate > 0 ? `${(t39.winRate * 100).toFixed(1)}%` : '—', '—'],
    ['平均盈利', t37.avgWin > 0 ? `+${t37.avgWin.toFixed(2)}%` : '—', t39.avgWin > 0 ? `+${t39.avgWin.toFixed(2)}%` : '—', '—'],
    ['平均亏损', t37.avgLoss !== 0 ? `${t37.avgLoss.toFixed(2)}%` : '—', t39.avgLoss !== 0 ? `${t39.avgLoss.toFixed(2)}%` : '—', '—'],
    ['空仓比例', `${(s37.cashRatio * 100).toFixed(1)}%`, `${(s39.cashRatio * 100).toFixed(1)}%`, '0%'],
  ];
  
  for (const [k, v1, v2, v3] of rows) {
    console.log(`   │ ${pad(k, 24)} │ ${pad(v1, 12)} │ ${pad(v2, 12)} │ ${pad(v3, 12)} │`);
  }
  console.log('   └──────────────────────────┴──────────────┴──────────────┴──────────────┘');
  
  // 改善分析
  console.log('\n' + '-'.repeat(80));
  console.log('   📈 v3.9 vs v3.7 改善分析');
  console.log('-'.repeat(80));
  const cagrDiff = ((s39.cagr - s37.cagr) * 100).toFixed(2);
  const ddDiff = (s39.maxDD - s37.maxDD).toFixed(2);
  const cashDiff = ((s39.cashRatio - s37.cashRatio) * 100).toFixed(1);
  
  console.log(`   CAGR变化: ${cagrDiff > 0 ? '+' : ''}${cagrDiff}%`);
  console.log(`   最大回撤变化: ${ddDiff > 0 ? '+' : ''}${ddDiff}% (负为改善)`);
  console.log(`   空仓比例变化: ${cashDiff > 0 ? '+' : ''}${cashDiff}% (负为更多持仓)`);
  console.log(`   交易次数变化: ${t39.count - t37.count > 0 ? '+' : ''}${t39.count - t37.count}`);
  
  // 详细交易
  console.log('\n' + '-'.repeat(80));
  console.log('   📋 v3.9 交易明细');
  console.log('-'.repeat(80));
  r39.trades.slice(-15).forEach(t => {
    if (t.type === 'BUY') {
      console.log(`   🟢 ${t.date} ¥${t.price.toFixed(2)} ${t.trend} ⭐${t.stars}`);
    } else {
      console.log(`   🔴 ${t.date} ¥${t.price.toFixed(2)} ${t.pnl || ''} [${t.reason}] ${t.trend || ''}`);
    }
  });
  
  // 趋势分布
  console.log('\n' + '-'.repeat(80));
  console.log('   📊 趋势强度分布（最后一天）');
  console.log('-'.repeat(80));
  const trendCounts = { strong_bull: 0, neutral: 0, bear: 0 };
  r39.equity.slice(-252).forEach(e => {
    if (e.trend === 'strong_bull') trendCounts.strong_bull++;
    else if (e.trend === 'bear') trendCounts.bear++;
    else trendCounts.neutral++;
  });
  console.log(`   近一年: 🟢强多头 ${trendCounts.strong_bull}天 | 🟡中性 ${trendCounts.neutral}天 | 🔴空头 ${trendCounts.bear}天`);
  
  // 保存
  const outDir = path.join(__dirname, '..', '..', 'reviews', 'backtest');
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, `v39_trend_filter_${new Date().toISOString().slice(0, 10)}.json`);
  fs.writeFileSync(outFile, JSON.stringify({ v37: { stats: s37, trades: r37.trades }, v39: { stats: s39, trades: r39.trades } }, null, 2));
  console.log(`\n📁 已保存: ${outFile}`);
  
  console.log('\n' + '='.repeat(80) + '\n');
}

main().catch(console.error);
