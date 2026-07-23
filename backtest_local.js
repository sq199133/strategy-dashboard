/**
 * backtest_local.js - 基于本地历史数据的回测脚本
 * 
 * 数据：require('./data/history/sh159338.json') 等
 * 无需网络调用，回测瞬间完成
 * 
 * 使用方法：
 *   node backtest_local.js                    # 回测全部有本地数据的ETF
 *   node backtest_local.js 159338 510300     # 只回测指定ETF
 *   node backtest_local.js 159338 510300 2020-01-01 2025-12-31  # 指定时间范围
 */

const fs   = require('fs');
const path = require('path');

// ── 读取本地K线数据 ──────────────────────────
function loadLocal(code, market) {
  var fn = (market || 'sh').toLowerCase() + code + '.json';
  var fp = path.join(__dirname, 'data', 'history', fn);
  if (!fs.existsSync(fp)) return null;
  try {
    var raw = require(fp);
    return raw.records || [];
  } catch(e) { return null; }
}

// ── 指标计算（复用MA20+MACD核心逻辑）────────
function calcMA(closes, period) {
  var result = [];
  for (var i = 0; i < closes.length; i++) {
    if (i < period - 1) { result.push(null); continue; }
    var sum = 0;
    for (var j = 0; j < period; j++) sum += closes[i - j];
    result.push(sum / period);
  }
  return result;
}

function calcMACD(closes, fast, slow, signal) {
  var ema = function(data, p) {
    var k = 2 / (p + 1);
    var e = [data[0]];
    for (var i = 1; i < data.length; i++) e.push(data[i] * k + e[i-1] * (1-k));
    return e;
  };
  var ef = ema(closes, fast);           // 12日EMA
  var es = ema(closes, slow);            // 26日EMA
  var dif = ef.map(function(v, i){ return v - es[i]; }); // DIF

  // DEA（Signal线）：26日EMA of DIF
  // 种子：dea[slow-1] = dif[slow-1]（与扫描脚本完全一致）
  var k = 2 / (signal + 1);
  var dea = new Array(dif.length).fill(null);
  dea[slow - 1] = dif[slow - 1];  // 种子值
  for (var i = slow; i < dif.length; i++) {
    dea[i] = dif[i] * k + dea[i-1] * (1 - k);
  }

  // 柱 = DIF - DEA（与扫描脚本一致）
  var osc = dif.map(function(v, i){ return dea[i] !== null ? v - dea[i] : null; });
  return { dif: dif, dea: dea, osc: osc };
}

// ── MA方向 ──────────────────────────────────
function maDirection(ma, index, lookback) {
  if (index < lookback) return 'flat';
  var recent = ma.slice(Math.max(0, index - lookback + 1), index + 1).filter(function(v){ return v !== null; });
  if (recent.length < 2) return 'flat';
  return recent[recent.length-1] > recent[0] ? 'up' : 'dn';
}

// ── 回测单只ETF ─────────────────────────────
function backtestOne(records, label, startDate, endDate) {
  if (!records || records.length < 60) return null;

  // 过滤日期范围
  var bars = records.filter(function(r){ return r.date >= startDate && r.date <= endDate; });
  if (bars.length < 60) return null;

  var closes = bars.map(function(r){ return r.close; });
  var ma20   = calcMA(closes, 20);
  var macd   = calcMACD(closes, 12, 26, 9);

  var cash   = 100000;
  var shares = 0;
  var trades = [];
  var equity = [];
  var state  = 'out'; // 'out' | 'in'
  var entryPrice = 0;

  for (var i = 21; i < bars.length; i++) {
    var price  = closes[i];
    var ma     = ma20[i];
    var dif    = macd.dif[i];
    var dea    = macd.dea[i];
    var osc    = macd.osc[i];
    var maUp   = maDirection(ma20, i, 5) === 'up';

    // 买入信号
    if (state === 'out') {
      var crossUp = i > 0 && macd.dif[i-1] < macd.dea[i-1] && dif > dea && dif > 0;
      if (price > ma && maUp && crossUp) {
        shares = Math.floor(cash / price / 100) * 100;
        cash  -= shares * price;
        entryPrice = price;
        trades.push({ date: bars[i].date, action: 'BUY', price: price, shares: shares, cash: cash });
        state = 'in';
      }
    }
    // 卖出信号
    else if (state === 'in') {
      var crossDn = i > 0 && macd.dif[i-1] >= macd.dea[i-1] && dif < dea;
      if (price < ma || crossDn) {
        cash += shares * price;
        trades.push({ date: bars[i].date, action: 'SELL', price: price, shares: shares, cash: cash, ret: (price/entryPrice-1)*100 });
        shares = 0;
        state = 'out';
      }
    }

    // 记录当日净值
    var nav = cash + shares * price;
    equity.push({ date: bars[i].date, nav: nav });
  }

  // 最终强制平仓
  if (state === 'in') {
    var lastPrice = closes[closes.length-1];
    cash += shares * lastPrice;
    trades.push({ date: bars[bars.length-1].date, action: 'SELL*', price: lastPrice, shares: shares, cash: cash });
  }

  var finalNav  = cash;
  var buyHold   = bars.length > 0 ? closes[closes.length-1] / closes[0] : 1;
  var totalRet  = (finalNav / 100000 - 1) * 100;
  var buyHoldPct= (buyHold - 1) * 100;
  var winTrades = trades.filter(function(t){ return t.action === 'SELL' && t.ret > 0; });
  var years     = (new Date(endDate) - new Date(startDate)) / 365.25 / 86400000;

  return {
    label:    label,
    bars:     bars.length,
    start:    bars[0].date,
    end:      bars[bars.length-1].date,
    trades:   trades.length,
    wins:     winTrades.length,
    totalRet: totalRet.toFixed(1) + '%',
    buyHold:  buyHoldPct.toFixed(1) + '%',
    annualized: years > 0 ? ((Math.pow(finalNav/100000, 1/years))-1)*100 : 0,
    vsBH:     (totalRet - buyHoldPct).toFixed(1) + '%',
    finalNav: finalNav.toFixed(0),
    trades_detail: trades
  };
}

// ── 入口 ────────────────────────────────────
var pool   = require('./data/etf_pool.js');
// 参数格式: node backtest_local.js [code1 code2...] [startDate endDate]
// 日期格式: YYYY-MM-DD（包含-），其余视为ETF代码
var args = process.argv.slice(2);
var codes  = args.filter(function(a){ return /^\d{6}$/.test(a); });
var dates  = args.filter(function(a){ return /^\d{4}-\d{2}-\d{2}$/.test(a); });
var startD = dates[0] || '2018-01-01';
var endD   = dates[1] || '2025-12-31';
var targets = codes.length > 0
  ? pool.filter(function(e){ return codes.indexOf(e.code) >= 0; })
  : pool;

console.log('═══════════════════════════════════════════════════════');
console.log('  本地历史K线回测  |  MA20+MACD共振策略');
console.log('  范围: ' + startD + ' → ' + endD);
console.log('  目标: ' + targets.length + ' 只ETF');
console.log('═══════════════════════════════════════════════════════\n');

var results = [];
targets.forEach(function(etf){
  var records = loadLocal(etf.code, etf.market);
  if (!records || records.length === 0) {
    console.log('⏭  ' + etf.code + ' ' + etf.name + '  无本地数据');
    return;
  }
  var r = backtestOne(records, etf.code + ' ' + etf.name + ' [' + etf.category + ']', startD, endD);
  if (!r) {
    console.log('⏭  ' + etf.code + ' ' + etf.name + '  数据不足(' + records.length + '条)');
    return;
  }
  results.push(r);
  var beat = parseFloat(r.vsBH) >= 0 ? '✅' : '❌';
  console.log(beat + ' ' + r.label.padEnd(40) + ' 总收益:' + r.totalRet.padStart(8) + '  买入持有:' + r.buyHold.padStart(8) + '  超额:' + r.vsBH.padStart(7) + '  年化:' + r.annualized.toFixed(1) + '%  交易:' + r.trades + '笔  胜率:' + (r.trades>0?(r.wins/r.trades*100).toFixed(0)+'%':'N/A'));
});

console.log('\n' + '='.repeat(70));
console.log('回测完成: ' + results.length + ' 只ETF');

// 排序：按年化收益
results.sort(function(a,b){ return b.annualized - a.annualized; });

var top5 = results.slice(0,5);
console.log('\n🏆 TOP5（年化收益）:');
top5.forEach(function(r, i){
  console.log('  ' + (i+1) + '. ' + r.label + '  年化:' + r.annualized.toFixed(1) + '%  总收益:' + r.totalRet + '  超额:' + r.vsBH + '  交易:' + r.trades + '笔');
});

var wins = results.filter(function(r){ return parseFloat(r.vsBH) >= 0; });
console.log('\n跑赢买入持有: ' + wins.length + '/' + results.length + ' (' + (wins.length/results.length*100).toFixed(0) + '%)');
