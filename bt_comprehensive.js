/**
 * bt_comprehensive.js - MA10/MA20/MA30 长周期综合回测
 * 同时测试：指数(21年) vs ETF(3年) 真实差距
 */
const fs   = require('fs');
const path = require('path');

const DATA = 'D:/QClaw_Trading/data';
const INIT_CASH = 100000;

// ── 指标计算 ────────────────────────────────
function calcMA(closes, period) {
  const r = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) { r.push(null); continue; }
    let s = 0; for (let j = 0; j < period; j++) s += closes[i - j];
    r.push(s / period);
  }
  return r;
}

function calcMACD(closes, fast, slow, signal) {
  const ema = (data, p) => {
    const k = 2 / (p + 1);
    const e = [data[0]];
    for (let i = 1; i < data.length; i++) e.push(data[i] * k + e[i-1] * (1-k));
    return e;
  };
  const ef = ema(closes, fast), es = ema(closes, slow);
  const dif = ef.map((v, i) => v - es[i]);
  const k = 2 / (signal + 1);
  const dea = new Array(dif.length).fill(null);
  dea[slow - 1] = dif[slow - 1];
  for (let i = slow; i < dif.length; i++) dea[i] = dif[i] * k + dea[i-1] * (1-k);
  const osc = dif.map((v, i) => dea[i] !== null ? v - dea[i] : null);
  return { dif, dea, osc };
}

function maDir(ma, idx, lookback) {
  if (idx < lookback) return 'flat';
  const recent = ma.slice(Math.max(0, idx - lookback + 1), idx + 1).filter(v => v !== null);
  if (recent.length < 2) return 'flat';
  return recent[recent.length-1] > recent[0] ? 'up' : 'dn';
}

// ── 单次回测核心 ────────────────────────────
function backtest(records, label, cfg) {
  if (!records || records.length < 60) return null;
  const bars = records;
  const closes = bars.map(r => r.close);
  const maMap = {};
  cfg.MAs.forEach(ma => { maMap[ma] = calcMA(closes, ma); });
  const macd = calcMACD(closes, 12, 26, 9);

  let cash = INIT_CASH, shares = 0, state = 'out', entryPrice = 0, entryIdx = 0;
  const equity = [];
  const trades = [];

  for (let i = 26; i < bars.length; i++) {
    const price = closes[i];
    const nav = cash + shares * price;
    equity.push({ date: bars[i].date, nav });

    if (state === 'in') {
      // 止损
      if (cfg.stopLoss && price / entryPrice - 1 < -cfg.stopLoss) {
        cash += shares * price; trades.push({ date: bars[i].date, action: 'SELL(SL)', price, ret: (price/entryPrice-1)*100 });
        shares = 0; state = 'out'; continue;
      }
      // 跟踪止损（从N日后开始）
      if (cfg.tsl && i - entryIdx >= cfg.tslDays) {
        const peakPrice = Math.max(...closes.slice(entryIdx, i));
        if (price / peakPrice - 1 < -cfg.tsl) {
          cash += shares * price; trades.push({ date: bars[i].date, action: 'SELL(TSL)', price, ret: (price/entryPrice-1)*100 });
          shares = 0; state = 'out'; continue;
        }
      }
    }

    if (state === 'out') {
      // 买入：MA多头排列 + MACD金叉
      const primaryMA = maMap[cfg.MAs[0]][i];
      const macdCrossUp = i > 0 && macd.dif[i-1] < macd.dea[i-1] && macd.dif[i] > macd.dea[i] && macd.dif[i] > 0;
      const maUp = maDir(maMap[cfg.MAs[0]], i, cfg.maLookback) === 'up';
      // 多均线排列：每条均线均上升
      let allUp = true;
      for (let m = 1; m < cfg.MAs.length; m++) {
        if (maDir(maMap[cfg.MAs[m]], i, cfg.maLookback) !== 'up') { allUp = false; break; }
      }
      if (price > primaryMA && maUp && allUp && macdCrossUp) {
        shares = Math.floor(cash / price / 100) * 100;
        cash -= shares * price;
        entryPrice = price; entryIdx = i;
        trades.push({ date: bars[i].date, action: 'BUY', price, macdOsc: macd.osc[i] ? macd.osc[i].toFixed(4) : 'null' });
        state = 'in';
      }
    } else {
      // 卖出：价格跌破MA 或 MACD死叉
      const macdCrossDn = i > 0 && macd.dif[i-1] >= macd.dea[i-1] && macd.dif[i] < macd.dea[i];
      if (price < maMap[cfg.MAs[0]][i] || macdCrossDn) {
        cash += shares * price;
        trades.push({ date: bars[i].date, action: 'SELL', price, ret: (price/entryPrice-1)*100 });
        shares = 0; state = 'out';
      }
    }
  }
  if (state === 'in') { cash += shares * closes[closes.length-1]; trades.push({ date: bars[bars.length-1].date, action: 'SELL*', price: closes[closes.length-1], ret: (closes[closes.length-1]/entryPrice-1)*100 }); }

  return computeStats(trades, equity, bars, label, cfg);
}

function computeStats(trades, equity, bars, label, cfg) {
  if (equity.length < 20) return null;
  const rets = [];
  for (let i = 1; i < equity.length; i++) {
    rets.push((equity[i].nav - equity[i-1].nav) / equity[i-1].nav);
  }
  const avgRet = rets.reduce((a,b)=>a+b,0)/rets.length;
  const stdRet = Math.sqrt(rets.reduce((a,b)=>a+(b-avgRet)**2,0)/rets.length);
  const years = (new Date(bars[bars.length-1].date) - new Date(bars[0].date)) / 86400000 / 365.25;
  const annRet = (equity[equity.length-1].nav / INIT_CASH - 1) / years * 100;
  const sharpe = stdRet > 0 ? (avgRet / stdRet) * Math.sqrt(252) : 0;

  // 最大回撤
  let peak = INIT_CASH, maxDD = 0;
  for (const e of equity) { if(e.nav > peak) peak = e.nav; const dd = (peak - e.nav) / peak; if(dd > maxDD) maxDD = dd; }

  const buyHold = closes => closes[closes.length-1] / closes[0];
  const closes = bars.map(r => r.close);
  const bh = (closes[closes.length-1] / closes[0] - 1) * 100;
  const bhAnn = (Math.pow(closes[closes.length-1] / closes[0], 1/Math.max(years,0.01)) - 1) * 100;

  const winTrades = trades.filter(t => t.ret !== undefined && t.ret > 0);
  const sellTrades = trades.filter(t => t.action && t.action.startsWith('SELL'));
  const winRate = sellTrades.length > 0 ? winTrades.length / sellTrades.length * 100 : 0;
  const avgWin = winTrades.length > 0 ? winTrades.reduce((a,t)=>a+t.ret,0)/winTrades.length : 0;
  const avgLoss = sellTrades.filter(t => t.ret !== undefined && t.ret <= 0).reduce((a,t)=>a+t.ret,0) / Math.max(1, sellTrades.filter(t=>t.ret!==undefined&&t.ret<=0).length);

  return {
    label, years: years.toFixed(2),
    annRet: annRet.toFixed(1), sharpe: sharpe.toFixed(2), maxDD: (maxDD*100).toFixed(1),
    totalRet: (equity[equity.length-1].nav / INIT_CASH - 1) * 100,
    bhAnn: bhAnn.toFixed(1), bh: bh.toFixed(1),
    vsBH: (annRet - bhAnn).toFixed(1),
    winRate: winRate.toFixed(0), avgWin: avgWin.toFixed(1), avgLoss: avgLoss.toFixed(1),
    trades: trades.length, wins: winTrades.length,
    start: bars[0].date, end: bars[bars.length-1].date,
    finalNav: equity[equity.length-1].nav.toFixed(0),
  };
}

// ── 加载数据 ────────────────────────────────
function loadData(fp) {
  try {
    const raw = JSON.parse(fs.readFileSync(fp, 'utf8'));
    const r = raw.records || raw;
    return r.filter(x => x.close > 0 && x.date >= '2000-01-01').sort((a,b)=>a.date.localeCompare(b.date));
  } catch(e) { return null; }
}

// ── 策略配置 ───────────────────────────────
const STRATS = [
  { name: 'MA20+MACD',  MAs: [20],     maLookback: 5,  stopLoss: null, tsl: null,      tslDays: null },
  { name: 'MA10+MACD',  MAs: [10],     maLookback: 3,  stopLoss: null, tsl: null,      tslDays: null },
  { name: 'MA30+MACD',  MAs: [30],     maLookback: 5,  stopLoss: null, tsl: null,      tslDays: null },
  { name: 'MA10+20',    MAs: [10,20],  maLookback: 3,  stopLoss: null, tsl: null,      tslDays: null },
  { name: 'MA20+50',    MAs: [20,50],  maLookback: 5,  stopLoss: null, tsl: null,      tslDays: null },
  { name: 'MA10+MACD+SL5%', MAs: [10], maLookback: 3,  stopLoss: 0.05, tsl: null,      tslDays: null },
  { name: 'MA20+MACD+SL5%', MAs: [20], maLookback: 5,  stopLoss: 0.05, tsl: null,      tslDays: null },
];

// ── 数据集 ─────────────────────────────────
const DATASETS = [
  { label: '沪深300指数', fp: DATA + '/index_history/sh000300.json', start: '2005-04-08', end: '2026-04-24' },
  { label: '50ETF',       fp: DATA + '/history_long/sh510050.json',  start: '2018-05-30', end: '2026-04-24' },
  { label: '300ETF',      fp: DATA + '/history_long/sh510300.json',  start: '2018-05-30', end: '2026-04-24' },
  { label: '500ETF',      fp: DATA + '/history_long/sh510500.json',  start: '2018-05-30', end: '2026-04-24' },
  { label: '纳指ETF',     fp: DATA + '/history_long/sh513100.json',  start: '2018-05-30', end: '2026-04-24' },
  { label: '创业板ETF',    fp: DATA + '/history_long/sh159915.json',  start: '2018-05-30', end: '2026-04-24' },
];

console.log('═══════════════════════════════════════════════════════════════════════════════');
console.log('  综合回测：MA策略长周期 vs 短周期对比');
console.log('  时间: ' + new Date().toLocaleString());
console.log('═══════════════════════════════════════════════════════════════════════════════\n');

const allResults = [];

DATASETS.forEach(ds => {
  const records = loadData(ds.fp);
  if (!records) { console.log('❌ ' + ds.label + ' 数据加载失败'); return; }
  const filtered = records.filter(r => r.date >= ds.start && r.date <= ds.end);
  if (filtered.length < 60) { console.log('❌ ' + ds.label + ' 数据不足'); return; }
  console.log('📊 ' + ds.label + ': ' + filtered.length + ' bars, ' + ds.start + ' → ' + ds.end);
  console.log('   数据首日: ' + filtered[0].date + ' | 末: ' + filtered[filtered.length-1].date);

  STRATS.forEach(cfg => {
    const r = backtest(filtered, ds.label + ' | ' + cfg.name, cfg);
    if (r) {
      r.strat = cfg.name; r.dataset = ds.label;
      allResults.push(r);
      const beat = parseFloat(r.vsBH) >= 0 ? '✅' : '❌';
      console.log('  ' + beat + ' ' + cfg.name.padEnd(18) + ' 年化:' + r.annRet + '%  夏普:' + r.sharpe + '  回撤:' + r.maxDD + '%  胜率:' + r.winRate + '%  交易:' + r.trades + '  超额:' + r.vsBH + '%  BH年化:' + r.bhAnn + '%');
    }
  });
  console.log('');
});

// ── 汇总表 ─────────────────────────────────
console.log('═══════════════════════════════════════════════════════════════════════════════');
console.log('汇总对比（按夏普降序）');
console.log('');
console.log('数据集'.padEnd(14) + '策略'.padEnd(20) + '年化%'.padEnd(8) + '夏普'.padEnd(7) + '回撤%'.padEnd(8) + '胜率%'.padEnd(7) + '交易'.padEnd(6) + '超额%  | BH年化%');
console.log('-'.repeat(90));

const sorted = allResults.sort((a,b)=>parseFloat(b.sharpe)-parseFloat(a.sharpe));
sorted.forEach(r => {
  console.log(
    r.dataset.padEnd(14) + r.strat.padEnd(20) +
    r.annRet.padEnd(8) + r.sharpe.padEnd(7) + r.maxDD.padEnd(8) +
    r.winRate.padEnd(7) + r.trades.toString().padEnd(6) +
    (parseFloat(r.vsBH)>=0?'+':'') + r.vsBH + '%  | ' + r.bhAnn + '%'
  );
});

console.log('\n' + '='.repeat(90));
console.log('完成');

fs.writeFileSync('D:/QClaw_Trading/data/bt_comprehensive_result.json', JSON.stringify(sorted, null, 2));
