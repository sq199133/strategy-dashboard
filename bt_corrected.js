/**
 * bt_corrected.js - 修正后的MA策略综合回测
 * 关键修复：MACD金叉死叉判断逻辑正确、DIF/DEA使用真实数组
 */
const fs   = require('fs');
const INIT_CASH = 100000;
const DATA = 'D:/QClaw_Trading/data';

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
  // DEA种子 = 前slow日DIF简单均值（比dif[slow-1]更稳定）
  const k = 2 / (signal + 1);
  const dea = new Array(dif.length);
  let seed = 0; for (let i = 0; i < slow; i++) seed += dif[i]; seed /= slow;
  dea[slow - 1] = seed;
  for (let i = slow; i < dif.length; i++) dea[i] = dif[i] * k + dea[i-1] * (1-k);
  return { dif, dea };
}

function maDir(ma, idx, lookback) {
  if (idx < lookback || ma[idx] === null) return 'flat';
  const recent = ma.slice(Math.max(0, idx - lookback + 1), idx + 1).filter(v => v !== null);
  if (recent.length < 2) return 'flat';
  return recent[recent.length-1] > recent[0] ? 'up' : 'dn';
}

function backtest(bars, stratCfg, label) {
  if (!bars || bars.length < 60) return null;
  const closes = bars.map(r => r.close);
  const maMap = {};
  stratCfg.MAs.forEach(ma => { maMap[ma] = calcMA(closes, ma); });
  const macd = calcMACD(closes, 12, 26, 9);

  let cash = INIT_CASH, shares = 0, state = 'out', entryPrice = 0;
  const equity = [], trades = [];

  for (let i = 1; i < bars.length; i++) {
    const price = closes[i];
    equity.push({ date: bars[i].date, nav: cash + shares * price });

    if (state === 'in') {
      // 止损
      if (stratCfg.stopLoss && price / entryPrice - 1 < -stratCfg.stopLoss) {
        cash += shares * price;
        trades.push({ action: 'SELL_SL', date: bars[i].date, ret: (price/entryPrice-1)*100 });
        shares = 0; state = 'out'; continue;
      }
    }

    const primaryMA = maMap[stratCfg.MAs[0]][i];
    if (primaryMA === null) continue;

    if (state === 'out') {
      // 买入条件
      const macdUp = macd.dif[i] > 0 && macd.dif[i] > macd.dea[i] && macd.dif[i-1] <= macd.dea[i-1];
      const maUp = maDir(maMap[stratCfg.MAs[0]], i, stratCfg.maLookback) === 'up';
      let allUp = true;
      for (let m = 1; m < stratCfg.MAs.length; m++) {
        if (maDir(maMap[stratCfg.MAs[m]], i, stratCfg.maLookback) !== 'up') { allUp = false; break; }
      }
      if (price > primaryMA && maUp && allUp && macdUp) {
        shares = Math.floor(cash / price / 100) * 100;
        if (shares > 0) { cash -= shares * price; entryPrice = price; trades.push({ action: 'BUY', date: bars[i].date, price }); state = 'in'; }
      }
    } else {
      // 卖出：跌破MA 或 MACD死叉
      const macdDn = macd.dif[i] < macd.dea[i] && macd.dif[i-1] >= macd.dea[i-1];
      if (price < primaryMA || macdDn) {
        cash += shares * price;
        trades.push({ action: 'SELL', date: bars[i].date, ret: (price/entryPrice-1)*100 });
        shares = 0; state = 'out';
      }
    }
  }
  if (state === 'in') { cash += shares * closes[closes.length-1]; trades.push({ action: 'SELL*', date: bars[bars.length-1].date, ret: (closes[closes.length-1]/entryPrice-1)*100 }); }

  return computeStats(trades, equity, bars, label, stratCfg);
}

function computeStats(trades, equity, bars, label, stratCfg) {
  if (equity.length < 20) return null;
  const rets = [];
  for (let i = 1; i < equity.length; i++) rets.push((equity[i].nav - equity[i-1].nav) / equity[i-1].nav);
  const avgR = rets.reduce((a,b)=>a+b,0)/rets.length || 0;
  const stdR = Math.sqrt(rets.reduce((a,b)=>a+(b-avgR)**2,0)/rets.length) || 0;
  const years = (new Date(bars[bars.length-1].date) - new Date(bars[0].date)) / 86400000 / 365.25;
  const annRet = (equity[equity.length-1].nav / INIT_CASH - 1) / years * 100;
  const sharpe = stdR > 0 ? (avgR / stdR) * Math.sqrt(252) : 0;
  let peak = INIT_CASH, maxDD = 0;
  for (const e of equity) { if(e.nav > peak) peak = e.nav; const dd = (peak - e.nav) / peak; if(dd > maxDD) maxDD = dd; }
  const closes = bars.map(r => r.close);
  const bhAnn = (Math.pow(closes[closes.length-1]/closes[0], 1/Math.max(years,0.01)) - 1) * 100;
  const sellTrades = trades.filter(t => t.action && t.action.startsWith('SELL'));
  const wins = trades.filter(t => t.ret !== undefined && t.ret > 0);
  const winRate = sellTrades.length > 0 ? wins.length / sellTrades.length * 100 : 0;
  const avgWin = wins.length > 0 ? wins.reduce((a,t)=>a+t.ret,0)/wins.length : 0;
  const losses = sellTrades.filter(t => t.ret !== undefined && t.ret <= 0);
  const avgLoss = losses.length > 0 ? losses.reduce((a,t)=>a+t.ret,0)/losses.length : 0;
  return {
    label, strat: stratCfg.name,
    annRet: +annRet.toFixed(1), sharpe: +sharpe.toFixed(2), maxDD: +(maxDD*100).toFixed(1),
    totalRet: +((equity[equity.length-1].nav/INIT_CASH-1)*100).toFixed(1),
    bhAnn: +bhAnn.toFixed(1), vsBH: +(annRet - bhAnn).toFixed(1),
    winRate: +winRate.toFixed(0), avgWin: +avgWin.toFixed(1), avgLoss: +avgLoss.toFixed(1),
    trades: trades.length, wins: wins.length, years: +years.toFixed(2),
    start: bars[0].date, end: bars[bars.length-1].date,
    finalNav: equity[equity.length-1].nav.toFixed(0),
  };
}

function loadData(fp) {
  try {
    const raw = JSON.parse(fs.readFileSync(fp, 'utf8'));
    const r = (raw.records || raw).filter(x => x.close > 0 && x.date >= '2000-01-01').sort((a,b) => a.date.localeCompare(b.date));
    return r;
  } catch(e) { return null; }
}

const STRATS = [
  { name: 'MA20+MACD',      MAs: [20],    maLookback: 5,  stopLoss: null },
  { name: 'MA10+MACD',      MAs: [10],    maLookback: 3,  stopLoss: null },
  { name: 'MA20+50',        MAs: [20,50], maLookback: 5,  stopLoss: null },
  { name: 'MA10+20',        MAs: [10,20], maLookback: 3,  stopLoss: null },
  { name: 'MA20+MACD+SL5%', MAs: [20],    maLookback: 5,  stopLoss: 0.05 },
  { name: 'MA10+MACD+SL5%', MAs: [10],    maLookback: 3,  stopLoss: 0.05 },
];

const DATASETS = [
  { label: '沪深300[2005-]',   fp: DATA + '/index_history/sh000300.json',  start: '2005-04-08' },
  { label: '50ETF[2018-]',     fp: DATA + '/history_long/sh510050.json',   start: '2018-05-30' },
  { label: '300ETF[2018-]',   fp: DATA + '/history_long/sh510300.json',   start: '2018-05-30' },
  { label: '500ETF[2018-]',   fp: DATA + '/history_long/sh510500.json',   start: '2018-05-30' },
  { label: '纳指ETF[2018-]',  fp: DATA + '/history_long/sh513100.json',   start: '2018-05-30' },
];

console.log('═══════════════════════════════════════════════════════════════════════');
console.log('  综合回测 v2 - 修正MACD计算 + 真实DIF/DEA判断');
console.log('  ' + new Date().toLocaleString());
console.log('═══════════════════════════════════════════════════════════════════════\n');

const allResults = [];
DATASETS.forEach(ds => {
  const records = loadData(ds.fp);
  if (!records) { console.log('❌ 加载失败: ' + ds.label); return; }
  const bars = records.filter(r => r.date >= ds.start).sort((a,b) => a.date.localeCompare(b.date));
  console.log('📊 ' + ds.label + ': ' + bars.length + ' bars, ' + bars[0].date + ' → ' + bars[bars.length-1].date);
  STRATS.forEach(cfg => {
    const r = backtest(bars, cfg, ds.label);
    if (r) {
      allResults.push(r);
      const beat = r.vsBH >= 0 ? '✅' : '❌';
      console.log('  ' + beat + ' ' + cfg.name.padEnd(18) + ' 年化:' + r.annRet.toString().padStart(6) + '%  夏普:' + r.sharpe.toFixed(2) + '  回撤:' + r.maxDD.toString().padStart(5) + '%  胜率:' + r.winRate + '%  交易:' + r.trades + '笔  超额:' + (r.vsBH>=0?'+':'')+r.vsBH+'%  BH:' + r.bhAnn + '%');
    }
  });
  console.log('');
});

console.log('═══════════════════════════════════════════════════════════════════════');
console.log('汇总（按夏普降序）');
console.log('数据集'.padEnd(16) + '策略'.padEnd(20) + '年化%'.padEnd(8) + '夏普'.padEnd(7) + '回撤%'.padEnd(8) + '胜率%'.padEnd(7) + '交易'.padEnd(6) + '超额%  | BH%');
console.log('-'.repeat(90));
const sorted = allResults.sort((a,b) => b.sharpe - a.sharpe);
sorted.forEach(r => console.log(r.label.padEnd(16)+r.strat.padEnd(20)+r.annRet.toString().padEnd(8)+r.sharpe.toFixed(2).padEnd(7)+r.maxDD.toString().padEnd(8)+r.winRate.padEnd(7)+r.trades.toString().padEnd(6)+(r.vsBH>=0?'+':'')+r.vsBH+'%  | '+r.bhAnn));

console.log('\n='.repeat(90));
fs.writeFileSync(DATA + '/bt_corrected_result.json', JSON.stringify(sorted, null, 2));
console.log('结果已保存');
