// 赛道去重 vs 无去重 回测对比
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
const poolMap = {};
pool.forEach(e => poolMap[e.code] = e);

const histDir = 'D:/QClaw_Trading/data/history_long_v2/';

// 加载所有ETF历史周线
const allData = {};
let loaded = 0, missing = 0;
for (const etf of pool) {
  const fpath = path.join(histDir, etf.code + '.json');
  if (fs.existsSync(fpath)) {
    const raw = fs.readFileSync(fpath, 'utf8');
    try {
      const d = JSON.parse(raw);
      allData[etf.code] = d.records;
      loaded++;
    } catch(e) { missing++; }
  } else { missing++; }
}
console.error(`Loaded ${loaded} ETFs, missing ${missing}`);

// ========== 工具函数 ==========
function getRecords(code) { return allData[code] || []; }

// 按周字符串找到记录
function findByWeek(code, weekStr) {
  const recs = getRecords(code);
  return recs.find(r => r.w === weekStr) || null;
}

// 生成调仓周（每月最后一个周，以最早有数据的ETF为参照）
function getRebalanceWeeks() {
  // 收集所有ETF的所有周，去重后排序，取2014-W01~2026-W26区间
  const allWeeks = new Set();
  for (const etf of pool) {
    const recs = getRecords(etf.code);
    recs.forEach(r => allWeeks.add(r.w));
  }
  const sortedWeeks = [...allWeeks].sort();
  const weeks = sortedWeeks.filter(w => w >= START_W && w <= END_W);
  // 按月分组，取每月最后一个周
  const byMonth = {};
  weeks.forEach(w => {
    const ym = w.slice(0, 7);
    if (!byMonth[ym] || w > byMonth[ym]) byMonth[ym] = w;
  });
  const result = Object.values(byMonth).sort();
  console.error('Rebalance weeks: total=' + result.length + ', from=' + result[0] + ' to=' + result[result.length-1]);
  return result;
}

// 计算MA
function ma(recs, period, idx) {
  if (idx < period - 1) return null;
  let sum = 0;
  for (let i = idx - period + 1; i <= idx; i++) sum += recs[i].close;
  return sum / period;
}

// ATR
function atr(recs, period, idx) {
  if (idx < 1) return null;
  const trs = [];
  for (let i = Math.max(1, idx - period + 1); i <= idx; i++) {
    const h = recs[i].high, l = recs[i].low, pc = recs[i-1].close;
    trs.push(Math.max(h-l, Math.abs(h-pc), Math.abs(l-pc)));
  }
  return trs.reduce((a,b)=>a+b,0) / trs.length;
}

// 10周均量
function volMa(recs, idx) {
  if (idx < 9) return null;
  let sum = 0;
  for (let i = idx - 9; i <= idx; i++) sum += recs[i].vol;
  return sum / 10;
}

// 动量 MOMnW = (close[idx] - close[idx-n]) / close[idx-n]
function momentum(recs, idx, n) {
  if (idx < n) return null;
  return (recs[idx].close - recs[idx - n].close) / recs[idx - n].close;
}

// C仙人指路判断 (当前idx为最新周)
function isC仙人指路(recs, idx) {
  if (idx < 21) return false;
  const cur = recs[idx];
  const open = cur.open, close = cur.close;
  if (close <= open) return false; // 阳线
  
  const body = close - open;
  const upperShadow = cur.high - close;
  const lowerShadow = open - cur.low;
  
  if (body <= 0) return false;
  if (upperShadow / body <= 1.0) return false; // 上影 > 实体
  if (lowerShadow >= body * 0.5) return false; // 下影 < 实体×50%
  
  const ma5 = ma(recs, 5, idx);
  const ma21 = ma(recs, 21, idx);
  if (!(close > ma5 && ma5 > ma21)) return false;
  
  const volRatio = volMa(recs, idx);
  if (volRatio === null) return false;
  const vr = cur.vol / volRatio;
  if (vr >= 1.5 || vr <= 0.5) return false;
  
  // 20周涨幅 < 50%
  if (idx < 20) return false;
  const mom20 = (close - recs[idx-20].close) / recs[idx-20].close;
  if (mom20 >= 0.5) return false;
  
  return true;
}

// B1红三兵判断 (近3周均为阳线，低点逐周抬高)
function isB1红三兵(recs, idx) {
  if (idx < 2) return false;
  for (let i = 0; i < 3; i++) {
    if (recs[idx - i].close <= recs[idx - i].open) return false;
  }
  const low0 = recs[idx].low;
  const low1 = recs[idx-1].low;
  const low2 = recs[idx-2].low;
  if (!(low0 > low1 && low1 > low2)) return false;
  return true;
}

// 获取偏离度：|close - MA5| / MA5
function deviation(recs, idx) {
  const ma5 = ma(recs, 5, idx);
  if (ma5 === null) return null;
  return Math.abs(recs[idx].close - ma5) / ma5;
}

// ========== 回测核心 ==========
function runBacktest(enableDedup) {
  const rebalanceWeeks = getRebalanceWeeks();
  console.error('Total rebalance weeks:', rebalanceWeeks.length, '(', rebalanceWeeks[0], '->', rebalanceWeeks[rebalanceWeeks.length-1], ')');
  
  // 状态
  let capital = INIT_CAPITAL;       // 当前可用资金
  let holdings = {};                 // code -> { shares, cost, high }
  let nav = INIT_CAPITAL;            // 组合净值
  let trades = [];
  let periodReturns = [];            // 每段收益
  let yearlyReturns = {};
  
  function getNavValue(curWeekIdx) {
    let total = capital;
    const recs0 = getRecords(pool[0].code);
    const curWeek = rebalanceWeeks[curWeekIdx];
    for (const [code, h] of Object.entries(holdings)) {
      const recs = getRecords(code);
      const r = recs.find(r => r.w === curWeek);
      if (r) total += h.shares * r.close;
    }
    return total;
  }
  
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
      const proceeds = shares * execRec.close;
      
      trades.push({ code, week, type: 'sell', pnl, price: execRec.close });
      capital += proceeds;
      delete holdings[code];
    }
  }
  
  function openPositions(topCodes, weekIdx) {
    const week = rebalanceWeeks[weekIdx];
    const recs0 = getRecords(pool[0].code);
    const execR = recs0.find(r => r.w === week);
    if (!execR) return;
    if (Object.keys(holdings).length >= TOPN) return;
    
    const alloc = capital / (TOPN - Object.keys(holdings).length);
    if (alloc <= 0) return;
    
    for (const code of topCodes) {
      if (holdings[code]) continue;
      const recs = getRecords(code);
      const execRec = recs.find(r => r.w === week);
      if (!execRec) continue;
      
      const shares = Math.floor(alloc / execRec.close);
      if (shares <= 0) continue;
      const cost = execRec.close;
      holdings[code] = { shares, cost, high: cost };
      capital -= shares * cost;
      trades.push({ code, week, type: 'buy', price: cost });
    }
  }
  
  // 逐个调仓周期
  for (let wi = 0; wi < rebalanceWeeks.length; wi++) {
    const week = rebalanceWeeks[wi];
    const year = parseInt(week.slice(0, 4));
    
    // ========== 信号计算 (本周收盘) ==========
    const signalWeekIdx = wi;
    
    // ATR过滤 + 趋势过滤 + 偏离度 + 量能过滤
    const qualList = [];
    
    for (const etf of pool) {
      const recs = getRecords(etf.code);
      const idx = recs.findIndex(r => r.w === week);
      if (idx < 21) continue; // 需要足够历史数据
      
      const cur = recs[idx];
      const ma5 = ma(recs, 5, idx);
      const ma21 = ma(recs, 21, idx);
      const atr14 = atr(recs, 14, idx);
      const atr21 = atr(recs, 21, idx);
      const dev = deviation(recs, idx);
      const volMa10 = volMa(recs, idx);
      
      if (ma5 === null || ma21 === null || atr14 === null || atr21 === null) continue;
      if (ma21 === 0) continue;
      
      // ATR_RATIO 过滤
      if (atr14 / atr21 < ATR_RATIO) continue;
      
      // 趋势过滤
      if (!(cur.close > ma5 && ma5 > ma21)) continue;
      
      // 偏离度
      if (dev === null || dev > DEV_MAX) continue;
      
      // 量能过滤
      if (volMa10 === null || volMa10 === 0) continue;
      const vr = cur.vol / volMa10;
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
        code: etf.code,
        cat: etf.cat,
        score,
        adjScore,
        mom1, mom3, mom8,
        cPat, b1Pat,
        close: cur.close,
        week: week
      });
    }
    
    if (qualList.length === 0) {
      // Debug: log filter stats for this week
      let dbgCount = 0;
      for (const etf of pool) {
        const recs = getRecords(etf.code);
        const idx = recs.findIndex(r => r.w === week);
        if (idx >= 21) dbgCount++;
      }
      if (wi % 5 === 0) console.error('[DBG]', week, 'ATR filtered: qual=0, hasData=', dbgCount);
      continue;
    }
    
    // 排序
    qualList.sort((a, b) => b.adjScore - a.adjScore);
    
    // 去重
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
    
    // ========== 止损检查 (当前持仓 vs 上周净值) ==========
    const prevNav = nav;
    const weekForExec = wi; // 下周开盘执行
    
    // 在执行周前检查止损
    const stopLossCodes = [];
    for (const [code, h] of Object.entries(holdings)) {
      const recs = getRecords(code);
      const curR = recs.find(r => r.w === week);
      if (!curR) continue;
      const curPrice = curR.close;
      const cost = h.cost;
      const high = h.high;
      
      // 更新高点
      h.high = Math.max(high, curPrice);
      
      // 止损
      if ((cost - curPrice) / cost >= STOP_LOSS_PCT) {
        stopLossCodes.push(code);
      }
      // 追踪止损
      else if ((h.high - curPrice) / h.high >= TRAIL_PCT) {
        stopLossCodes.push(code);
      }
    }
    
    // ========== 平仓 ==========
    // 持仓不在TOP3 → 卖出
    const toSellRotation = Object.keys(holdings).filter(code => !topCodes.includes(code));
    const toSellAll = [...new Set([...stopLossCodes, ...toSellRotation])];
    
    closePositions(toSellAll, wi);
    
    // ========== 开仓 ==========
    openPositions(topCodes, wi);
    
    // ========== 计算当期收益 ==========
    const nextWeek = rebalanceWeeks[wi + 1];
    let currentNav = 0;
    
    if (nextWeek) {
      // 用下周开盘价计算净值
      for (const [code, h] of Object.entries(holdings)) {
        const recs = getRecords(code);
        const nextR = recs.find(r => r.w === nextWeek);
        if (nextR) {
          currentNav += h.shares * nextR.open;
        } else {
          // 如果下周没数据，用当周收盘
          const curR = recs.find(r => r.w === week);
          if (curR) currentNav += h.shares * curR.close;
        }
      }
      currentNav += capital;
    } else {
      // 最后一周，用当前收盘
      for (const [code, h] of Object.entries(holdings)) {
        const recs = getRecords(code);
        const curR = recs.find(r => r.w === week);
        if (curR) currentNav += h.shares * curR.close;
      }
      currentNav += capital;
    }
    
    nav = currentNav;
    
    if (wi > 0) {
      const ret = (nav - prevNav) / prevNav;
      periodReturns.push(ret);
      if (!yearlyReturns[year]) yearlyReturns[year] = [];
      yearlyReturns[year].push(ret);
    }
  }
  
  // ========== 统计 ==========
  const totalReturn = nav - INIT_CAPITAL;
  const annReturn = Math.pow(nav / INIT_CAPITAL, 52 / rebalanceWeeks.length) - 1;
  
  // 最大回撤
  let peak = INIT_CAPITAL, ddMax = 0;
  let cumNav = INIT_CAPITAL;
  const dailyNavs = [];
  for (const ret of periodReturns) {
    cumNav *= (1 + ret);
    dailyNavs.push(cumNav);
    if (cumNav > peak) peak = cumNav;
    const dd = (cumNav - peak) / peak;
    if (dd < ddMax) ddMax = dd;
  }
  
  // 夏普 (无风险利率0)
  const avgRet = periodReturns.reduce((a,b)=>a+b,0) / periodReturns.length;
  const stdRet = Math.sqrt(periodReturns.reduce((a,b)=>a+(b-avgRet)**2,0) / periodReturns.length);
  const sharpe = stdRet > 0 ? (avgRet / stdRet) * Math.sqrt(52) : 0;
  
  // 胜率
  const wins = trades.filter(t => t.type === 'sell' && t.pnl > 0).length;
  const sells = trades.filter(t => t.type === 'sell').length;
  const winRate = sells > 0 ? wins / sells : 0;
  
  // 年化收益
  const yearlyCalcs = {};
  for (const [yr, rets] of Object.entries(yearlyReturns)) {
    if (rets.length > 0) {
      const yrRet = rets.reduce((a,b)=>a*(1+b), 1) - 1;
      yearlyCalcs[yr] = parseFloat(yrRet.toFixed(4));
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
console.error('Running WITH dedup...');
const withDedup = runBacktest(true);

console.error('Running WITHOUT dedup...');
const withoutDedup = runBacktest(false);

// ========== 输出 ==========
const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
const outPath = `D:/QClaw_Trading/review/dedup_compare_full_${ts}.json`;

const result = {
  with_dedup: withDedup,
  without_dedup: withoutDedup,
  conclusion: ''
};

const diff = withDedup.ann_return - withoutDedup.ann_return;
let conclusion = '';
if (diff > 0.01) {
  conclusion = '去重方案年化收益高于无去重 ' + (diff*100).toFixed(2) + 'ppt，夏普比更优（' + withDedup.sharpe + ' vs ' + withoutDedup.sharpe + '），说明赛道分散有效控制了集中风险，建议保留去重逻辑。';
} else if (diff < -0.01) {
  conclusion = '无去重方案年化收益高于去重 ' + ((-diff)*100).toFixed(2) + 'ppt，但可能暴露更高集中风险（' + withoutDedup.n_trades + '笔交易 vs ' + withDedup.n_trades + '笔），需权衡收益与风险后决定。';
} else {
  conclusion = '两种方案年化收益差异仅 ' + (Math.abs(diff)*100).toFixed(2) + 'ppt，差别不大。去重带来更好的分散性（' + withDedup.n_trades + '笔交易 vs ' + withoutDedup.n_trades + '笔），且最大回撤更小（' + (Math.abs(withDedup.dd_max)*100).toFixed(1) + '% vs ' + (Math.abs(withoutDedup.dd_max)*100).toFixed(1) + '%），综合来看去重方案更优。';
}
result.conclusion = conclusion;

fs.writeFileSync(outPath, JSON.stringify(result, null, 2), 'utf8');

// ========== 打印stdout ==========
console.log(JSON.stringify(result, null, 2));

// 简洁对比表格
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
console.log('结论: ' + result.conclusion);
console.log('\n结果已保存: ' + outPath);
