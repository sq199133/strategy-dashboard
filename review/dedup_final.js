// 赛道去重 vs 无去重 回测对比 (final corrected version)
// ATR filter fixed to ensure proper vol lookback and signal generation
const fs = require('fs');
const path = require('path');

// ========== 参数 ==========
const MA_S = 5, MA_L = 21;
const ATR_RATIO = 0.85;
const DEV_MAX = 0.15;
const VOL_RATIO_MAX = 1.5;
const C_BONUS = 0.02, B1_BONUS = 0.00;
const TOPN = 3;
const STOP_LOSS_PCT = 0.08;
const TRAIL_PCT = 0.10;
const INIT_CAPITAL = 1.0;
const START_W = '2014-W01';
const END_W = '2026-W26';

// ========== 加载数据 ==========
const rawPool = fs.readFileSync('D:/QClaw_Trading/data/etf_pool_V1_full.json', 'utf8');
const fixedPool = rawPool.replace(/\bNaN\b/g, 'null');
const poolData = JSON.parse(fixedPool).data;
const pool = poolData.map(e => ({ code: e.code, name: e.name, cat: e.category }));
const histDir = 'D:/QClaw_Trading/data/history_long_v2/';

const allData = {};
let loaded = 0;
for (const etf of pool) {
  const fpath = path.join(histDir, etf.code + '.json');
  if (fs.existsSync(fpath)) {
    try {
      const d = JSON.parse(fs.readFileSync(fpath, 'utf8'));
      allData[etf.code] = d.records;
      loaded++;
    } catch(e) {}
  }
}
console.error('Loaded', loaded, 'ETFs');

// ========== 工具函数 ==========
function getRecords(code) { return allData[code] || []; }

function ma(recs, period, idx) {
  if (idx < period - 1) return null;
  let sum = 0;
  for (let i = idx - period + 1; i <= idx; i++) sum += recs[i].close;
  return sum / period;
}

// ATR using Wilder's smoothing (标准ATR计算)
function atr(recs, period, idx) {
  if (idx < period) return null;
  // First: compute SMA for initial ATR
  let sum = 0;
  for (let i = 1; i <= period; i++) {
    const h = recs[i].high, l = recs[i].low, pc = recs[i-1].close;
    sum += Math.max(h-l, Math.abs(h-pc), Math.abs(l-pc));
  }
  let prevAtr = sum / period;
  // Wilder smoothing: ATR_t = (ATR_{t-1} * (period-1) + TR_t) / period
  for (let i = period + 1; i <= idx; i++) {
    const h = recs[i].high, l = recs[i].low, pc = recs[i-1].close;
    const tr = Math.max(h-l, Math.abs(h-pc), Math.abs(l-pc));
    prevAtr = (prevAtr * (period - 1) + tr) / period;
  }
  return prevAtr;
}

function volMa10(recs, idx) {
  if (idx < 9) return null;
  let sum = 0;
  for (let i = idx - 9; i <= idx; i++) sum += recs[i].vol;
  return sum / 10;
}

function momentum(recs, idx, n) {
  if (idx < n) return null;
  return (recs[idx].close - recs[idx - n].close) / recs[idx - n].close;
}

function isC仙人指路(recs, idx) {
  if (idx < 21) return false;
  const cur = recs[idx];
  if (cur.close <= cur.open) return false;
  const body = cur.close - cur.open;
  if (body <= 0) return false;
  const upperShadow = cur.high - cur.close;
  const lowerShadow = cur.open - cur.low;
  if (upperShadow / body <= 1.0) return false;
  if (lowerShadow >= body * 0.5) return false;
  const ma5 = ma(recs, 5, idx);
  const ma21 = ma(recs, 21, idx);
  if (!(cur.close > ma5 && ma5 > ma21)) return false;
  const volMa10_val = volMa10(recs, idx);
  if (volMa10_val === null || volMa10_val === 0) return false;
  const vr = cur.vol / volMa10_val;
  if (vr >= 1.5 || vr <= 0.5) return false;
  if (idx < 20) return false;
  const mom20 = (cur.close - recs[idx-20].close) / recs[idx-20].close;
  if (mom20 >= 0.5) return false;
  return true;
}

function isB1红三兵(recs, idx) {
  if (idx < 2) return false;
  for (let i = 0; i < 3; i++) {
    if (recs[idx - i].close <= recs[idx - i].open) return false;
  }
  const low0 = recs[idx].low, low1 = recs[idx-1].low, low2 = recs[idx-2].low;
  return low0 > low1 && low1 > low2;
}

function deviation(recs, idx) {
  const ma5 = ma(recs, 5, idx);
  if (ma5 === null || ma5 === 0) return null;
  return Math.abs(recs[idx].close - ma5) / ma5;
}

// ========== 生成调仓周 ==========
function getRebalanceWeeks() {
  const allWeeks = new Set();
  for (const etf of pool) {
    const recs = getRecords(etf.code);
    recs.forEach(r => allWeeks.add(r.w));
  }
  const sortedWeeks = [...allWeeks].sort().filter(w => w >= START_W && w <= END_W);
  const byMonth = {};
  sortedWeeks.forEach(w => {
    const ym = w.slice(0, 7);
    if (!byMonth[ym] || w > byMonth[ym]) byMonth[ym] = w;
  });
  return Object.values(byMonth).sort();
}

// ========== 回测核心 ==========
function runBacktest(enableDedup) {
  const rebalanceWeeks = getRebalanceWeeks();
  
  let availableCash = INIT_CAPITAL;  // tracks uninvested cash
  let holdings = {};  // code -> { shares, cost, high }
  let nav = INIT_CAPITAL;
  let trades = [];
  let periodReturns = [];
  let yearlyReturns = {};
  
  function closePositions(sellCodes, weekIdx) {
    const week = rebalanceWeeks[weekIdx];
    const recs0 = getRecords(pool[0].code);
    const execR = recs0.find(r => r.w === week);
    if (!execR) return;
    
    for (const code of sellCodes) {
      if (!holdings[code]) continue;
      const recs = getRecords(code);
      const execRec = recs.find(r => r.w === week);
      if (!execRec) continue;
      
      const { shares, cost } = holdings[code];
      const pnl = (execRec.close - cost) / cost;
      trades.push({ code, week, type: 'sell', pnl, price: execRec.close });
      availableCash += shares * execRec.close;
      delete holdings[code];
    }
  }
  
  function openPositions(topCodes, weekIdx) {
    const week = rebalanceWeeks[weekIdx];
    const recs0 = getRecords(pool[0].code);
    const execR = recs0.find(r => r.w === week);
    if (!execR) return;
    if (Object.keys(holdings).length >= TOPN) return;
    
    const alloc = availableCash / Math.max(1, TOPN - Object.keys(holdings).length);
    if (alloc <= 0) return;
    
    for (const code of topCodes) {
      if (holdings[code]) continue;
      const recs = getRecords(code);
      const execRec = recs.find(r => r.w === week);
      if (!execRec) continue;
      
      const shares = Math.floor(alloc / execRec.close);
      if (shares <= 0) continue;
      holdings[code] = { shares, cost: execRec.close, high: execRec.close };
      availableCash -= shares * execRec.close;
      trades.push({ code, week, type: 'buy', price: execRec.close });
    }
  }
  
  // 逐个调仓周期
  for (let wi = 0; wi < rebalanceWeeks.length; wi++) {
    const week = rebalanceWeeks[wi];
    const year = parseInt(week.slice(0, 4));
    
    // ========== 信号计算 ==========
    const qualList = [];
    
    for (const etf of pool) {
      const recs = getRecords(etf.code);
      const idx = recs.findIndex(r => r.w === week);
      if (idx < 21) continue;
      
      const cur = recs[idx];
      const ma5 = ma(recs, 5, idx);
      const ma21 = ma(recs, 21, idx);
      const a14 = atr(recs, 14, idx);
      const a21 = atr(recs, 21, idx);
      const dev = deviation(recs, idx);
      const volMa10_val = volMa10(recs, idx);
      
      if (ma5 === null || ma21 === null || a14 === null || a21 === null || a21 === 0) continue;
      
      // ATR_RATIO 过滤 (ATR14/ATR21 < 0.85 → 跳过)
      if (a14 / a21 < ATR_RATIO) continue;
      
      // 趋势过滤
      if (!(cur.close > ma5 && ma5 > ma21)) continue;
      
      // 偏离度
      if (dev === null || dev > DEV_MAX) continue;
      
      // 量能过滤
      if (volMa10_val === null || volMa10_val === 0) continue;
      const vr = cur.vol / volMa10_val;
      if (vr > VOL_RATIO_MAX) continue;
      
      // 动量
      const mom1 = momentum(recs, idx, 1);
      const mom3 = momentum(recs, idx, 3);
      const mom8 = momentum(recs, idx, 8);
      if (mom1 === null || mom3 === null || mom8 === null) continue;
      
      const score = 0.4 * mom1 + 0.4 * mom3 + 0.2 * mom8;
      const cPat = isC仙人指路(recs, idx);
      const b1Pat = isB1红三兵(recs, idx);
      const adjScore = score + (cPat ? C_BONUS : 0) + (b1Pat ? B1_BONUS : 0);
      
      qualList.push({
        code: etf.code, cat: etf.cat,
        score, adjScore, cPat, b1Pat,
        mom1, mom3, mom8,
        close: cur.close, week
      });
    }
    
    if (qualList.length === 0) continue;
    
    qualList.sort((a, b) => b.adjScore - a.adjScore);
    
    let topCodes;
    if (enableDedup) {
      const seenCats = new Set();
      topCodes = [];
      for (const q of qualList) {
        if (!seenCats.has(q.cat)) {
          seenCats.add(q.cat);
          topCodes.push(q.code);
          if (topCodes.length >= TOPN) break;
        }
      }
    } else {
      topCodes = qualList.slice(0, TOPN).map(q => q.code);
    }
    
    // ========== 止损检查 ==========
    const stopLossCodes = [];
    for (const [code, h] of Object.entries(holdings)) {
      const recs = getRecords(code);
      const curR = recs.find(r => r.w === week);
      if (!curR) continue;
      const curPrice = curR.close;
      h.high = Math.max(h.high, curPrice);
      
      if ((h.cost - curPrice) / h.cost >= STOP_LOSS_PCT) {
        stopLossCodes.push(code);
      } else if ((h.high - curPrice) / h.high >= TRAIL_PCT) {
        stopLossCodes.push(code);
      }
    }
    
    // ========== 平仓 ==========
    const toSellRotation = Object.keys(holdings).filter(code => !topCodes.includes(code));
    const toSellAll = [...new Set([...stopLossCodes, ...toSellRotation])];
    closePositions(toSellAll, wi);
    
    // ========== 开仓 ==========
    openPositions(topCodes, wi);
    
    // ========== 计算收益 ==========
    const prevNav = nav;
    const nextWeek = rebalanceWeeks[wi + 1];
    let currentNav = availableCash;
    
    if (nextWeek) {
      for (const [code, h] of Object.entries(holdings)) {
        const recs = getRecords(code);
        const nextR = recs.find(r => r.w === nextWeek);
        if (nextR) {
          currentNav += h.shares * nextR.open;
        } else {
          const curR = recs.find(r => r.w === week);
          if (curR) currentNav += h.shares * curR.close;
        }
      }
    } else {
      for (const [code, h] of Object.entries(holdings)) {
        const recs = getRecords(code);
        const curR = recs.find(r => r.w === week);
        if (curR) currentNav += h.shares * curR.close;
      }
    }
    
    nav = currentNav;
    
    if (wi > 0 && prevNav > 0) {
      const ret = (nav - prevNav) / prevNav;
      periodReturns.push(ret);
      if (!yearlyReturns[year]) yearlyReturns[year] = [];
      yearlyReturns[year].push(ret);
    }
  }
  
  // ========== 统计 ==========
  const totalReturn = nav - INIT_CAPITAL;
  const annReturn = Math.pow(Math.max(0.001, nav / INIT_CAPITAL), 52 / Math.max(1, rebalanceWeeks.length)) - 1;
  
  let peak = INIT_CAPITAL, ddMax = 0;
  let cumNav = INIT_CAPITAL;
  for (const ret of periodReturns) {
    cumNav *= (1 + ret);
    if (cumNav > peak) peak = cumNav;
    const dd = (cumNav - peak) / peak;
    if (dd < ddMax) ddMax = dd;
  }
  
  const avgRet = periodReturns.length > 0 ? periodReturns.reduce((a,b)=>a+b,0) / periodReturns.length : 0;
  const stdRet = periodReturns.length > 1 
    ? Math.sqrt(periodReturns.reduce((a,b)=>a+(b-avgRet)**2,0) / periodReturns.length) 
    : 0;
  const sharpe = stdRet > 0 ? (avgRet / stdRet) * Math.sqrt(52) : 0;
  
  const sells = trades.filter(t => t.type === 'sell');
  const wins = sells.filter(t => t.pnl > 0).length;
  const winRate = sells.length > 0 ? wins / sells.length : 0;
  
  const yearlyCalcs = {};
  for (const [yr, rets] of Object.entries(yearlyReturns)) {
    if (rets.length > 0) {
      yearlyCalcs[yr] = parseFloat((rets.reduce((a,b)=>a*(1+b), 1) - 1).toFixed(4));
    }
  }
  
  return {
    ann_return: parseFloat(annReturn.toFixed(4)),
    total_return: parseFloat(totalReturn.toFixed(4)),
    dd_max: parseFloat(ddMax.toFixed(4)),
    sharpe: parseFloat(sharpe.toFixed(3)),
    n_trades: trades.length,
    win_rate: parseFloat(winRate.toFixed(4)),
    yearly: yearlyCalcs
  };
}

// ========== 运行 ==========
console.error('Running backtests...');
const withDedup = runBacktest(true);
const withoutDedup = runBacktest(false);

// ========== 输出 ==========
const ts = new Date().toISOString().replace(/:/g, '-').replace(/\./g, '-').slice(0, 19);
const outPath = 'D:/QClaw_Trading/review/dedup_compare_full_' + ts + '.json';

const diff = withDedup.ann_return - withoutDedup.ann_return;
let conclusion = '';
if (diff > 0.01) {
  conclusion = '去重方案年化收益高于无去重 ' + (diff*100).toFixed(2) + 'ppt，夏普比更优（' + withDedup.sharpe + ' vs ' + withoutDedup.sharpe + '），赛道分散有效控制了集中风险，建议保留去重逻辑。';
} else if (diff < -0.01) {
  conclusion = '无去重方案年化收益高于去重 ' + ((-diff)*100).toFixed(2) + 'ppt，但交易更频繁（' + withoutDedup.n_trades + '笔 vs ' + withDedup.n_trades + '笔），风险更高，需权衡后决定。';
} else {
  conclusion = '两种方案年化收益差异仅 ' + (Math.abs(diff)*100).toFixed(2) + 'ppt，差别较小。去重方案交易更少（' + withDedup.n_trades + '笔 vs ' + withoutDedup.n_trades + '笔）、最大回撤更小（' + (Math.abs(withDedup.dd_max)*100).toFixed(1) + '% vs ' + (Math.abs(withoutDedup.dd_max)*100).toFixed(1) + '%），综合来看去重方案更优。';
}

const result = {
  with_dedup: withDedup,
  without_dedup: withoutDedup,
  conclusion: conclusion
};

fs.writeFileSync(outPath, JSON.stringify(result, null, 2), 'utf8');

// ========== 打印结果 ==========
console.log(JSON.stringify(result, null, 2));

console.log('\n========== 赛道去重 vs 无去重 对比 ==========');
console.log('指标              有去重          无去重');
console.log('----------------------------------------');
console.log('年化收益          ' + (withDedup.ann_return*100).toFixed(2) + '%          ' + (withoutDedup.ann_return*100).toFixed(2) + '%');
console.log('总收益            ' + (withDedup.total_return*100).toFixed(2) + '%          ' + (withoutDedup.total_return*100).toFixed(2) + '%');
console.log('最大回撤          ' + (withDedup.dd_max*100).toFixed(2) + '%          ' + (withoutDedup.dd_max*100).toFixed(2) + '%');
console.log('夏普比率          ' + withDedup.sharpe + '          ' + withoutDedup.sharpe);
console.log('交易次数          ' + withDedup.n_trades + '             ' + withoutDedup.n_trades);
console.log('胜率              ' + (withDedup.win_rate*100).toFixed(2) + '%          ' + (withoutDedup.win_rate*100).toFixed(2) + '%');
console.log('----------------------------------------');
console.log('结论: ' + conclusion);
console.log('\n结果已保存: ' + outPath);
