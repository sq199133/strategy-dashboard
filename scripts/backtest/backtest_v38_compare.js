// ============================================================
// MA20+MACD策略 v3.7 vs v3.8 对比回测
// v3.8 新增：防追高被套机制（BIAS20 + 短期涨幅 + 连涨天数）
// 标的：沪深300指数 (000300)
// ============================================================
'use strict';

const fs = require('fs');
const path = require('path');

// ════════════════════════════════════════════════════════════
// 一、技术指标计算
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
  for (let i = slow - 1; i < prices.length; i++) {
    dif[i] = emaFast[i] - emaSlow[i];
  }
  const sig = new Array(prices.length).fill(null);
  let first = null;
  for (let i = slow - 1; i < prices.length; i++) {
    if (first === null) { first = dif[i]; sig[i] = dif[i]; }
    else { sig[i] = dif[i] * (2 / (signal + 1)) + sig[i - 1] * (1 - 2 / (signal + 1)); }
  }
  const hist = new Array(prices.length).fill(null);
  for (let i = slow - 1; i < prices.length; i++) {
    hist[i] = dif[i] - sig[i];
  }
  return { dif, sig, hist };
}

// ════════════════════════════════════════════════════════════
// 二、五星评分系统 (v3.7, 13分制)
// ════════════════════════════════════════════════════════════

function calcStarScore(data, idx, benchmarkData = null) {
  const prices = data.map(d => d.close);
  const vols = data.map(d => d.vol);
  const ma20 = SMA(prices, 20);
  const ma50 = SMA(prices, 50);
  const ma200 = SMA(prices, 200);
  const macd = MACD(prices);
  
  let score = 0;
  const details = [];
  
  if (idx < 200) return { score: 0, stars: 0, details: ['数据不足'] };
  if (ma20[idx] === null || macd.dif[idx] === null) return { score: 0, stars: 0, details: ['指标无效'] };
  
  const price = prices[idx];
  const prevPrice = prices[idx - 1];
  
  // 趋势 (0-5)
  if (price > ma20[idx]) { score += 1; details.push('站上MA20(+1)'); }
  if (ma50[idx] !== null && ma20[idx] > ma50[idx]) { score += 1; details.push('MA20>MA50(+1)'); }
  if (ma200[idx] !== null && ma20[idx] > ma50[idx] && ma50[idx] > ma200[idx]) { score += 2; details.push('多头排列(+2)'); }
  if (ma20[idx] > ma20[idx - 1]) { score += 1; details.push('MA20向上(+1)'); }
  
  // 动量 (0-4)
  const d = macd.dif[idx], dPrev = macd.dif[idx - 1];
  const s = macd.sig[idx], sPrev = macd.sig[idx - 1];
  const h = macd.hist[idx], hPrev = macd.hist[idx - 1];
  const goldX = dPrev <= sPrev && d > s && d > 0 && s > 0;
  if (goldX) { score += 3; details.push('零轴上金叉(+3)'); }
  else if (dPrev <= sPrev && d > s) { score += 1; details.push('零轴下金叉(+1)'); }
  if (h > 0 && hPrev > 0) { score += 1; details.push('红柱持续(+1)'); }
  
  // 相对强弱 (0-3)
  const pct20 = (price - prices[idx - 20]) / prices[idx - 20] * 100;
  const pct5 = (price - prices[idx - 5]) / prices[idx - 5] * 100;
  let bench20 = 0;
  if (benchmarkData && benchmarkData.length > idx) {
    const bp = benchmarkData[idx].close;
    const bp20 = benchmarkData[idx - 20]?.close || benchmarkData[0].close;
    bench20 = (bp - bp20) / bp20 * 100;
  }
  if (pct20 > bench20 && bench20 > 0) { score += 2; details.push(`跑赢基准(+2)`); }
  else if (pct20 > 0) { score += 1; details.push(`绝对正动量(+1)`); }
  if (pct5 > 0) { score += 1; details.push('5日正动量(+1)'); }
  
  // 成交量 (0-1)
  const volMA20 = vols.slice(idx - 19, idx + 1).reduce((a, b) => a + b, 0) / 20;
  if (vols[idx] > volMA20 * 1.5) { score += 1; details.push('放量1.5倍(+1)'); }
  
  let stars = 0;
  if (score >= 10) stars = 5;
  else if (score >= 8) stars = 4;
  else if (score >= 6) stars = 3;
  else if (score >= 4) stars = 2;
  else if (score >= 1) stars = 1;
  
  return { score, stars, details, pct20, pct5, bench20, goldX, aboveMA20: price > ma20[idx], ma20Up: ma20[idx] > ma20[idx - 1] };
}

// ════════════════════════════════════════════════════════════
// 三、v3.8 防追高检测
// ════════════════════════════════════════════════════════════

function checkChaseRisk(data, idx) {
  const prices = data.map(d => d.close);
  const ma20 = SMA(prices, 20);
  
  if (idx < 20 || ma20[idx] === null) return { redLine: false, deduction: 0, reasons: [], details: [] };
  
  const price = prices[idx];
  
  // BIAS20
  const bias20 = (price - ma20[idx]) / ma20[idx] * 100;
  
  // 3日涨幅
  const pct3d = (price - prices[idx - 3]) / prices[idx - 3] * 100;
  
  // 5日涨幅
  const pct5d = (price - prices[idx - 5]) / prices[idx - 5] * 100;
  
  // 连涨天数
  let conUp = 0;
  for (let i = idx; i > 0; i--) {
    if (prices[i] > prices[i - 1]) conUp++;
    else break;
  }
  
  const reasons = [];
  const details = [];
  let deduction = 0;
  let yellowCount = 0;
  let redLine = false;
  
  // 🟡 黄线
  if (bias20 > 5 && bias20 <= 8) { deduction += 1; yellowCount++; details.push(`BIAS20=${bias20.toFixed(1)}%(黄线-1)`); }
  if (pct3d > 5 && pct3d <= 10) { deduction += 1; yellowCount++; details.push(`3日涨${pct3d.toFixed(1)}%(黄线-1)`); }
  if (pct5d > 10 && pct5d <= 15) { deduction += 1; yellowCount++; details.push(`5日涨${pct5d.toFixed(1)}%(黄线-1)`); }
  if (conUp >= 5 && conUp <= 7) { deduction += 1; yellowCount++; details.push(`连涨${conUp}天(黄线-1)`); }
  
  // 🔴 红线
  if (bias20 > 8) { redLine = true; reasons.push(`BIAS20=${bias20.toFixed(1)}%>8%`); }
  if (pct3d > 10) { redLine = true; reasons.push(`3日涨${pct3d.toFixed(1)}%>10%`); }
  if (pct5d > 15) { redLine = true; reasons.push(`5日涨${pct5d.toFixed(1)}%>15%`); }
  if (conUp >= 8) { redLine = true; reasons.push(`连涨${conUp}天>=8`); }
  if (yellowCount >= 3) { redLine = true; reasons.push(`黄线叠加${yellowCount}个>=3`); }
  
  return { redLine, deduction, reasons, details, bias20, pct3d, pct5d, conUp, yellowCount };
}

// ════════════════════════════════════════════════════════════
// 四、回测引擎（通用，传入买入过滤函数）
// ════════════════════════════════════════════════════════════

function runBacktest(data, benchmarkData, initialCapital, buyFilter) {
  const trades = [];
  const equity = [];
  let capital = initialCapital;
  let position = 0;
  let avgCost = 0;
  let peak = initialCapital;
  let maxDD = 0;
  let chaseBlocked = 0;  // 被追高过滤阻止的次数
  let watchlistHits = 0; // 观察池回踩成功买入次数
  
  const ma20Arr = SMA(data.map(d => d.close), 20);
  
  for (let i = 200; i < data.length; i++) {
    const price = data[i].close;
    const scoreInfo = calcStarScore(data, i, benchmarkData);
    
    if (position === 0) {
      const canBuy = scoreInfo.stars >= 4 && 
                     scoreInfo.goldX && 
                     scoreInfo.aboveMA20 && 
                     scoreInfo.ma20Up;
      
      if (canBuy) {
        const filterResult = buyFilter(data, i, scoreInfo);
        if (filterResult.allowed) {
          const shares = Math.floor(capital / price / 100) * 100;
          if (shares > 0) {
            position = shares;
            avgCost = price;
            capital -= shares * price;
            trades.push({
              type: 'BUY', date: data[i].date, price, shares,
              value: shares * price, score: scoreInfo.score, stars: scoreInfo.stars,
              reason: filterResult.label || `${'⭐'.repeat(scoreInfo.stars)} ${scoreInfo.details.slice(0,3).join(',')}`
            });
          }
        } else {
          chaseBlocked++;
        }
      }
    }
    else if (position > 0) {
      const belowMA20 = price < ma20Arr[i];
      const loss5pct = (price - avgCost) / avgCost <= -0.05;
      let reason = null;
      if (loss5pct) reason = '硬性止损-5%';
      else if (belowMA20) reason = '跌破MA20';
      
      if (reason) {
        capital += position * price;
        const pnl = ((price - avgCost) / avgCost * 100);
        trades.push({
          type: 'SELL', date: data[i].date, price, shares: position,
          value: position * price, pnl: pnl.toFixed(2) + '%', reason
        });
        position = 0;
        avgCost = 0;
      }
    }
    
    const totalValue = capital + position * price;
    equity.push({ date: data[i].date, value: totalValue, price, score: scoreInfo.score, stars: scoreInfo.stars });
    if (totalValue > peak) peak = totalValue;
    const dd = (peak - totalValue) / peak * 100;
    if (dd > maxDD) maxDD = dd;
  }
  
  // 强制平仓
  if (position > 0) {
    const lastPrice = data[data.length - 1].close;
    capital += position * lastPrice;
    const pnl = ((lastPrice - avgCost) / avgCost * 100);
    trades.push({
      type: 'SELL', date: data[data.length - 1].date, price: lastPrice,
      shares: position, value: position * lastPrice, pnl: pnl.toFixed(2) + '%', reason: '回测结束平仓'
    });
  }
  
  return { trades, equity, finalValue: capital, maxDD, peak, chaseBlocked, watchlistHits };
}

// ════════════════════════════════════════════════════════════
// 五、统计
// ════════════════════════════════════════════════════════════

function calcStats(equity, initialCapital, maxDD) {
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
  const winRate = rets.filter(r => r > 0).length / rets.length;
  
  return { finalV, totalRet, cagr, sharpe, winRate, maxDD, years };
}

function tradeStats(trades) {
  const sells = trades.filter(t => t.type === 'SELL' && !t.reason.includes('平仓'));
  const buys = trades.filter(t => t.type === 'BUY');
  if (sells.length === 0) return { count: buys.length, wins: 0, losses: 0, winRate: 0, avgWin: 0, avgLoss: 0, profitFactor: 0 };
  
  const pnls = sells.map(t => parseFloat(t.pnl));
  const wins = pnls.filter(p => p > 0);
  const loses = pnls.filter(p => p <= 0);
  const winRate = wins.length / sells.length;
  const avgWin = wins.length > 0 ? wins.reduce((a, b) => a + b, 0) / wins.length : 0;
  const avgLoss = loses.length > 0 ? loses.reduce((a, b) => a + b, 0) / loses.length : 0;
  const profitFactor = avgLoss !== 0 ? (avgWin * winRate) / (Math.abs(avgLoss) * (1 - winRate)) : 0;
  
  return { count: buys.length, wins: wins.length, losses: loses.length, winRate, avgWin, avgLoss, profitFactor };
}

// ════════════════════════════════════════════════════════════
// 六、主程序
// ════════════════════════════════════════════════════════════

async function main() {
  console.log('\n' + '='.repeat(76));
  console.log('   MA20+MACD策略 v3.7 vs v3.8 对比回测');
  console.log('   v3.8新增: 防追高被套机制 (BIAS20 + 短期涨幅 + 连涨天数)');
  console.log('   标的: 沪深300 (000300)');
  console.log('='.repeat(76) + '\n');
  
  // 读取数据
  const histFile = path.join(__dirname, '..', '..', 'data', 'history', 'sh000300.json');
  let data;
  try {
    data = JSON.parse(fs.readFileSync(histFile, 'utf8'));
    data = data.map(d => ({ date: d.date, open: d.open, close: d.close, high: d.high, low: d.low, vol: d.volume || 0 }));
  } catch (e) {
    console.error('❌ 读取历史数据失败:', e.message);
    process.exit(1);
  }
  if (data.length < 1000) { console.error('❌ 数据不足'); process.exit(1); }
  console.log(`📥 读取 ${data.length} 条数据 (${data[0].date} ~ ${data[data.length - 1].date})\n`);
  
  const ICAP = 1000000;
  
  // ── v3.7 买入过滤（无追高过滤）──
  const v37Filter = (data, idx, scoreInfo) => ({ allowed: true, label: `v3.7 ${'⭐'.repeat(scoreInfo.stars)}` });
  
  // ── v3.8 买入过滤（含追高过滤）──
  const v38Filter = (data, idx, scoreInfo) => {
    const chase = checkChaseRisk(data, idx);
    if (chase.redLine) {
      return { allowed: false, label: `🔴红线 ${chase.reasons.join('; ')}` };
    }
    const adjustedScore = scoreInfo.score - chase.deduction;
    let adjustedStars = scoreInfo.stars;
    if (adjustedScore >= 10) adjustedStars = 5;
    else if (adjustedScore >= 8) adjustedStars = 4;
    else if (adjustedScore >= 6) adjustedStars = 3;
    else if (adjustedScore >= 4) adjustedStars = 2;
    else adjustedStars = 1;
    
    // 扣分后仍需>=4星才买
    if (adjustedStars < 4) {
      return { allowed: false, label: `🟡扣分后${adjustedStars}星(原${scoreInfo.stars}星-${chase.deduction}分)` };
    }
    
    const label = chase.deduction > 0 
      ? `v3.8 ${'⭐'.repeat(adjustedStars)}(原${scoreInfo.stars}星-${chase.deduction}分 ${chase.details.join(',')})`
      : `v3.8 ${'⭐'.repeat(adjustedStars)}`;
    return { allowed: true, label };
  };
  
  // 运行回测
  console.log('🔄 运行 v3.7 回测...');
  const r37 = runBacktest(data, data, ICAP, v37Filter);
  const s37 = calcStats(r37.equity, ICAP, r37.maxDD);
  const t37 = tradeStats(r37.trades);
  
  console.log('🔄 运行 v3.8 回测...');
  const r38 = runBacktest(data, data, ICAP, v38Filter);
  const s38 = calcStats(r38.equity, ICAP, r38.maxDD);
  const t38 = tradeStats(r38.trades);
  
  // 买入持有基准
  const bhShares = Math.floor(ICAP / data[200].close);
  const bhCost = bhShares * data[200].close;
  const bhFinal = bhShares * data[data.length - 1].close;
  const bhCAGR = Math.pow(bhFinal / bhCost, 1 / s37.years) - 1;
  
  // ════════════════════════════════════════════════════════════
  // 输出结果
  // ════════════════════════════════════════════════════════════
  
  console.log('\n' + '='.repeat(76));
  console.log('   📊 回测结果对比：v3.7 vs v3.8 vs 买入持有');
  console.log('='.repeat(76));
  console.log(`   回测区间: ${data[200].date} → ${data[data.length - 1].date} (${s37.years.toFixed(1)}年)`);
  console.log(`   初始资金: ¥${ICAP.toLocaleString()}\n`);
  
  const pad = (s, n) => String(s).padEnd(n);
  const padL = (s, n) => String(s).padStart(n);
  
  console.log('   ┌────────────────────────┬──────────────┬──────────────┬──────────────┐');
  console.log('   │ 指标                   │    v3.7      │    v3.8      │   买入持有   │');
  console.log('   ├────────────────────────┼──────────────┼──────────────┼──────────────┤');
  
  const rows = [
    ['期末资金', `¥${Math.round(s37.finalV).toLocaleString()}`, `¥${Math.round(s38.finalV).toLocaleString()}`, `¥${Math.round(bhFinal).toLocaleString()}`],
    ['总收益率', `${(s37.totalRet * 100).toFixed(2)}%`, `${(s38.totalRet * 100).toFixed(2)}%`, `${((bhFinal / bhCost - 1) * 100).toFixed(2)}%`],
    ['年化收益率(CAGR)', `${(s37.cagr * 100).toFixed(2)}%`, `${(s38.cagr * 100).toFixed(2)}%`, `${(bhCAGR * 100).toFixed(2)}%`],
    ['最大回撤', `${s37.maxDD.toFixed(2)}%`, `${s38.maxDD.toFixed(2)}%`, '—'],
    ['夏普比率', `${s37.sharpe.toFixed(2)}`, `${s38.sharpe.toFixed(2)}`, '—'],
    ['交易次数', `${t37.count}买/${t37.count > 0 ? t37.count : 0}卖`, `${t38.count}买/${t38.count > 0 ? t38.count : 0}卖`, '1'],
    ['胜率', t37.winRate > 0 ? `${(t37.winRate * 100).toFixed(1)}%` : '—', t38.winRate > 0 ? `${(t38.winRate * 100).toFixed(1)}%` : '—', '—'],
    ['平均盈利', t37.avgWin > 0 ? `+${t37.avgWin.toFixed(2)}%` : '—', t38.avgWin > 0 ? `+${t38.avgWin.toFixed(2)}%` : '—', '—'],
    ['平均亏损', t37.avgLoss !== 0 ? `${t37.avgLoss.toFixed(2)}%` : '—', t38.avgLoss !== 0 ? `${t38.avgLoss.toFixed(2)}%` : '—', '—'],
    ['盈亏比', t37.profitFactor > 0 ? t37.profitFactor.toFixed(2) : '—', t38.profitFactor > 0 ? t38.profitFactor.toFixed(2) : '—', '—'],
  ];
  
  for (const [k, v1, v2, v3] of rows) {
    console.log(`   │ ${pad(k, 22)} │ ${pad(v1, 12)} │ ${pad(v2, 12)} │ ${pad(v3, 12)} │`);
  }
  console.log('   └────────────────────────┴──────────────┴──────────────┴──────────────┘');
  
  // v3.8 特有统计
  console.log('\n' + '-'.repeat(76));
  console.log('   🛡️ v3.8 防追高机制统计');
  console.log('-'.repeat(76));
  console.log(`   被追高过滤阻止的买入: ${r38.chaseBlocked} 次`);
  console.log(`   v3.7交易次数: ${t37.count}, v3.8交易次数: ${t38.count}, 减少: ${t37.count - t38.count} 次`);
  
  const cagrDiff = ((s38.cagr - s37.cagr) * 100).toFixed(2);
  const ddDiff = (s38.maxDD - s37.maxDD).toFixed(2);
  console.log(`   CAGR变化: ${cagrDiff > 0 ? '+' : ''}${cagrDiff}%`);
  console.log(`   最大回撤变化: ${ddDiff > 0 ? '+' : ''}${ddDiff}% (负为改善)`);
  
  // 详细交易对比
  console.log('\n' + '-'.repeat(76));
  console.log('   📋 v3.8 交易明细（含追高过滤信息）');
  console.log('-'.repeat(76));
  r38.trades.slice(-20).forEach(t => {
    if (t.type === 'BUY') {
      console.log(`   🟢 ${t.date} 买入 ¥${t.price.toFixed(2)} ${t.reason.substring(0, 70)}`);
    } else {
      console.log(`   🔴 ${t.date} 卖出 ¥${t.price.toFixed(2)} ${t.pnl} [${t.reason}]`);
    }
  });
  
  // 分析被过滤掉的具体交易
  console.log('\n' + '-'.repeat(76));
  console.log('   🔍 v3.7有但v3.8被过滤的交易分析');
  console.log('-'.repeat(76));
  
  // 找出v3.7买入但v3.8没买入的时间点
  const v37BuyDates = new Set(r37.trades.filter(t => t.type === 'BUY').map(t => t.date));
  const v38BuyDates = new Set(r38.trades.filter(t => t.type === 'BUY').map(t => t.date));
  const filteredDates = [...v37BuyDates].filter(d => !v38BuyDates.has(d));
  
  if (filteredDates.length > 0) {
    console.log(`   共 ${filteredDates.length} 笔被追高过滤阻止：`);
    filteredDates.slice(0, 10).forEach(date => {
      const idx = data.findIndex(d => d.date === date);
      if (idx >= 200) {
        const chase = checkChaseRisk(data, idx);
        const score = calcStarScore(data, idx, data);
        console.log(`   🚫 ${date} ⭐${score.stars} BIAS=${chase.bias20?.toFixed(1) || '?'}% 3日=${chase.pct3d?.toFixed(1) || '?'}% 5日=${chase.pct5d?.toFixed(1) || '?'}% 连涨=${chase.conUp}天 [${chase.reasons.join('; ')}]`);
      }
    });
    if (filteredDates.length > 10) console.log(`   ... 还有 ${filteredDates.length - 10} 笔`);
  } else {
    console.log('   无交易被过滤（v3.7和v3.8买入点完全一致）');
  }
  
  // 保存结果
  const outDir = path.join(__dirname, '..', '..', 'reviews', 'backtest');
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  
  const outFile = path.join(outDir, `v38_compare_${new Date().toISOString().slice(0, 10)}.json`);
  fs.writeFileSync(outFile, JSON.stringify({
    v37: { stats: s37, trades: r37.trades, tradeStats: t37 },
    v38: { stats: s38, trades: r38.trades, tradeStats: t38, chaseBlocked: r38.chaseBlocked },
    buyHold: { cagr: bhCAGR, totalReturn: (bhFinal / bhCost - 1) },
    filteredBuyDates: filteredDates
  }, null, 2));
  console.log(`\n📁 结果已保存: ${outFile}`);
  
  console.log('\n' + '='.repeat(76));
  console.log('   ⚠️  风险提示：回测不代表未来收益，防追高机制在极端趋势中可能错过持续上涨');
  console.log('='.repeat(76) + '\n');
}

main().catch(console.error);
