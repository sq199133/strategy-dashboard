// ============================================================
// MA20+MACD策略 v3.7 回测脚本
// 标的：沪深300指数 (000300) 作为策略有效性验证
// 规则：五星评分(13分) + 分市场相对强弱 + 仅MA20跌破卖出
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
// 二、数据获取
// ════════════════════════════════════════════════════════════

// 腾讯K线API (前复权)
async function fetchKlineTencent(code, days = 5000) {
  const prefix = code.startsWith('6') || code.startsWith('5') || code.startsWith('11') ? 'sh' : 'sz';
  const fullCode = prefix + code;
  const url = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${fullCode},day,,,${days},qfq`;
  
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(30000) });
    const j = await r.json();
    const data = j.data?.[fullCode];
    const klines = data?.qfqday || data?.day || [];
    
    return klines.map(k => ({
      date: k[0],
      open: +k[1],
      close: +k[2],
      low: +k[3],
      high: +k[4],
      vol: +k[5] || 0
    }));
  } catch (e) {
    console.error(`获取 ${code} 失败:`, e.message);
    return [];
  }
}

async function fetchKline(code, start, end) {
  return fetchKlineTencent(code, 5000);
}

// ════════════════════════════════════════════════════════════
// 三、五星评分系统 (v3.7, 13分制)
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
  
  // 数据有效性检查
  if (idx < 200) return { score: 0, stars: 0, details: ['数据不足'] };
  if (ma20[idx] === null || macd.dif[idx] === null) return { score: 0, stars: 0, details: ['指标无效'] };
  
  const price = prices[idx];
  const prevPrice = prices[idx - 1];
  const prev2Price = prices[idx - 2];
  
  // ── 趋势维度 (0-5分) ──
  // 1. 站上MA20
  if (price > ma20[idx]) { score += 1; details.push('站上MA20(+1)'); }
  
  // 2. MA20 > MA50
  if (ma50[idx] !== null && ma20[idx] > ma50[idx]) { score += 1; details.push('MA20>MA50(+1)'); }
  
  // 3. 多头排列 MA20>MA50>MA200
  if (ma200[idx] !== null && ma20[idx] > ma50[idx] && ma50[idx] > ma200[idx]) { 
    score += 2; details.push('多头排列(+2)'); 
  }
  
  // 4. MA20方向向上
  if (ma20[idx] > ma20[idx - 1]) { score += 1; details.push('MA20向上(+1)'); }
  
  // ── 动量维度 (0-4分) ──
  const d = macd.dif[idx];
  const dPrev = macd.dif[idx - 1];
  const s = macd.sig[idx];
  const sPrev = macd.sig[idx - 1];
  const h = macd.hist[idx];
  const hPrev = macd.hist[idx - 1];
  
  // MACD零轴上金叉 (v3.7: +3分，已修复重复计数)
  const goldX = dPrev <= sPrev && d > s && d > 0 && s > 0;
  if (goldX) { score += 3; details.push('零轴上金叉(+3)'); }
  else if (dPrev <= sPrev && d > s) { score += 1; details.push('零轴下金叉(+1)'); }
  
  // 红柱持续
  if (h > 0 && hPrev > 0) { score += 1; details.push('红柱持续(+1)'); }
  
  // ── 相对强弱 (0-3分) ──
  // 计算20日涨幅
  const pct20 = (price - prices[idx - 20]) / prices[idx - 20] * 100;
  const pct5 = (price - prices[idx - 5]) / prices[idx - 5] * 100;
  
  // A股ETF: 20日涨幅 > 沪深300涨幅 AND 沪深300涨幅 > 0
  let bench20 = 0;
  if (benchmarkData && benchmarkData.length > idx) {
    const benchPrice = benchmarkData[idx].close;
    const benchPrice20 = benchmarkData[idx - 20]?.close || benchmarkData[0].close;
    bench20 = (benchPrice - benchPrice20) / benchPrice20 * 100;
  }
  
  // v3.7: 相对沪深300，且沪深300本身需处于多头
  if (pct20 > bench20 && bench20 > 0) { score += 2; details.push(`跑赢基准(+2, ${pct20.toFixed(1)}% vs ${bench20.toFixed(1)}%)`); }
  else if (pct20 > 0) { score += 1; details.push(`绝对正动量(+1, ${pct20.toFixed(1)}%)`); }
  
  // 5日短期强势
  if (pct5 > 0) { score += 1; details.push(`5日正动量(+1)`); }
  
  // ── 成交量 (0-1分) ──
  const volMA20 = vols.slice(idx - 19, idx + 1).reduce((a, b) => a + b, 0) / 20;
  if (vols[idx] > volMA20 * 1.5) { score += 1; details.push('放量1.5倍(+1)'); }
  
  // 星级映射 (v3.7: 五星门槛10分)
  let stars = 0;
  if (score >= 10) stars = 5;
  else if (score >= 8) stars = 4;
  else if (score >= 6) stars = 3;
  else if (score >= 4) stars = 2;
  else if (score >= 1) stars = 1;
  
  return { score, stars, details, pct20, pct5, bench20, goldX, aboveMA20: price > ma20[idx], ma20Up: ma20[idx] > ma20[idx - 1] };
}

// ════════════════════════════════════════════════════════════
// 四、回测引擎 (v3.7规则)
// ════════════════════════════════════════════════════════════

function runBacktest(data, benchmarkData, initialCapital = 1000000) {
  const trades = [];
  const equity = [];
  let capital = initialCapital;
  let position = 0;
  let avgCost = 0;
  let peak = initialCapital;
  let maxDD = 0;
  
  // 从第200根K线开始（确保MA200有效）
  for (let i = 200; i < data.length; i++) {
    const price = data[i].close;
    const ma20 = SMA(data.map(d => d.close), 20);
    
    // 计算当前评分
    const scoreInfo = calcStarScore(data, i, benchmarkData);
    
    // ── 买入信号 (v3.7: 必须零轴上金叉 + 站上MA20 + MA20向上 + 相对强弱) ──
    if (position === 0) {
      // 买入条件：⭐⭐⭐⭐⭐ 或 ⭐⭐⭐⭐ 且满足硬性条件
      const canBuy = scoreInfo.stars >= 4 && 
                     scoreInfo.goldX &&  // 必须零轴上金叉
                     scoreInfo.aboveMA20 && 
                     scoreInfo.ma20Up;
      
      if (canBuy) {
        const shares = Math.floor(capital / price / 100) * 100; // 100股整数
        if (shares > 0) {
          position = shares;
          avgCost = price;
          capital -= shares * price;
          trades.push({
            type: 'BUY', date: data[i].date, price, shares,
            value: shares * price, score: scoreInfo.score, stars: scoreInfo.stars,
            reason: `⭐${'⭐'.repeat(scoreInfo.stars - 1)} ${scoreInfo.details.join(', ')}`
          });
        }
      }
    }
    
    // ── 卖出信号 (v3.7: 仅MA20跌破 或 亏损>5%) ──
    else if (position > 0) {
      const belowMA20 = price < ma20[i];
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
    
    // 记录净值
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
  
  return { trades, equity, finalValue: capital, maxDD, peak };
}

// ════════════════════════════════════════════════════════════
// 五、统计与报告
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

// ════════════════════════════════════════════════════════════
// 六、主程序
// ════════════════════════════════════════════════════════════

async function main() {
  console.log('\n' + '='.repeat(70));
  console.log('   MA20+MACD策略 v3.7 回测');
  console.log('   标的: 沪深300 (000300)');
  console.log('   规则: 五星评分(13分) + 零轴上金叉 + 仅MA20跌破卖出');
  console.log('='.repeat(70) + '\n');
  
  // 读取本地历史数据
  console.log('📥 读取沪深300历史数据...');
  const fs = require('fs');
  const path = require('path');
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
  console.log(`✅ 读取 ${data.length} 条数据 (${data[0].date} ~ ${data[data.length - 1].date})\n`);
  
  // 回测
  const ICAP = 1000000;
  console.log('🔄 运行 v3.7 策略回测...\n');
  const result = runBacktest(data, data, ICAP);
  const stats = calcStats(result.equity, ICAP, result.maxDD);
  
  // 买入持有基准
  const bhShares = Math.floor(ICAP / data[200].close);
  const bhCost = bhShares * data[200].close;
  const bhFinal = bhShares * data[data.length - 1].close;
  const bhCAGR = Math.pow(bhFinal / bhCost, 1 / stats.years) - 1;
  
  // 输出结果
  console.log('='.repeat(70));
  console.log('   回测结果对比 (v3.7 vs 买入持有)');
  console.log('='.repeat(70));
  console.log(`   回测区间:  ${data[200].date} → ${data[data.length - 1].date} (${stats.years.toFixed(1)}年)`);
  console.log(`   初始资金:  ¥${ICAP.toLocaleString()}\n`);
  
  const rows = [
    ['期末资金', `¥${stats.finalV.toFixed(0)}`, `¥${bhFinal.toFixed(0)}`],
    ['总收益率', `${(stats.totalRet * 100).toFixed(2)}%`, `${((bhFinal / bhCost - 1) * 100).toFixed(2)}%`],
    ['年化收益率(CAGR)', `${(stats.cagr * 100).toFixed(2)}%`, `${(bhCAGR * 100).toFixed(2)}%`],
    ['最大回撤', `${stats.maxDD.toFixed(2)}%`, '—'],
    ['夏普比率', `${stats.sharpe.toFixed(2)}`, '—'],
    ['日胜率', `${(stats.winRate * 100).toFixed(1)}%`, '—'],
  ];
  
  console.log('   ┌────────────────────┬──────────────────┬──────────────────┐');
  console.log('   │ 指标               │   v3.7策略       │     买入持有     │');
  console.log('   ├────────────────────┼──────────────────┼──────────────────┤');
  for (const [k, v1, v2] of rows) {
    console.log(`   │ ${k.padEnd(18)} │ ${v1.padEnd(16)} │ ${v2.padEnd(16)} │`);
  }
  console.log('   └────────────────────┴──────────────────┴──────────────────┘');
  
  const diff = stats.finalV - bhFinal;
  console.log(`\n   💡 策略累计 ${diff >= 0 ? '跑赢' : '跑输'} 买入持有 ¥${Math.abs(diff).toFixed(0)} (${(diff / bhFinal * 100).toFixed(2)}%)`);
  
  // 交易统计
  console.log('\n' + '-'.repeat(70));
  console.log('   交易统计');
  console.log('-'.repeat(70));
  const buys = result.trades.filter(t => t.type === 'BUY');
  const sells = result.trades.filter(t => t.type === 'SELL' && !t.reason.includes('平仓'));
  console.log(`   总交易次数: ${buys.length} 次买入 / ${sells.length} 次卖出`);
  
  if (sells.length > 0) {
    const pnls = sells.map(t => parseFloat(t.pnl));
    const wins = pnls.filter(p => p > 0);
    const loses = pnls.filter(p => p <= 0);
    const winRate = wins.length / sells.length;
    const avgWin = wins.length > 0 ? wins.reduce((a, b) => a + b, 0) / wins.length : 0;
    const avgLoss = loses.length > 0 ? loses.reduce((a, b) => a + b, 0) / loses.length : 0;
    const profitFactor = avgWin * winRate / (Math.abs(avgLoss) * (1 - winRate));
    
    console.log(`   盈利次数:   ${wins.length} (${(wins.length / sells.length * 100).toFixed(1)}%)`);
    console.log(`   亏损次数:   ${loses.length} (${(loses.length / sells.length * 100).toFixed(1)}%)`);
    console.log(`   平均盈利:   +${avgWin.toFixed(2)}%`);
    console.log(`   平均亏损:   ${avgLoss.toFixed(2)}%`);
    console.log(`   盈亏比:     ${(avgWin / Math.abs(avgLoss)).toFixed(2)}`);
    console.log(`   胜率×盈亏比: ${(winRate * (avgWin / Math.abs(avgLoss))).toFixed(2)}`);
  }
  
  // 最近交易
  console.log('\n' + '-'.repeat(70));
  console.log('   最近10笔交易');
  console.log('-'.repeat(70));
  result.trades.slice(-10).forEach(t => {
    if (t.type === 'BUY') {
      console.log(`   🟢 ${t.date} 买入 ${t.shares.toLocaleString()}股 @ ¥${t.price.toFixed(2)} [${t.reason.substring(0, 50)}...]`);
    } else {
      console.log(`   🔴 ${t.date} 卖出 ${t.shares.toLocaleString()}股 @ ¥${t.price.toFixed(2)} ${t.pnl} [${t.reason}]`);
    }
  });
  
  // 保存结果
  const outDir = path.join(__dirname, '..', '..', 'reviews', 'backtest');
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  
  const outFile = path.join(outDir, `v37_backtest_${new Date().toISOString().slice(0, 10)}.json`);
  fs.writeFileSync(outFile, JSON.stringify({ stats, trades: result.trades, equity: result.equity.slice(-100) }, null, 2));
  console.log(`\n📁 结果已保存: ${outFile}`);
  
  console.log('\n' + '='.repeat(70));
  console.log('   ⚠️  风险提示：回测不代表未来收益');
  console.log('='.repeat(70) + '\n');
}

main().catch(console.error);
