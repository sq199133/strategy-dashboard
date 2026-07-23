// backtest_v1.js — MA20+MACD策略回测引擎 v1
// 目标：(1)测出当前策略基准夏普 (2)发现改进空间 (3)给出优化方案
'use strict';
var fs = require('fs');
var path = require('path');

var HIST_DIR = 'D:\\QClaw_Trading\\data\\history';
var POOL_FILE = 'D:\\QClaw_Trading\\scripts\\scan\\etf_pool.json';
var INITIAL_CAPITAL = 100000;
var SLIPPAGE = 0.001; // 0.1% 滑点

// ── 读取池 ───────────────────────────────────────────
var pool = JSON.parse(fs.readFileSync(POOL_FILE, 'utf8'));
var poolMap = {};
pool.forEach(function(e){ poolMap[e.code] = e; });

// ── 读取所有ETF历史数据 ───────────────────────────────
var etfData = {};
var files = fs.readdirSync(HIST_DIR).filter(function(f){ return f.endsWith('.json'); });
files.forEach(function(f){
  var code = f.replace('.json','');
  var d = JSON.parse(fs.readFileSync(path.join(HIST_DIR, f), 'utf8'));
  var r = d.records || [];
  if (r.length < 120) return; // 至少6个月数据
  // 过滤到2025-12-31
  r = r.filter(function(x){ return x.date <= '2025-12-31'; });
  // 按日期升序
  r.sort(function(a,b){ return a.date.localeCompare(b.date); });
  var pc = code.replace('sz','').replace('sh','');
  var info = poolMap[pc] || null;
  if (info && r.length >= 120) {
    etfData[code] = { info: info, records: r };
  }
});

console.log('=== 数据加载 ===');
console.log('ETF池: ' + pool.length + ' 只');
console.log('有足够数据: ' + Object.keys(etfData).length + ' 只');
console.log('');

// ── 指标函数 ─────────────────────────────────────────
function sma(prices, n) {
  var out = new Array(prices.length).fill(null);
  for (var i = n-1; i < prices.length; i++) {
    var s = 0;
    for (var j = i-n+1; j <= i; j++) s += prices[j];
    out[i] = s / n;
  }
  return out;
}

function ema(prices, n) {
  var k = 2/(n+1);
  var ef = [];
  ef[n-1] = prices.slice(0,n).reduce(function(a,b){return a+b;},0)/n;
  for (var i=n; i < prices.length; i++) ef[i] = prices[i]*k + ef[i-1]*(1-k);
  return new Array(n-1).fill(null).concat(ef.slice(n-1));
}

function macd(prices, f, s, sig) {
  f=f||12; s=s||26; sig=sig||9;
  var ef = ema(prices, f);
  var es = ema(prices, s);
  var dif = prices.map(function(v,i){ return ef[i]!==null && es[i]!==null ? ef[i]-es[i] : null; });
  var sk = 2/(sig+1);
  var se = [];
  var firstDif = null;
  for (var di=s-1; di<dif.length; di++) { if (dif[di]!==null){firstDif=dif[di];break;}}
  se[s-1] = firstDif;
  for (var si=s; si<dif.length; si++) {
    se[si] = dif[si]!==null ? dif[si]*sk + (se[si-1]||0)*(1-sk) : null;
  }
  var hist = dif.map(function(v,i){ return v!==null&&se[i]!==null ? v-se[i] : null; });
  return { dif:dif, sig:se, hist:hist };
}

// ── 单ETF回测 ────────────────────────────────────────
function backtestOne(records, params) {
  var MA_N = params.MA_N || 20;
  var MACD_F = params.MACD_F || 12;
  var MACD_S = params.MACD_S || 26;
  var MACD_SIG = params.MACD_SIG || 9;
  var STOP_PCT = params.STOP_PCT || 0.05;
  var REL_STR_REQUIRED = params.REL_STR_REQUIRED || false;
  var BENCH_CODE = params.BENCH_CODE || null;
  var BENCH_DATA = params.BENCH_DATA || null;
  var CORR_LIMIT = params.CORR_LIMIT || 1.0;
  var HOLD_MAX = params.HOLD_MAX || 5;
  var USE_TRAILING_STOP = params.USE_TRAILING_STOP || false;
  var TRAIL_ATR_N = params.TRAIL_ATR_N || 14;
  var VOL_FILTER = params.VOL_FILTER || false;
  var MAX_VOL = params.MAX_VOL || 1.0;
  var MIN_STARS = params.MIN_STARS || 0;
  var USE_MA50_FILTER = params.USE_MA50_FILTER || false;

  var closes = records.map(function(r){ return r.close; });
  var highs = records.map(function(r){ return r.high; });
  var lows = records.map(function(r){ return r.low; });
  var dates = records.map(function(r){ return r.date; });

  var ma20 = sma(closes, MA_N);
  var ma50 = USE_MA50_FILTER ? sma(closes, 50) : null;
  var macdObj = macd(closes, MACD_F, MACD_S, MACD_SIG);
  var dif = macdObj.dif;
  var sig = macdObj.sig;
  var hist = macdObj.hist;

  // ATR (for trailing stop)
  var atr = null;
  if (USE_TRAILING_STOP) {
    atr = new Array(TRAIL_ATR_N).fill(null);
    for (var i=TRAIL_ATR_N; i<closes.length; i++) {
      var tr = Math.max(highs[i]-lows[i], Math.abs(highs[i]-closes[i-1]), Math.abs(lows[i]-closes[i-1]));
      var s=0; for(var j=i-TRAIL_ATR_N+1;j<=i;j++) s+=tr; atr[i]=s/TRAIL_ATR_N;
    }
  }

  var trades = [];
  var position = null; // { entryPrice, entryDate, entryIdx, peakPrice }
  var capital = INITIAL_CAPITAL;
  var equity = INITIAL_CAPITAL;
  var dailyEquity = []; // 每日权益(用于计算夏普)
  var equityCurve = [];
  var periodReturns = [];

  for (var i = MA_N+2; i < closes.length; i++) {
    var date = dates[i];
    var price = closes[i];
    var ma20c = ma20[i];
    var ma20p1 = ma20[i-1];
    var ma20p2 = ma20[i-2];
    var ma50c = ma50 ? ma50[i] : price + 1;
    var ma50p1 = ma50 ? ma50[i-1] : price + 1;
    var d = dif[i], dP1 = dif[i-1];
    var s = sig[i], sP1 = sig[i-1];
    var h = hist[i], hP1 = hist[i-1];

    if (position) {
      // 更新峰值
      if (price > position.peakPrice) position.peakPrice = price;

      // 卖出信号
      var sell = false;
      var sellReason = '';

      // ① MA20跌破
      if (price < ma20c && ma20p1 >= ma20c) {
        sell = true; sellReason = 'MA20跌破';
      }
      // ② 5%硬止损
      else if ((position.entryPrice - price) / position.entryPrice >= STOP_PCT) {
        sell = true; sellReason = '止损' + ((position.entryPrice-price)/position.entryPrice*100).toFixed(1)+'%';
      }
      // ③ 追踪止损(可选)
      else if (USE_TRAILING_STOP && atr[i] !== null) {
        var trailLevel = position.peakPrice - 2 * atr[i];
        if (price < trailLevel && position.peakPrice > position.entryPrice * 1.02) {
          sell = true; sellReason = '追踪止损';
        }
      }

      if (sell) {
        var sellPrice = price * (1 - SLIPPAGE);
        var ret = (sellPrice - position.entryPrice) / position.entryPrice;
        capital = capital * (1 + ret);
        trades.push({
          entryDate: position.entryDate,
          exitDate: date,
          entryPrice: position.entryPrice,
          exitPrice: sellPrice,
          ret: ret,
          retPct: (ret*100).toFixed(2)+'%',
          reason: sellReason,
          holdingDays: i - position.entryIdx
        });
        position = null;
      }
    }

    if (!position && capital > 0) {
      // 买入信号
      var buy = false;

      // MACD金叉: dif从下穿过signal
      var goldX = dP1 !== null && sP1 !== null && dP1 <= sP1 && d > s;
      var macdAboveZero = d > 0 && s > 0;
      var histRed = h > 0;
      var aboveMa20 = price > ma20c;
      var ma20Up = ma20c > ma20p1;
      var ma20Above50 = USE_MA50_FILTER ? (ma50c !== null && ma20c > ma50c) : true;
      var ma50Above200 = false;

      // 基准相对强弱(如果提供了)
      var relOk = true;
      if (REL_STR_REQUIRED && BENCH_DATA && BENCH_DATA.length > i) {
        var bClose = BENCH_DATA[i];
        var b20 = BENCH_DATA[i] && closes[i-20] > 0 ?
          (bClose - BENCH_DATA[i-20]) / BENCH_DATA[i-20] : 0;
        var e20 = closes[i-20] > 0 ? (price - closes[i-20]) / closes[i-20] : 0;
        relOk = e20 > b20;
      }

      // 波动率过滤
      var volOk = true;
      if (VOL_FILTER && i >= 22) {
        var rets2 = [];
        for (var vi = i-20; vi < i; vi++) {
          if (closes[vi] > 0 && closes[vi-1] > 0)
            rets2.push((closes[vi]-closes[vi-1])/closes[vi-1]);
        }
        if (rets2.length > 5) {
          var mv = rets2.reduce(function(a,b){return a+b;},0)/rets2.length;
          var vs = rets2.reduce(function(a,b){return a+(b-mv)*(b-mv);},0)/rets2.length;
          var annVol = Math.sqrt(vs)*Math.sqrt(242);
          volOk = annVol < MAX_VOL;
        }
      }

      if (aboveMa20 && goldX && macdAboveZero && ma20Up && ma20Above50 && relOk && volOk) {
        buy = true;
      }

      if (buy) {
        position = { entryPrice: price*(1+SLIPPAGE), entryDate: date, entryIdx: i, peakPrice: price };
      }
    }

    // 记录每日权益
    var posValue = position ? capital * (price / position.entryPrice) : capital;
    equityCurve.push({ date: date, equity: posValue });
  }

  // 如果期末还有持仓，按最后价格结算
  if (position) {
    var lastPrice = closes[closes.length-1];
    var ret = (lastPrice - position.entryPrice) / position.entryPrice;
    capital = capital * (1 + ret);
    trades.push({
      entryDate: position.entryDate,
      exitDate: dates[closes.length-1],
      entryPrice: position.entryPrice,
      exitPrice: lastPrice,
      ret: ret,
      retPct: (ret*100).toFixed(2)+'%',
      reason: '期末平仓',
      holdingDays: closes.length - position.entryIdx
    });
    position = null;
  }

  // ── 计算指标 ──────────────────────────────────────
  var totalReturn = (capital - INITIAL_CAPITAL) / INITIAL_CAPITAL;
  var annualizedReturn = Math.pow(1 + totalReturn, 252 / closes.length) - 1;

  // 权益曲线计算
  var eqDates = equityCurve.map(function(x){ return x.date; });
  var eqValues = equityCurve.map(function(x){ return x.equity; });

  // 日收益率序列
  var dailyRets = [];
  for (var ri = 1; ri < eqValues.length; ri++) {
    dailyRets.push((eqValues[ri] - eqValues[ri-1]) / eqValues[ri-1]);
  }

  // 夏普比率 (假设无风险利率3%)
  var rf = 0.03 / 252;
  var meanRet = dailyRets.reduce(function(a,b){return a+b;},0) / dailyRets.length;
  var vol = Math.sqrt(dailyRets.reduce(function(a,b){return a+(b-meanRet)*(b-meanRet);},0)/dailyRets.length);
  var sharpe = vol > 0 ? (meanRet - rf) * Math.sqrt(252) / vol : 0;

  // 最大回撤
  var peak = INITIAL_CAPITAL;
  var maxDrawdown = 0;
  var maxDDDate = '';
  eqValues.forEach(function(v, idx){
    if (v > peak) peak = v;
    var dd = (peak - v) / peak;
    if (dd > maxDrawdown) { maxDrawdown = dd; maxDDDate = eqDates[idx]; }
  });

  // 胜率
  var wins = trades.filter(function(t){ return t.ret > 0; });
  var winRate = trades.length > 0 ? wins.length / trades.length : 0;

  // 平均盈亏
  var avgGain = wins.length > 0 ? wins.reduce(function(a,b){return a+b.ret;},0)/wins.length : 0;
  var losses = trades.filter(function(t){ return t.ret <= 0; });
  var avgLoss = losses.length > 0 ? Math.abs(losses.reduce(function(a,b){return a+b.ret;},0)/losses.length) : 0;
  var profitLossRatio = avgLoss > 0 ? avgGain / avgLoss : 0;

  return {
    totalReturn: totalReturn,
    annualizedReturn: annualizedReturn,
    sharpe: sharpe,
    maxDrawdown: maxDrawdown,
    maxDDDate: maxDDDate,
    winRate: winRate,
    profitLossRatio: profitLossRatio,
    trades: trades,
    tradeCount: trades.length,
    avgHoldingDays: trades.length > 0 ? trades.reduce(function(a,b){return a+b.holdingDays;},0)/trades.length : 0,
    equityCurve: equityCurve,
    eqValues: eqValues
  };
}

// ── 主程序 ─────────────────────────────────────────
console.log('=== 回测: MA20+MACD策略 v1 ===\n');

// 选择有足够数据的ETF (>=300条, 约1.2年)
var eligible = Object.keys(etfData).filter(function(code){
  return etfData[code].records.length >= 300;
});
console.log('符合条件ETF(' + eligible.length + '只, >=300条K线):');
eligible.forEach(function(code){
  var d = etfData[code];
  console.log('  ' + code + ' ' + d.info.name + ' ' + d.records.length + '条 ' +
    d.records[0].date + '~' + d.records[d.records.length-1].date);
});
console.log('');

// ── 场景定义 ───────────────────────────────────────
var scenarios = [
  {
    name: '基准: MA20+MACD金叉+5%止损',
    params: { MA_N:20, MACD_F:12, MACD_S:26, MACD_SIG:9, STOP_PCT:0.05, REL_STR_REQUIRED:false, CORR_LIMIT:1.0, HOLD_MAX:5, USE_TRAILING_STOP:false, VOL_FILTER:false, USE_MA50_FILTER:false, MIN_STARS:0 }
  },
  {
    name: 'S2: +MA50上方过滤',
    params: { MA_N:20, MACD_F:12, MACD_S:26, MACD_SIG:9, STOP_PCT:0.05, REL_STR_REQUIRED:false, CORR_LIMIT:1.0, HOLD_MAX:5, USE_TRAILING_STOP:false, VOL_FILTER:false, USE_MA50_FILTER:true, MIN_STARS:0 }
  },
  {
    name: 'S3: +ATR追踪止损(2ATR)',
    params: { MA_N:20, MACD_F:12, MACD_S:26, MACD_SIG:9, STOP_PCT:0.05, REL_STR_REQUIRED:false, CORR_LIMIT:1.0, HOLD_MAX:5, USE_TRAILING_STOP:true, TRAIL_ATR_N:14, VOL_FILTER:false, USE_MA50_FILTER:false, MIN_STARS:0 }
  },
  {
    name: 'S4: +波动率过滤(年化<50%)',
    params: { MA_N:20, MACD_F:12, MACD_S:26, MACD_SIG:9, STOP_PCT:0.05, REL_STR_REQUIRED:false, CORR_LIMIT:1.0, HOLD_MAX:5, USE_TRAILING_STOP:false, VOL_FILTER:true, MAX_VOL:0.50, USE_MA50_FILTER:false, MIN_STARS:0 }
  },
  {
    name: 'S5: S2+S3组合(MA50+ATR)',
    params: { MA_N:20, MACD_F:12, MACD_S:26, MACD_SIG:9, STOP_PCT:0.05, REL_STR_REQUIRED:false, CORR_LIMIT:1.0, HOLD_MAX:5, USE_TRAILING_STOP:true, TRAIL_ATR_N:14, VOL_FILTER:false, USE_MA50_FILTER:true, MIN_STARS:0 }
  },
  {
    name: 'S6: S4+波动率<40%',
    params: { MA_N:20, MACD_F:12, MACD_S:26, MACD_SIG:9, STOP_PCT:0.05, REL_STR_REQUIRED:false, CORR_LIMIT:1.0, HOLD_MAX:5, USE_TRAILING_STOP:false, VOL_FILTER:true, MAX_VOL:0.40, USE_MA50_FILTER:false, MIN_STARS:0 }
  },
  {
    name: 'S7: 激进止损3%+ATR',
    params: { MA_N:20, MACD_F:12, MACD_S:26, MACD_SIG:9, STOP_PCT:0.03, REL_STR_REQUIRED:false, CORR_LIMIT:1.0, HOLD_MAX:5, USE_TRAILING_STOP:true, TRAIL_ATR_N:10, VOL_FILTER:false, USE_MA50_FILTER:false, MIN_STARS:0 }
  },
  {
    name: 'S8: MA10短期(替代MA20)',
    params: { MA_N:10, MACD_F:8, MACD_S:17, MACD_SIG:9, STOP_PCT:0.05, REL_STR_REQUIRED:false, CORR_LIMIT:1.0, HOLD_MAX:5, USE_TRAILING_STOP:false, VOL_FILTER:false, USE_MA50_FILTER:false, MIN_STARS:0 }
  },
];

// ── 运行回测 ──────────────────────────────────────
var results = [];
scenarios.forEach(function(sc) {
  console.log('回测: ' + sc.name + ' ...');
  var scenarioResults = [];
  eligible.forEach(function(code) {
    var records = etfData[code].records;
    var r = backtestOne(records, sc.params);
    r.code = code;
    r.name = etfData[code].info.name;
    r.category = etfData[code].info.category;
    scenarioResults.push(r);
  });

  // 按夏普排序
  scenarioResults.sort(function(a,b){ return b.sharpe - a.sharpe; });

  // 汇总
  var totalSharpe = scenarioResults.reduce(function(a,b){return a+b.sharpe;},0)/scenarioResults.length;
  var totalRet = scenarioResults.reduce(function(a,b){return a+b.annualizedReturn;},0)/scenarioResults.length;
  var avgWinRate = scenarioResults.reduce(function(a,b){return a+b.winRate;},0)/scenarioResults.length;
  var avgMaxDD = scenarioResults.reduce(function(a,b){return a+b.maxDrawdown;},0)/scenarioResults.length;
  var totalTrades = scenarioResults.reduce(function(a,b){return a+b.tradeCount;},0);
  var bestOne = scenarioResults[0];
  var worstOne = scenarioResults[scenarioResults.length-1];

  results.push({
    scenario: sc.name,
    params: sc.params,
    avgSharpe: totalSharpe,
    avgAnnualReturn: totalRet,
    avgWinRate: avgWinRate,
    avgMaxDD: avgMaxDD,
    totalTrades: totalTrades,
    best: bestOne,
    worst: worstOne,
    all: scenarioResults
  });

  console.log('  → 平均夏普=' + totalSharpe.toFixed(3) +
    ' 年化=' + (totalRet*100).toFixed(1) + '%' +
    ' 胜率=' + (avgWinRate*100).toFixed(0) + '%' +
    ' 平均回撤=' + (avgMaxDD*100).toFixed(1) + '%' +
    ' 总交易=' + totalTrades);
});

// ── 输出汇总表格 ────────────────────────────────────
console.log('\n══════════════════════════════════════════════════════════');
console.log('  回测汇总 | ' + eligible.length + '只ETF | ' + '2023-11~2025-12');
console.log('══════════════════════════════════════════════════════════');
console.log('  场景               | 夏普  | 年化   | 胜率  | 回撤   | 交易数');
console.log('  ─────────────────────────────────────────────────────');
results.forEach(function(r){
  var star = r.avgSharpe >= 1.0 ? '★' : (r.avgSharpe >= 0.5 ? '☆' : ' ');
  console.log(' ' + star + ' ' + r.scenario.padEnd(22) + ' | ' +
    r.avgSharpe.toFixed(3) + ' | ' +
    (r.avgAnnualReturn*100).toFixed(1) + '%  | ' +
    (r.avgWinRate*100).toFixed(0) + '%  | ' +
    (r.avgMaxDD*100).toFixed(1) + '% | ' +
    r.totalTrades);
});
console.log('');

// ── 最佳场景详细 ────────────────────────────────────
results.sort(function(a,b){ return b.avgSharpe - a.avgSharpe; });
var best = results[0];
console.log('══════════════════════════════════════════════════════════');
console.log('  最佳场景: ' + best.scenario);
console.log('  夏普=' + best.avgSharpe.toFixed(3) + ' 年化=' + (best.avgAnnualReturn*100).toFixed(1) +
  '% 胜率=' + (best.avgWinRate*100).toFixed(0) + '% 平均回撤=' + (best.avgMaxDD*100).toFixed(1) + '%');
console.log('');
console.log('  Top5 ETF (按夏普):');
best.all.slice(0,5).forEach(function(r){
  console.log('    ' + r.code + ' ' + r.name.padEnd(12) +
    ' 夏普=' + r.sharpe.toFixed(3) +
    ' 年化=' + (r.annualizedReturn*100).toFixed(1) + '%' +
    ' 胜率=' + (r.winRate*100).toFixed(0) + '%' +
    ' 回撤=' + (r.maxDrawdown*100).toFixed(1) + '%' +
    ' 交易=' + r.tradeCount);
});
console.log('');
console.log('  最差5 ETF:');
best.all.slice(-5).forEach(function(r){
  console.log('    ' + r.code + ' ' + r.name.padEnd(12) +
    ' 夏普=' + r.sharpe.toFixed(3) +
    ' 年化=' + (r.annualizedReturn*100).toFixed(1) + '%' +
    ' 胜率=' + (r.winRate*100).toFixed(0) + '%' +
    ' 回撤=' + (r.maxDrawdown*100).toFixed(1) + '%' +
    ' 交易=' + r.tradeCount);
});

// ── 保存结果 ────────────────────────────────────────
var summary = results.map(function(r){
  return {
    scenario: r.scenario,
    avgSharpe: r.avgSharpe,
    avgAnnualReturn: r.avgAnnualReturn,
    avgWinRate: r.avgWinRate,
    avgMaxDD: r.avgMaxDD,
    totalTrades: r.totalTrades,
    topETF: r.all[0] ? {code:r.all[0].code, name:r.all[0].name, sharpe:r.all[0].sharpe} : null
  };
});
fs.writeFileSync('D:\\QClaw_Trading\\data\\backtest_results.json', JSON.stringify(summary, null, 2), 'utf8');
console.log('\n结果已保存: D:\\QClaw_Trading\\data\\backtest_results.json');
