// backtest_v2.js — MA20+MACD策略v2回测（加入均值回归+布林带+改进止损）
// 核心发现: 纯MA20+MACD夏普=-0.039(72ETF平均), 需要加入均值回归逻辑提升胜率
'use strict';
var fs = require('fs');
var path = require('path');

var HIST_DIR = 'D:\\QClaw_Trading\\data\\history';
var POOL_FILE = 'D:\\QClaw_Trading\\scripts\\scan\\etf_pool.json';
var INITIAL_CAPITAL = 100000;
var SLIPPAGE = 0.001;

// ── 数据加载 ──────────────────────────────────────
var pool = JSON.parse(fs.readFileSync(POOL_FILE, 'utf8'));
var poolMap = {};
pool.forEach(function(e){ poolMap[e.code] = e; });

var etfData = {};
fs.readdirSync(HIST_DIR).filter(function(f){ return f.endsWith('.json'); }).forEach(function(f){
  var code = f.replace('.json','');
  var d = JSON.parse(fs.readFileSync(path.join(HIST_DIR, f), 'utf8'));
  var r = (d.records || []).filter(function(x){ return x.date <= '2025-12-31'; });
  r.sort(function(a,b){ return a.date.localeCompare(b.date); });
  var pc = code.replace('sz','').replace('sh','');
  if (poolMap[pc] && r.length >= 300) etfData[code] = { info:poolMap[pc], records:r };
});

console.log('数据: ' + Object.keys(etfData).length + ' 只ETF\n');

// ── 指标 ─────────────────────────────────────────
function sma(arr,n){var o=new Array(arr.length).fill(null);for(var i=n-1;i<arr.length;i++){var s=0;for(var j=i-n+1;j<=i;j++)s+=arr[j];o[i]=s/n;}return o;}
function ema(arr,n){var k=2/(n+1),ef=[];ef[n-1]=arr.slice(0,n).reduce(function(a,b){return a+b;},0)/n;for(var i=n;i<arr.length;i++)ef[i]=arr[i]*k+ef[i-1]*(1-k);return new Array(n-1).fill(null).concat(ef.slice(n-1));}
function macd(arr,f,s,sig){
  f=f||12;s=s||26;sig=sig||9;
  var ef=ema(arr,f),es=ema(arr,s);
  var dif=arr.map(function(v,i){return ef[i]!==null&&es[i]!==null?ef[i]-es[i]:null;});
  var sk=2/(sig+1),se=[];var fd=null;for(var di=s-1;di<dif.length;di++){if(dif[di]!==null){fd=dif[di];break;}}
  se[s-1]=fd;
  for(var si=s;si<dif.length;si++)se[si]=dif[si]!==null?dif[si]*sk+(se[si-1]||0)*(1-sk):null;
  return{dif:dif,sig:se,hist:dif.map(function(v,i){return v!==null&&se[i]!==null?v-se[i]:null;})};
}

function rsi(arr, n) {
  var out = new Array(arr.length).fill(null);
  var gains = [], losses = [];
  for (var i = 1; i < arr.length; i++) {
    var ch = arr[i] - arr[i-1];
    gains.push(ch > 0 ? ch : 0);
    losses.push(ch < 0 ? -ch : 0);
  }
  for (var i = n; i < gains.length + 1; i++) {
    var sg = gains.slice(i-n, i).reduce(function(a,b){return a+b;}, 0) / n;
    var sl = losses.slice(i-n, i).reduce(function(a,b){return a+b;}, 0) / n;
    out[i] = sl === 0 ? 100 : 100 - 100 / (1 + sg / sl);
  }
  return out;
}

function calcBB(arr, n, k) {
  k = k || 2;
  var mid = sma(arr, n);
  var out = mid.map(function(m, i) {
    if (m === null) return { mid: null, upper: null, lower: null };
    var s = 0;
    for (var j = i-n+1; j <= i; j++) s += (arr[j]-m)*(arr[j]-m);
    var sd = Math.sqrt(s/n);
    return { mid: m, upper: m + k*sd, lower: m - k*sd };
  });
  return out;
}

// ── 单ETF回测核心 ────────────────────────────────
function backtest(records, cfg) {
  var closes = records.map(function(r){ return r.close; });
  var highs  = records.map(function(r){ return r.high; });
  var lows   = records.map(function(r){ return r.low; });
  var dates  = records.map(function(r){ return r.date; });
  var vols   = records.map(function(r){ return r.vol || 0; });

  var MA_N   = cfg.MA_N || 20;
  var MA50_N = cfg.MA50_N || 50;
  var MACD_F = cfg.MACD_F || 12;
  var MACD_S = cfg.MACD_S || 26;
  var MACD_SIG = cfg.MACD_SIG || 9;
  var RSI_N  = cfg.RSI_N || 14;
  var BB_N   = cfg.BB_N || 20;
  var STOP   = cfg.STOP_PCT || 0.05;
  var TRAIL_STOP_PCT = cfg.TRAIL_STOP_PCT || 0; // 追踪止损%
  var ENTRY_TYPE = cfg.ENTRY_TYPE || 'macd'; // 'macd'|'pullback'|'bollinger'|'hybrid'
  var RSI_OVERSOLD = cfg.RSI_OVERSOLD || 40;
  var RSI_ENTRY    = cfg.RSI_ENTRY || 50;
  var BB_ENTRY_PCT = cfg.BB_ENTRY_PCT || 0.5; // 距离布林下轨多少%内买入
  var VOL_MAX  = cfg.VOL_MAX || 999;
  var CORR_ENABLED = cfg.CORR_ENABLED || false;

  var ma20  = sma(closes, MA_N);
  var ma50  = sma(closes, MA50_N);
  var mcd   = macd(closes, MACD_F, MACD_S, MACD_SIG);
  var dif=mcd.dif, sig=mcd.sig, hist=mcd.hist;
  var rsi14 = rsi(closes, RSI_N);
  var bb20  = calcBB(closes, BB_N, 2);

  // ATR
  var atr = null;
  if (TRAIL_STOP_PCT > 0) {
    atr = new Array(closes.length).fill(null);
    for (var i=14; i<closes.length; i++) {
      var tr = Math.max(highs[i]-lows[i], Math.abs(highs[i]-closes[i-1]), Math.abs(lows[i]-closes[i-1]));
      var s=0; for(var j=i-13;j<=i;j++) s+=tr; atr[i]=s/14;
    }
  }

  var trades = [];
  var position = null;
  var capital = INITIAL_CAPITAL;
  var equityCurve = [];
  var eqValues = [];
  var eqDates = [];

  var startIdx = Math.max(MA_N+2, MA50_N+2, MACD_S+MACD_SIG+2, RSI_N+2, BB_N+2);

  for (var i = startIdx; i < closes.length; i++) {
    var date = dates[i];
    var price = closes[i];
    var ma20c = ma20[i], ma20p1 = ma20[i-1];
    var ma50c = ma50[i], ma50p1 = ma50[i-1];
    var dP1 = dif[i-1], dP2 = dif[i-2];
    var d = dif[i], s = sig[i], sP1 = sig[i-1];
    var h = hist[i];
    var rsiV = rsi14[i];
    var bb = bb20[i];
    var atrV = atr ? atr[i] : null;

    // ── 卖出 ──────────────────────────────────
    if (position) {
      var peak = position.peakPrice;
      if (price > peak) peak = price;
      position.peakPrice = peak;

      var sell = false, reason = '';
      // MA20跌破
      if (price < ma20c && ma20p1 >= ma20c) { sell=true; reason='MA20跌破'; }
      // 固定止损
      else if ((position.entryPrice - price)/position.entryPrice >= STOP) { sell=true; reason='止损'+(STOP*100).toFixed(0)+'%'; }
      // ATR追踪止损
      else if (TRAIL_STOP_PCT > 0 && atrV) {
        var trailLevel = peak - TRAIL_STOP_PCT * peak;
        if (price < trailLevel && peak/position.entryPrice > 1.03) { sell=true; reason='ATR追踪'; }
      }

      if (sell) {
        var sp = price*(1-SLIPPAGE);
        var ret = (sp-position.entryPrice)/position.entryPrice;
        capital = capital*(1+ret);
        trades.push({
          entryDate:position.entryDate, exitDate:date,
          entryPrice:position.entryPrice, exitPrice:sp,
          ret:ret, retPct:(ret*100).toFixed(1)+'%', reason:reason,
          holdingDays:i-position.entryIdx
        });
        position = null;
      }
    }

    // ── 买入 ───────────────────────────────────
    if (!position) {
      // 基本条件
      var aboveMa20  = price > ma20c;
      var ma20Up     = ma20c > ma20p1;
      var ma50Up     = ma50c > ma50p1;
      var ma20Above50 = ma20c > ma50c;
      var macdAboveZero = d>0 && s>0;
      var goldX = dP1!==null && sP1!==null && dP1<=sP1 && d>s; // MACD金叉
      var histRed = h>0;

      // 波动率过滤
      var volOk = true;
      if (i >= 22 && VOL_MAX < 10) {
        var rets2=[];
        for(var vi=i-20;vi<i;vi++)if(closes[vi]>0&&closes[vi-1]>0)rets2.push((closes[vi]-closes[vi-1])/closes[vi-1]);
        if(rets2.length>5){
          var mv=rets2.reduce(function(a,b){return a+b;},0)/rets2.length;
          var vs=rets2.reduce(function(a,b){return a+(b-mv)*(b-mv);},0)/rets2.length;
          volOk=Math.sqrt(vs)*Math.sqrt(242)<VOL_MAX;
        }
      }

      if (!volOk) { eqValues.push(capital); eqDates.push(date); continue; }

      var buy = false;

      if (ENTRY_TYPE === 'macd') {
        // 基准: MACD金叉 + MA20向上 + 零轴上
        if (aboveMa20 && goldX && macdAboveZero && ma20Up && histRed) buy = true;
      }
      else if (ENTRY_TYPE === 'pullback') {
        // ── v4.0核心改进: 回调入场 ──────────────
        // 前提: 在上涨趋势中(MA20向上)，价格回调到MA20附近时买入
        // 条件: MA20向上 + 价格从近期低点反弹超过3%但仍接近MA20 + RSI从低位回升
        // 替代: MACD绿色柱连续收缩 + 价格接近布林下轨

        // 条件1: 上涨趋势
        var inUptrend = ma20Up && ma20Above50;
        // 条件2: 价格从近期高点回调了一定幅度(避免追高)
        var recentHigh = Math.max.apply(null, closes.slice(Math.max(0,i-10), i+1));
        var pullback = (recentHigh - price)/recentHigh; // 回调幅度
        // 条件3: 价格回到MA20附近(距离<3%)
        var nearMA20 = (price - ma20c)/ma20c < 0.03;
        // 条件4: RSI从低位反弹(但还没过热)
        var rsiOk = rsiV !== null && rsiV > RSI_ENTRY && rsiV < 65;
        // 条件5: MACD柱状图开始收缩(空方力量减弱) 或 金叉
        var macdImproving = h > h-1 || goldX;
        // 条件6: 成交量放大(比10日均量>1.2倍)
        var vol10avg = vols.slice(Math.max(0,i-9),i+1).reduce(function(a,b){return a+b;},0)/10;
        var volUp = vols[i] > vol10avg * 1.2;

        if (inUptrend && pullback > 0.03 && pullback < 0.12 && nearMA20 && rsiOk && macdImproving && volUp) {
          buy = true;
        }
        // 备选: 如果没有完美回调但在强势趋势中突破布林中轨
        else if (inUptrend && ma20Up && macdAboveZero && bb && price > bb.mid * 0.98 && price < bb.mid * 1.01 && rsiV > 55) {
          buy = true;
        }
      }
      else if (ENTRY_TYPE === 'bollinger') {
        // 布林带RSI策略
        if (aboveMa20 && ma20Up && bb && price < bb.lower * (1+BB_ENTRY_PCT/100) && price > bb.lower * (1-BB_ENTRY_PCT/100) && rsiV > RSI_ENTRY) {
          buy = true;
        }
      }
      else if (ENTRY_TYPE === 'hybrid') {
        // ── v4.0混合策略: 趋势+均值回归 ─────────
        // 必须: MA20向上 + 价格高于MA20
        // 优先: 回调入场(MA20上方3%以内买入)
        // 替代: 金叉确认后追入(但只有零轴上金叉)
        // 过滤: RSI<70(避免过热) + 波动率过滤

        var vol10v = vols.slice(Math.max(0,i-9),i+1).reduce(function(a,b){return a+b;},0)/10;
        var volOk2 = vols[i] > vol10v * 0.8; // 量能不过度萎缩

        // 首选: 回调到MA20附近(2%以内)
        var atMA20 = Math.abs(price - ma20c) / ma20c < 0.02;
        var pullPct = (Math.max.apply(null, closes.slice(Math.max(0,i-8), i+1)) - price) / Math.max.apply(null, closes.slice(Math.max(0,i-8), i+1));
        var isPullback = pullPct > 0.02; // 有一定回调

        // 条件A: 回调入场(高质量)
        if (aboveMa20 && ma20Up && atMA20 && isPullback && rsiV > RSI_ENTRY && rsiV < 68 && volOk2 && macdAboveZero && histRed) {
          buy = true;
        }
        // 条件B: MACD零轴上金叉确认(次选)
        else if (aboveMa20 && ma20Up && macdAboveZero && goldX && rsiV < 72 && volOk2 && pullPct < 0.08) {
          buy = true;
        }
        // 条件C: 强势趋势中RSI从40以下反弹到50以上(布林下轨支撑)
        else if (aboveMa20 && ma20Up && ma20Above50 && rsiV > RSI_ENTRY && rsiV < 65 && bb && price < bb.lower * 1.03 && volOk2) {
          buy = true;
        }
      }

      if (buy) {
        position = { entryPrice: price*(1+SLIPPAGE), entryDate: date, entryIdx: i, peakPrice: price };
      }
    }

    eqValues.push(position ? capital * (price/position.entryPrice) : capital);
    eqDates.push(date);
  }

  // 期末平仓
  if (position) {
    var lp = closes[closes.length-1]*(1-SLIPPAGE);
    var ret=(lp-position.entryPrice)/position.entryPrice;
    capital = capital*(1+ret);
    trades.push({entryDate:position.entryDate,exitDate:dates[closes.length-1],entryPrice:position.entryPrice,exitPrice:lp,ret:ret,retPct:(ret*100).toFixed(1)+'%',reason:'期末平仓',holdingDays:closes.length-position.entryIdx});
  }

  // 统计
  var wins=trades.filter(function(t){return t.ret>0;});
  var losses=trades.filter(function(t){return t.ret<=0;});
  var wr=trades.length>0?wins.length/trades.length:0;
  var avgG=wins.length>0?wins.reduce(function(a,b){return a+b.ret;},0)/wins.length:0;
  var avgL=losses.length>0?Math.abs(losses.reduce(function(a,b){return a+b.ret;},0)/losses.length):0;
  var plRatio=avgL>0?avgG/avgL:0;
  var totalRet=(capital-INITIAL_CAPITAL)/INITIAL_CAPITAL;
  var annRet=Math.pow(1+totalRet,252/closes.length)-1;

  var dailyRets=[];
  for(var ri=1;ri<eqValues.length;ri++)dailyRets.push((eqValues[ri]-eqValues[ri-1])/eqValues[ri-1]);
  var meanR=dailyRets.reduce(function(a,b){return a+b;},0)/Math.max(dailyRets.length,1);
  var vol=Math.sqrt(dailyRets.reduce(function(a,b){return a+(b-meanR)*(b-meanR);},0)/Math.max(dailyRets.length,1));
  var sharpe=vol>0?(meanR-0.03/252)*Math.sqrt(252)/vol:0;

  var peak=INITIAL_CAPITAL,maxDD=0,maxDDDate='';
  eqValues.forEach(function(v,idx){
    if(v>peak)peak=v;
    var dd=(peak-v)/peak;
    if(dd>maxDD){maxDD=dd;maxDDDate=eqDates[idx];}
  });

  var avgHold=trades.length>0?trades.reduce(function(a,b){return a+b.holdingDays;},0)/trades.length:0;

  return {
    totalRet:totalRet, annRet:annRet, sharpe:sharpe, maxDD:maxDD, maxDDDate:maxDDDate,
    winRate:wr, profitLossRatio:plRatio, trades:trades, tradeCount:trades.length,
    avgHoldingDays:avgHold, eqValues:eqValues, eqDates:eqDates
  };
}

// ── 主程序 ─────────────────────────────────────
var eligible = Object.keys(etfData);
console.log('测试ETF: ' + eligible.length + '只\n');

// ── 场景定义 ──────────────────────────────────
var scenarios = [
  // 原始基准
  {name:'V1基准 MA20+MACD金叉',   cfg:{ENTRY_TYPE:'macd',    MA_N:20, STOP_PCT:0.05, VOL_MAX:999}},
  // 回调入场(新核心)
  {name:'V2 回调入场(MA20+RSI反弹)',cfg:{ENTRY_TYPE:'pullback',MA_N:20, RSI_ENTRY:50, RSI_OVERSOLD:40, STOP_PCT:0.05, VOL_MAX:999}},
  // 布林带策略
  {name:'V3 布林带RSI策略',         cfg:{ENTRY_TYPE:'bollinger',RSI_ENTRY:50,BB_ENTRY_PCT:1,STOP_PCT:0.05,MA_N:20,VOL_MAX:999}},
  // 混合策略
  {name:'V4 混合策略(趋势+均值)',    cfg:{ENTRY_TYPE:'hybrid',  MA_N:20, RSI_ENTRY:50, STOP_PCT:0.05, VOL_MAX:999}},
  // V4+波动率过滤
  {name:'V5 V4+波动率<50%',         cfg:{ENTRY_TYPE:'hybrid',  MA_N:20, RSI_ENTRY:50, STOP_PCT:0.05, VOL_MAX:0.50}},
  {name:'V6 V4+波动率<40%',         cfg:{ENTRY_TYPE:'hybrid',  MA_N:20, RSI_ENTRY:50, STOP_PCT:0.05, VOL_MAX:0.40}},
  {name:'V7 V4+波动率<35%',         cfg:{ENTRY_TYPE:'hybrid',  MA_N:20, RSI_ENTRY:50, STOP_PCT:0.05, VOL_MAX:0.35}},
  // V4+ATR追踪止损
  {name:'V8 V4+ATR追踪止损10%',     cfg:{ENTRY_TYPE:'hybrid',  MA_N:20, RSI_ENTRY:50, STOP_PCT:0.03, TRAIL_STOP_PCT:0.10, VOL_MAX:999}},
  {name:'V9 V4+ATR追踪止损15%',      cfg:{ENTRY_TYPE:'hybrid',  MA_N:20, RSI_ENTRY:50, STOP_PCT:0.03, TRAIL_STOP_PCT:0.15, VOL_MAX:999}},
  // V4+更严格止损
  {name:'V10 V4+激进止损3%',        cfg:{ENTRY_TYPE:'hybrid',  MA_N:20, RSI_ENTRY:55, STOP_PCT:0.03, VOL_MAX:999}},
  {name:'V11 V4+激进止损2%',        cfg:{ENTRY_TYPE:'hybrid',  MA_N:20, RSI_ENTRY:55, STOP_PCT:0.02, VOL_MAX:999}},
  // V4参数调优
  {name:'V12 V4+RSI55过滤',         cfg:{ENTRY_TYPE:'hybrid',  MA_N:20, RSI_ENTRY:55, STOP_PCT:0.05, VOL_MAX:999}},
  {name:'V13 V4+RSI60过滤',         cfg:{ENTRY_TYPE:'hybrid',  MA_N:20, RSI_ENTRY:60, STOP_PCT:0.05, VOL_MAX:999}},
  // MA50组合
  {name:'V14 V4+MA50过滤',          cfg:{ENTRY_TYPE:'hybrid',  MA_N:20, MA50_N:50, RSI_ENTRY:50, STOP_PCT:0.05, VOL_MAX:999}},
  {name:'V15 V14+波动率<40%',        cfg:{ENTRY_TYPE:'hybrid',  MA_N:20, MA50_N:50, RSI_ENTRY:50, STOP_PCT:0.05, VOL_MAX:0.40}},
  // 最优组合
  {name:'V16 最优:V4+MA50+ATR15+Vol40',cfg:{ENTRY_TYPE:'hybrid',MA_N:20,MA50_N:50,RSI_ENTRY:55,STOP_PCT:0.03,TRAIL_STOP_PCT:0.15,VOL_MAX:0.40}},
  // MA20替代
  {name:'V17 V4(MA15替代MA20)',     cfg:{ENTRY_TYPE:'hybrid',  MA_N:15, RSI_ENTRY:50, STOP_PCT:0.05, VOL_MAX:999}},
  {name:'V18 V4(MA25替代MA20)',      cfg:{ENTRY_TYPE:'hybrid',  MA_N:25, RSI_ENTRY:50, STOP_PCT:0.05, VOL_MAX:999}},
];

var results = [];
scenarios.forEach(function(sc){
  var scenarioResults = eligible.map(function(code){
    return Object.assign({code:code, name:etfData[code].info.name, category:etfData[code].info.category}, backtest(etfData[code].records, sc.cfg));
  });
  scenarioResults.sort(function(a,b){return b.sharpe-a.sharpe;});

  var avgShar = scenarioResults.reduce(function(a,b){return a+b.sharpe;},0)/scenarioResults.length;
  var avgRet  = scenarioResults.reduce(function(a,b){return a+b.annRet;},0)/scenarioResults.length;
  var avgWR   = scenarioResults.reduce(function(a,b){return a+b.winRate;},0)/scenarioResults.length;
  var avgDD   = scenarioResults.reduce(function(a,b){return a+b.maxDD;},0)/scenarioResults.length;
  var totalTrades = scenarioResults.reduce(function(a,b){return a+b.tradeCount;},0);

  results.push({
    name: sc.name,
    avgSharpe: avgShar,
    avgAnnRet: avgRet,
    avgWinRate: avgWR,
    avgMaxDD: avgDD,
    totalTrades: totalTrades,
    topETF: scenarioResults[0],
    worstETF: scenarioResults[scenarioResults.length-1],
    all: scenarioResults
  });

  var star = avgShar >= 1.0 ? '★★' : avgShar >= 0.5 ? '★' : avgShar >= 0 ? '☆' : '  ';
  console.log(star + ' ' + sc.name.padEnd(30) + ' 夏普=' + avgShar.toFixed(3) + ' 年化=' + (avgRet*100).toFixed(1) + '%' + ' 胜率=' + (avgWR*100).toFixed(0) + '%' + ' 回撤=' + (avgDD*100).toFixed(1) + '%' + ' 交易=' + totalTrades);
});

// 排序输出
console.log('\n══════════════════════════════════════════════════════════');
console.log('  回测汇总排名（' + eligible.length + '只ETF）');
console.log('══════════════════════════════════════════════════════════');
results.sort(function(a,b){return b.avgSharpe-a.avgSharpe;});
results.forEach(function(r,i){
  var star = r.avgSharpe >= 1.0 ? '★★' : r.avgSharpe >= 0.5 ? '★ ' : r.avgSharpe >= 0 ? '☆ ' : '  ';
  console.log((i+1) + '. ' + star + r.name.padEnd(32) + ' | 夏普=' + r.avgSharpe.toFixed(3) + ' | 年化=' + (r.avgAnnRet*100).toFixed(1) + '% | 胜=' + (r.avgWinRate*100).toFixed(0) + '% | DD=' + (r.avgMaxDD*100).toFixed(1) + '%');
});

// 最佳场景Top3
console.log('\n══════════════════════════════════════════════════════════');
console.log('  最佳场景: ' + results[0].name);
console.log('  夏普=' + results[0].avgSharpe.toFixed(3) + ' 年化=' + (results[0].avgAnnRet*100).toFixed(1) + '% 胜率=' + (results[0].avgWinRate*100).toFixed(0) + '% 回撤=' + (results[0].avgMaxDD*100).toFixed(1) + '%');
console.log('\n  Top5 ETF:');
results[0].all.slice(0,5).forEach(function(r){
  console.log('    ' + r.code + ' ' + r.name.padEnd(12) + ' 夏普=' + r.sharpe.toFixed(3) + ' 年化=' + (r.annRet*100).toFixed(1) + '% 胜=' + (r.winRate*100).toFixed(0) + '% DD=' + (r.maxDD*100).toFixed(1) + '% 交易=' + r.tradeCount);
});
console.log('\n  最差Top3:');
results[0].all.slice(-3).forEach(function(r){
  console.log('    ' + r.code + ' ' + r.name.padEnd(12) + ' 夏普=' + r.sharpe.toFixed(3) + ' 年化=' + (r.annRet*100).toFixed(1) + '% 胜=' + (r.winRate*100).toFixed(0) + '% DD=' + (r.maxDD*100).toFixed(1) + '% 交易=' + r.tradeCount);
});

// 保存
fs.writeFileSync('D:\\QClaw_Trading\\data\\backtest_v2_results.json', JSON.stringify(results.map(function(r){
  return {name:r.name, avgSharpe:r.avgSharpe, avgAnnRet:r.avgAnnRet, avgWinRate:r.avgWinRate, avgMaxDD:r.avgMaxDD, totalTrades:r.totalTrades,
    topETF:r.topETF?{code:r.topETF.code,name:r.topETF.name,sharpe:r.topETF.sharpe,annRet:r.topETF.annRet,winRate:r.topETF.winRate,maxDD:r.topETF.maxDD}:null};
}),null,2),'utf8');
console.log('\n结果已保存');
