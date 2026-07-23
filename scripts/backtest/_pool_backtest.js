// ============================================================
// 策略优化 v3：组合回测引擎
// 目标：找夏普>1的策略组合
// ============================================================
const fs = require('fs');
const path = require('path');

// ─── 数据加载 ───────────────────────────────────────────────
const HIST = 'D:\\QClaw_Trading\\data\\history';
const scanPool = JSON.parse(fs.readFileSync('D:/QClaw_Trading/scripts/scan/etf_pool.json', 'utf8'));
const allCodes = Array.isArray(scanPool)
  ? scanPool.map(e => typeof e === 'object' ? ((e.market || 'sh') + (e.code || e.name || '')).toLowerCase() : e)
  : Object.values(scanPool).filter(v => typeof v === 'string');

function getRecords(raw) {
  if (!raw) return null;
  if (Array.isArray(raw)) return raw;
  if (raw.records) {
    // records可能是数组，也可能是对象{0:{...},1:{...},...}
    if (Array.isArray(raw.records)) return raw.records;
    if (typeof raw.records === 'object') {
      // 对象 → 提取为数组
      if (raw.records.days) return raw.records.days;
      if (raw.records.qfqday) return raw.records.qfqday;
      if (raw.records.day) return raw.records.day;
      // 纯对象{0:{...},1:{...}} → 转为数组
      const keys = Object.keys(raw.records).filter(k => !isNaN(k)).sort((a,b)=>a-b);
      if (keys.length > 0) return keys.map(k => raw.records[k]);
    }
  }
  return null;
}
function getClose(d) {
  if (!d) return 0;
  if (typeof d === 'number') return d;
  return d.close || d.c || d.C || d.price || 0;
}
function loadETF(code) {
  // Case-insensitive file lookup
  const lc = code.toLowerCase();
  const files = fs.readdirSync(HIST).filter(f => f.endsWith('.json'));
  const match = files.find(f => f.replace(/\.(json|JSON)$/, '').toLowerCase() === lc);
  if (!match) return null;
  try {
    const raw = JSON.parse(fs.readFileSync(path.join(HIST, match), 'utf8'));
    const recs = getRecords(raw);
    if (!recs || recs.length < 50) return null;
    const closes = recs.map(getClose).filter(v => v > 0);
    return { code, name: raw.name || code, closes, n: closes.length };
  } catch(e) { return null; }
}

const etfs = allCodes.map(code => loadETF(code)).filter(e => e && e.n >= 200);
console.log(`加载 ${etfs.length} 只ETF (数据>=200条)\n`);

// ─── 技术指标 ──────────────────────────────────────────────
function sma(arr, n) {
  return arr.map((_, i) => {
    if (i < n - 1) return null;
    const sum = arr.slice(i - n + 1, i + 1).reduce((a, b) => a + b, 0);
    return sum / n;
  });
}
function ema(arr, n) {
  const k = 2 / (n + 1);
  const out = [arr[0]];
  for (let i = 1; i < arr.length; i++) out.push(arr[i] * k + out[i - 1] * (1 - k));
  return out;
}
function macd(closes, f = 12, s = 26, sig = 9) {
  const ef = ema(closes, f), es = ema(closes, s);
  const macdLine = ef.map((v, i) => v - es[i]);
  const signalLine = ema(macdLine, sig);
  const hist = macdLine.map((v, i) => v - signalLine[i]);
  return { macdLine, signalLine, hist };
}
function rsi14(closes, endIdx) {
  let gain = 0, loss = 0;
  for (let j = Math.max(1, endIdx - 13); j <= endIdx; j++) {
    const r = closes[j] / closes[j - 1] - 1;
    if (r > 0) gain += r; else loss += Math.abs(r);
  }
  const ag = gain / 14, al = loss / 14;
  return al === 0 ? 70 : 100 - 100 / (1 + ag / al);
}
function volCalc(rets) {
  if (rets.length < 2) return 0.25;
  const m = rets.reduce((a, b) => a + b, 0) / rets.length;
  const v = rets.reduce((a, b) => a + (b - m) ** 2, 0) / rets.length;
  return Math.sqrt(v * 252);
}

// ─── 策略定义 ──────────────────────────────────────────────

// S0: 基准 MA20 + MACD 金叉 + 固定止损5%
function stratS0(closes) {
  if (closes.length < 250) return null;
  const eq = [1]; let pos = 0, entryPrice = 0;
  for (let i = 1; i < closes.length; i++) {
    if (i < 30) { eq.push(eq[i-1]); continue; }
    const slice = closes.slice(0, i+1);
    const ma20 = sma(slice, 20);
    const { hist } = macd(slice);
    const price = closes[i];
    if (!pos && ma20[i] && price > ma20[i] && hist[i] > 0 && hist[i-1] <= 0) {
      pos = eq[i-1] / price; entryPrice = price; eq[i] = pos * price;
    } else if (pos > 0) {
      if (price < entryPrice * 0.95) { pos = 0; eq[i] = eq[i-1]; }
      else eq[i] = pos * price;
    } else {
      eq[i] = eq[i-1];
    }
  }
  return eq;
}

// S1: MA20 + MACD + ATR追踪止损(2ATR)
function stratS1(closes) {
  if (closes.length < 250) return null;
  const eq = [1]; let pos = 0, peakPrice = 0;
  for (let i = 1; i < closes.length; i++) {
    if (i < 30) { eq.push(eq[i-1]); continue; }
    const slice = closes.slice(0, i+1);
    const ma20 = sma(slice, 20);
    const { hist } = macd(slice);
    const price = closes[i];
    if (!pos && ma20[i] && price > ma20[i] && hist[i] > 0 && hist[i-1] <= 0) {
      pos = eq[i-1] / price; peakPrice = price; eq[i] = pos * price;
    } else if (pos > 0) {
      if (price > peakPrice) peakPrice = price;
      const stop = peakPrice * 0.96; // 4% trail
      if (price < stop) { pos = 0; eq[i] = eq[i-1]; }
      else eq[i] = pos * price;
    } else {
      eq[i] = eq[i-1];
    }
  }
  return eq;
}

// S2: MA20上方 + RSI<65回调入场 + 5%止损
function stratS2(closes) {
  if (closes.length < 250) return null;
  const eq = [1]; let pos = 0, entryPrice = 0;
  for (let i = 1; i < closes.length; i++) {
    if (i < 30) { eq.push(eq[i-1]); continue; }
    const slice = closes.slice(0, i+1);
    const ma20 = sma(slice, 20);
    const { hist } = macd(slice);
    const rsi = rsi14(slice, i);
    const price = closes[i];
    if (!pos && ma20[i] && price > ma20[i] && hist[i] > 0 && hist[i-1] <= 0 && rsi < 65 && rsi > 35) {
      pos = eq[i-1] / price; entryPrice = price; eq[i] = pos * price;
    } else if (pos > 0) {
      if (price < entryPrice * 0.95 || rsi > 80) { pos = 0; eq[i] = eq[i-1]; }
      else eq[i] = pos * price;
    } else {
      eq[i] = eq[i-1];
    }
  }
  return eq;
}

// S3: MA25 + MACD + RSI<60 + ATR止损(5%) + 波动率<40%
function stratS3(closes) {
  if (closes.length < 250) return null;
  const eq = [1]; let pos = 0, entryPrice = 0, peakPrice = 0;
  for (let i = 1; i < closes.length; i++) {
    if (i < 30) { eq.push(eq[i-1]); continue; }
    const slice = closes.slice(0, i+1);
    const ma25 = sma(slice, 25);
    const { hist } = macd(slice);
    const rsi = rsi14(slice, i);
    const price = closes[i];
    if (!pos && ma25[i] && price > ma25[i] && hist[i] > 0 && hist[i-1] <= 0 && rsi < 60 && rsi > 35) {
      pos = eq[i-1] / price; entryPrice = price; peakPrice = price; eq[i] = pos * price;
    } else if (pos > 0) {
      if (price > peakPrice) peakPrice = price;
      if (price < entryPrice * 0.95 || price < peakPrice * 0.95 || rsi > 80) { pos = 0; eq[i] = eq[i-1]; }
      else eq[i] = pos * price;
    } else {
      eq[i] = eq[i-1];
    }
  }
  return eq;
}

// S4: 布林带20下轨反弹 + MA20确认 + MACD 趋势
function stratS4(closes) {
  if (closes.length < 250) return null;
  const eq = [1]; let pos = 0, entryPrice = 0;
  for (let i = 1; i < closes.length; i++) {
    if (i < 30) { eq.push(eq[i-1]); continue; }
    const slice = closes.slice(0, i+1);
    const ma20 = sma(slice, 20);
    const { hist } = macd(slice);
    const price = closes[i];
    // BB lower
    const n = 20, m = ma20[i];
    let sd = 0;
    if (m !== null) {
      for (let j = Math.max(0, i-n+1); j <= i; j++) sd += (closes[j]-m)**2;
      sd = Math.sqrt(sd/n);
    }
    const bbLower = m !== null ? m - 2*sd : 0;
    const bbMid = m;
    const buy = (!pos && hist[i] > 0 && hist[i-1] <= 0 && price > bbMid && bbLower > 0 && price <= bbLower * 1.02);
    if (buy) { pos = eq[i-1] / price; entryPrice = price; eq[i] = pos * price; }
    else if (pos > 0) {
      if (price < entryPrice * 0.96) { pos = 0; eq[i] = eq[i-1]; }
      else if (price < bbMid && hist[i] < 0 && hist[i-1] >= 0) { pos = 0; eq[i] = eq[i-1]; }
      else eq[i] = pos * price;
    } else { eq[i] = eq[i-1]; }
  }
  return eq;
}

// ─── 绩效计算 ──────────────────────────────────────────────
function calcPerf(eq, period) {
  if (!eq || eq.length < period) return null;
  const slice = eq.slice(-period);
  const rets = slice.slice(1).map((v,i) => Math.log(v/slice[i]));
  const ann = rets.reduce((a,b)=>a+b,0)/period*252;
  const vol = volCalc(rets);
  const sharpe = vol > 0.001 ? ann/vol : 0;
  let peak = slice[0], dd = 0;
  for (const v of slice) { if(v>peak) peak=v; dd=Math.max(dd,(peak-v)/peak); }
  const totalRet = (eq[eq.length-1]-eq[eq.length-period-1])/(eq[eq.length-period-1]||1);
  let trades = 0;
  for (let i=1; i<eq.length; i++) if (eq[i]!==eq[i-1] && eq[i]>0) trades++;
  return { totalRet, ann, vol, sharpe, dd, trades, period };
}

// ─── 主回测 ────────────────────────────────────────────────
const strategies = [
  { name: 'S0 基准 MA20+MACD+5%止损', fn: stratS0 },
  { name: 'S1 MA20+MACD+4%追踪止损', fn: stratS1 },
  { name: 'S2 MA20+MACD+RSI回调入场', fn: stratS2 },
  { name: 'S3 MA25+MACD+RSI+ATR止损', fn: stratS3 },
  { name: 'S4 布林带下轨反弹入场', fn: stratS4 },
];

const PERIOD_1Y = 240;  // 1年
const PERIOD_6M = 120;  // 6个月

console.log('═══════════════════════════════════════════════════════════════════');
console.log(`  多策略 × ${etfs.length}只ETF 组合回测`);
console.log('═══════════════════════════════════════════════════════════════════\n');

function runBacktest(period, label) {
  console.log(`\n── ${label} (n=${etfs.length}只ETF) ──`);
  for (const strat of strategies) {
    const perfs = [];
    for (const etf of etfs) {
      const eq = strat.fn(etf.closes);
      const p = calcPerf(eq, period);
      if (p) perfs.push({ code: etf.code, name: etf.name, ...p });
    }
    if (!perfs.length) continue;
    const avgAnn = perfs.reduce((a,p)=>a+p.ann,0)/perfs.length;
    const avgSharpe = perfs.reduce((a,p)=>a+p.sharpe,0)/perfs.length;
    const avgDD = perfs.reduce((a,p)=>a+p.dd,0)/perfs.length;
    const winRate = perfs.filter(p=>p.sharpe>0).length/perfs.length;
    const totalTrades = perfs.reduce((a,p)=>a+p.trades,0);
    const flag = avgSharpe >= 1.0 ? '★★' : avgSharpe >= 0.5 ? '☆' : '  ';
    console.log(`${flag}${strat.name.padEnd(30)} | 夏普=${avgSharpe.toFixed(3)} 年化=${(avgAnn*100).toFixed(1)}% 胜率=${(winRate*100).toFixed(0)}% 回撤=${(avgDD*100).toFixed(1)}%`);
  }
}

runBacktest(PERIOD_1Y, '1年期回测(近240交易日)');
runBacktest(PERIOD_6M, '半年期回测(近120交易日)');

// ─── 波动率过滤效果 ────────────────────────────────────────
console.log('\n\n═══════════════════════════════════════════════════════════════════');
console.log('  波动率过滤效果（S3: MA25+MACD+RSI+ATR止损）');
console.log('═══════════════════════════════════════════════════════════════════\n');

for (const volThresh of [0.35, 0.40, 0.45, 0.50]) {
  const strat = strategies[3]; // S3
  const perfs = [], perfsF = [];
  for (const etf of etfs) {
    const eq = strat.fn(etf.closes);
    const p = calcPerf(eq, PERIOD_1Y);
    if (!p) continue;
    perfs.push(p);
    if (p.vol < volThresh) perfsF.push(p);
  }
  const avgA = perfs.reduce((a,p)=>a+p.ann,0)/perfs.length;
  const avgAF = perfsF.reduce((a,p)=>a+p.ann,0)/Math.max(1,perfsF.length);
  const avgShA = perfs.reduce((a,p)=>a+p.sharpe,0)/perfs.length;
  const avgShAF = perfsF.reduce((a,p)=>a+p.sharpe,0)/Math.max(1,perfsF.length);
  const winA = perfs.filter(p=>p.sharpe>0).length/perfs.length;
  const winAF = perfsF.length ? perfsF.filter(p=>p.sharpe>0).length/perfsF.length : 0;
  console.log(`波动率<${(volThresh*100).toFixed(0)}% (n=${perfsF.length}/${perfs.length}) | 夏普=${avgShAF.toFixed(3)} 年化=${(avgAF*100).toFixed(1)}% 胜率=${(winAF*100).toFixed(0)}% | vs全量: 夏普=${avgShA.toFixed(3)}`);
}

// ─── Top单只ETF ────────────────────────────────────────────
console.log('\n\n═══════════════════════════════════════════════════════════════════');
console.log('  各策略 Top10 单只ETF（近1年）');
console.log('═══════════════════════════════════════════════════════════════════\n');

for (const strat of strategies) {
  const perfs = [];
  for (const etf of etfs) {
    const eq = strat.fn(etf.closes);
    const p = calcPerf(eq, PERIOD_1Y);
    if (p) perfs.push({ code: etf.code, name: etf.name, ...p });
  }
  const top10 = perfs.sort((a,b)=>b.sharpe-a.sharpe).slice(0, 10);
  console.log(`\n[${strat.name}]`);
  top10.forEach((p,i) => {
    const flag = p.sharpe >= 1.0 ? '★' : p.sharpe >= 0.5 ? '☆' : ' ';
    console.log(`  ${flag}${p.code} ${(p.name||'').padEnd(12)} 夏普=${p.sharpe.toFixed(3)} 年化=${(p.ann*100).toFixed(1)}% vol=${(p.vol*100).toFixed(1)}% DD=${(p.dd*100).toFixed(1)}%`);
  });
}

console.log('\n\n完成');
