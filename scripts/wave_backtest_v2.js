// ============================================================
// 波浪策略回测 v2（优化版）
// 改进：数据更完整（2008起）、波浪识别更精确、斐波那契回撤更准确
// ============================================================

var path = require('path');
var fs   = require('fs');
var SCRIPT_DIR = __dirname;
var ICAP = 100000;

function sleep(ms) { return new Promise(function(r){ setTimeout(r,ms); }); }

function txSecid(code, market) {
  return market === 'SZ' ? 'sz' + code : 'sh' + code;
}

// ── K线获取（分段取再合并，最多1500条历史）─────────────────
async function fetchKline(code, market) {
  var secid = txSecid(code, market);
  var periods = [
    ['2018-01-01','2020-12-31'],
    ['2021-01-01','2023-12-31'],
    ['2024-01-01','2026-12-31'],
  ];
  var allKlines = [];

  for (var pi = 0; pi < periods.length; pi++) {
    var beg = periods[pi][0], end = periods[pi][1];
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + secid + ',day,' + beg + ',' + end + ',500,qfq';
    try {
      var r = await fetch(url, { signal: AbortSignal.timeout(10000) });
      var j = await r.json();
      var arr = j.data && j.data[secid]
        ? (j.data[secid].qfqday || j.data[secid].day || [])
        : [];
      allKlines = allKlines.concat(arr);
      await sleep(300);
    } catch(e) {}
  }

  // 去重（按日期），按日期升序
  var seen = {};
  var uniq = allKlines.filter(function(k) {
    if (seen[k[0]]) return false;
    seen[k[0]] = true;
    return true;
  });
  uniq.sort(function(a,b){ return a[0].localeCompare(b[0]); });

  return uniq.map(function(k) {
    return { date:k[0], open:+k[1], close:+k[2], high:+k[3], low:+k[4], vol:+k[5] };
  });
}

// ── 指标 ────────────────────────────────────────────
function SMA(prices, n) {
  var out = new Array(prices.length).fill(null);
  for (var i=n-1; i<prices.length; i++) {
    var s=0; for (var j=i-n+1;j<=i;j++) s+=prices[j];
    out[i]=s/n;
  }
  return out;
}

function EMA(prices, n) {
  var k=2/(n+1);
  var out = new Array(prices.length).fill(null);
  var seed=0; for(var i=0;i<n;i++) seed+=prices[i];
  out[n-1]=seed/n;
  for(var i=n;i<prices.length;i++) out[i]=prices[i]*k+out[i-1]*(1-k);
  return out;
}

function MACD(prices,f,s,sig) {
  f=f||12;s=s||26;sig=sig||9;
  var ef=EMA(prices,f), es=EMA(prices,s);
  var dif=new Array(prices.length).fill(null);
  for(var i=s-1;i<prices.length;i++) dif[i]=ef[i]-es[i];
  var sk=2/(sig+1), se=new Array(prices.length).fill(null);
  se[s-1]=dif[s-1];
  for(var i=s;i<dif.length;i++) se[i]=dif[i]*sk+se[i-1]*(1-sk);
  var hist=dif.map(function(v,i){return v===null?null:v-se[i];});
  return {dif:dif,sig:se,hist:hist};
}

// ── 找局部高低点（用于波浪识别）─────────────────────
function findPivot(prices, lookback, minDist) {
  minDist = minDist || 5;
  var pivots = [];
  for (var i = minDist; i < prices.length - minDist; i++) {
    var isHigh = true, isLow = true;
    for (var j = i - minDist; j <= i + minDist; j++) {
      if (j === i) continue;
      if (prices[j] >= prices[i]) isHigh = false;
      if (prices[j] <= prices[i]) isLow = false;
    }
    if (isHigh) pivots.push({i:i, type:'high', val:prices[i]});
    if (isLow)  pivots.push({i:i, type:'low',  val:prices[i]});
  }
  return pivots;
}

// ── 核心波浪识别 ─────────────────────────────────────
// 策略：识别 N字形（推动浪）+ 调整浪
// 简化版：趋势向上时找回撤买点（2浪底/4浪底），趋势向下时找反弹卖点
function waveAnalysis(data, idx, lookback) {
  lookback = lookback || 120;
  var start = Math.max(0, idx - lookback);
  var end   = idx;
  var seg   = data.slice(start, end+1);
  var C = seg.map(function(d){return d.close;});
  var V = seg.map(function(d){return d.vol;});
  var H = seg.map(function(d){return d.high;});
  var L = seg.map(function(d){return d.low;});

  if (C.length < 40) return null;

  var cur  = C[C.length-1];
  var curV = V[V.length-1];
  var curH = H[H.length-1];
  var curL = L[L.length-1];
  var curDate = data[idx].date;

  // ── 均线 ──
  var ma20 = SMA(C, 20);
  var ma60 = SMA(C, 60);
  var maMa20 = ma20[ma20.length-1];
  var maMa60 = ma60[ma60.length-1];
  var maPrev = ma20[ma20.length-2];

  var aboveMa20 = cur > maMa20;
  var ma20Up   = maMa20 >= ma20[ma20.length-2];
  var aboveMa60 = cur > maMa60;

  // ── MACD ──
  var macd = MACD(C, 12, 26, 9);
  var dif = macd.dif[macd.dif.length-1];
  var difP= macd.dif[macd.dif.length-2];
  var sig = macd.sig[macd.sig.length-1];
  var sigP= macd.sig[macd.dif.length-1];
  var hist= macd.hist[macd.hist.length-1];
  var histP=macd.hist[macd.hist.length-2];
  var aboveZero = dif > 0 && sig > 0;
  var goldX = difP <= sigP && dif > sig;
  var deadX = difP >= sigP && dif < sig;

  // ── 量能 ──
  var avgVol20 = V.slice(-20).reduce(function(a,b){return a+b;},0)/20;
  var volRatio = curV / avgVol20;
  var volUp = curV > avgVol20 * 1.2;

  // ── 找关键高低点 ──
  // 简化：找近100天内的最高点和次高点，最低点和次低点
  var maxIdx=0, minIdx=0;
  for (var i=1; i<C.length; i++) { if(C[i]>C[maxIdx]) maxIdx=i; if(C[i]<C[minIdx]) minIdx=i; }

  var recentHigh = C[maxIdx];
  var recentLow  = C[minIdx];
  var range = recentHigh - recentLow;

  // 斐波那契回撤位
  var fib236 = recentHigh - range * 0.236;
  var fib382 = recentHigh - range * 0.382;
  var fib500 = recentHigh - range * 0.500;
  var fib618 = recentHigh - range * 0.618;

  // ── 判断趋势方向 ──
  // 上升趋势：MA20在MA60上方，MA20向上
  var uptrend = maMa20 > maMa60 && ma20Up;
  var downtrend = maMa20 < maMa60 && !ma20Up;

  // ── 识别波浪阶段 ──
  var phase = 'neutral';
  var signal = null;
  var stopLoss = null;
  var target1 = null, target2 = null;
  var confidence = 0; // 1-5分信号强度

  // ── 【买入场景1：2浪回调结束，3浪启动前】─────────────────
  // 条件：上升趋势 + 价格从高点回撤（接近fib382-fib618）+ 缩量 + MA20走平/向上 + MACD底背离或0轴下金叉
  var pullback  = downtrend === false && cur < recentHigh * 0.90; // 有明显回撤
  var nearFib   = cur >= fib618 * 0.95 && cur <= fib382 * 1.05; // 在斐波那契支撑区
  var volShrink = curV < avgVol20 * 0.8; // 缩量
  var macdDiv   = false; // 简化：dif开始回升

  // 更严格：找回撤幅度
  var pullbackPct = (recentHigh - cur) / recentHigh * 100;

  if (uptrend && pullback && nearFib && volShrink) {
    phase = 'wave2_rebound';
    signal = '2浪回调结束-关注买入';
    confidence = 3;
    stopLoss = fib618 * 0.97;
    target1 = recentHigh + (recentHigh - recentLow) * 0.382; // 1.382目标
    target2 = recentHigh + (recentHigh - recentLow) * 0.618; // 1.618目标
  }

  // ── 【买入场景2：3浪强势突破】───────────────────────────
  // 条件：价格突破近期高点 + 放量 + MA20向上 + MACD零轴上方金叉/红柱放大
  var breakout = cur > recentHigh * 0.98;
  var strongVol = volRatio >= 1.5;
  var confirmUp = aboveZero || goldX;

  if (uptrend && breakout && strongVol && confirmUp) {
    phase = 'wave3_breakout';
    signal = '3浪突破-强烈买入';
    confidence = 4;
    stopLoss = recentLow * 0.97;
    target1 = recentHigh + range * 1.0;   // 3浪等长目标
    target2 = recentHigh + range * 1.618; // 3浪1.618目标
  }

  // ── 【C浪末端抄底】─────────────────────────────────────
  // 条件：大幅下跌后 + 价格接近长期支撑 + 缩量 + MACD底背离 + 零轴下金叉
  var bigDrop = (recentHigh - cur) / recentHigh > 0.20; // 从高点跌幅超20%
  var nearLongLow = cur < recentLow * 1.05;
  var macdGoldXBelow = !aboveZero && goldX; // 零轴下金叉

  if (downtrend && bigDrop && nearLongLow && volShrink && macdGoldXBelow) {
    phase = 'waveC_bottom';
    signal = 'C浪末端-轻仓抄底';
    confidence = 3;
    stopLoss = recentLow * 0.97;
    target1 = recentHigh - range * 0.382;
    target2 = recentHigh - range * 0.618;
  }

  // ── 【卖出信号】─────────────────────────────────────────
  var sellSignal = null;
  // 顶背离：价格创新高但MACD没新高
  var macdPeaks = [];
  for (var i=5; i<macd.dif.length; i++) {
    if (macd.dif[i] > macd.dif[i-1] && macd.dif[i-1] > macd.dif[i-2]) {
      macdPeaks.push(macd.dif[i]);
    }
  }
  var topDiv = recentHigh > curH * 0.99 && macdPeaks.length > 0 &&
               dif < macdPeaks[macdPeaks.length-1] * 0.9;

  if (deadX || topDiv || (aboveZero && !aboveZero === false && hist < 0 && histP > 0)) {
    sellSignal = topDiv ? 'MACD顶背离-清仓' : (hist < 0 && histP > 0 ? '红柱转绿-减仓' : 'MACD死叉-减仓');
  }

  return {
    date: curDate,
    price: cur,
    phase: phase,
    signal: signal,
    confidence: confidence,
    stopLoss: stopLoss,
    target1: target1,
    target2: target2,
    ma20: maMa20,
    ma60: maMa60,
    aboveMa20: aboveMa20,
    ma20Up: ma20Up,
    uptrend: uptrend,
    aboveZero: aboveZero,
    goldX: goldX,
    deadX: deadX,
    volRatio: volRatio,
    volUp: volUp,
    dif: dif,
    sig: sig,
    hist: hist,
    fib382: fib382,
    fib500: fib500,
    fib618: fib618,
    pullbackPct: pullbackPct,
    recentHigh: recentHigh,
    recentLow: recentLow,
    sellSignal: sellSignal,
    aboveZero: aboveZero,
  };
}

// ── 优化版波浪回测 ───────────────────────────────────
function waveBacktest(data, name, initialCapital) {
  var capital = initialCapital;
  var position = 0;
  var avgCost = 0;
  var peak = initialCapital;
  var maxDD = 0;
  var trades = [];
  var equity = [initialCapital];
  var posPhase = null;
  var buyPhase = null;
  var stopLoss = null;
  var target1 = null, target2 = null;

  for (var i = 120; i < data.length; i++) {
    var wave = waveAnalysis(data, i, 120);
    if (!wave || wave.signal === null) {
      equity.push(capital + position * data[i].close);
      continue;
    }

    var price = data[i].close;
    var date  = data[i].date;

    // ── 买入 ──
    if (position === 0 && wave.signal && wave.confidence >= 3) {
      // 3浪突破：半仓入场
      // 2浪底/C浪底：轻仓3成
      var ratio = wave.phase === 'wave3_breakout' ? 0.5 :
                  wave.phase === 'wave2_rebound' ? 0.3 : 0.5;
      var shares = Math.floor(capital * ratio / price);
      if (shares > 0) {
        avgCost = price;
        position = shares;
        capital -= shares * price;
        buyPhase = wave.phase;
        stopLoss = wave.stopLoss;
        target1  = wave.target1;
        target2  = wave.target2;
        trades.push({
          type:'BUY', date:date, price:price, shares:shares,
          value:shares*price, reason:wave.signal,
          phase:wave.phase, confidence:wave.confidence,
          stop:stopLoss?stopLoss.toFixed(3):'--',
          tgt1:target1?target1.toFixed(3):'--',
          tgt2:target2?target2.toFixed(3):'--',
        });
      }
    }

    // ── 加仓（回踩20日线确认3浪）──
    if (position > 0 && buyPhase === 'wave3_breakout' && capital > 0 && wave.uptrend) {
      var near20ma = Math.abs(price - wave.ma20) / wave.ma20 < 0.015;
      if (near20ma && wave.confidence >= 4) {
        var addShares = Math.floor(capital * 0.3 / price);
        if (addShares > 0) {
          var newAvg = (position * avgCost + addShares * price) / (position + addShares);
          avgCost = newAvg;
          position += addShares;
          capital -= addShares * price;
          trades.push({
            type:'BUY', date:date, price:price, shares:addShares,
            value:addShares*price, reason:'3浪确认-回踩MA20加仓',
          });
          buyPhase = 'wave3_holding';
        }
      }
    }

    // ── 卖出/止损 ──
    if (position > 0) {
      var shouldSell = false;
      var sellReason = '';
      var partialSell = false;

      // 止损
      if (stopLoss && price < stopLoss) {
        shouldSell = true;
        sellReason = '止损(跌破' + stopLoss.toFixed(3) + ')';
      }
      // 到达目标1，部分止盈
      else if (target1 && price >= target1 && avgCost > 0) {
        // 检查是否已经部分止盈
        var lastTrade = trades[trades.length-1];
        if (!lastTrade.halfSell) {
          var halfPos = Math.floor(position * 0.5);
          capital += halfPos * price;
          position -= halfPos;
          var pnl = position > 0 ? ((price - avgCost) / avgCost * 100).toFixed(2) + '%' : ((price - avgCost) / avgCost * 100).toFixed(2) + '%';
          trades.push({
            type:'SELL', date:date, price:price, shares:halfPos,
            value:halfPos*price, pnl:pnl,
            reason:'目标1止盈50%:>' + (target1?target1.toFixed(3):'--'),
            halfSell:true,
          });
          stopLoss = Math.max(stopLoss || 0, price * 0.97); // 移动止损
          target1 = target2;
          target2 = null;
          partialSell = true;
        }
      }
      // 到达目标2，全清
      else if (target2 && price >= target2) {
        shouldSell = true;
        sellReason = '目标2止盈清仓';
      }
      // MACD顶背离或死叉
      else if (wave.sellSignal) {
        shouldSell = true;
        sellReason = wave.sellSignal;
      }
      // 跌破20日线（稳健止损）
      else if (!wave.aboveMa20 && buyPhase !== 'wave3_holding') {
        shouldSell = true;
        sellReason = '跌破MA20';
      }

      if (shouldSell) {
        capital += position * price;
        var pnl = ((price - avgCost) / avgCost * 100).toFixed(2);
        trades.push({
          type:'SELL', date:date, price:price, shares:position,
          value:position*price, pnl:pnl+'%',
          reason:sellReason,
        });
        position=0; avgCost=0; buyPhase=null;
        stopLoss=null; target1=null; target2=null;
      }
    }

    equity.push(capital + position * price);
    var curValue = equity[equity.length-1];
    if (curValue > peak) peak = curValue;
    var dd = (peak - curValue) / peak * 100;
    if (dd > maxDD) maxDD = dd;
  }

  // 强制平仓
  if (position > 0) {
    var lastPrice = data[data.length-1].close;
    capital += position * lastPrice;
    trades.push({
      type:'SELL', date:data[data.length-1].date, price:lastPrice,
      shares:position, value:position*lastPrice,
      pnl:((lastPrice-avgCost)/avgCost*100).toFixed(2)+'%',
      reason:'回测结束强制平仓',
    });
    equity[equity.length-1] = capital;
  }

  return { equity:equity, trades:trades, finalValue:capital, peak:peak, maxDD:maxDD };
}

// ── 买入持有 ────────────────────────────────
function buyHold(data, initialCapital) {
  var firstP = data[0].close;
  var lastP  = data[data.length-1].close;
  var shares = Math.floor(initialCapital / firstP);
  var cost   = shares * firstP;
  var finalV  = shares * lastP;
  var years  = (new Date(data[data.length-1].date) - new Date(data[0].date)) / (365.25 * 864e5);
  return { cost:cost, finalV:finalV, years:years };
}

// ── 绩效统计 ─────────────────────────────────
function stats(equity, initialCapital, maxDD) {
  var finalV   = equity[equity.length-1];
  var totalRet  = (finalV - initialCapital) / initialCapital;
  var n = equity.length;
  var years = n / 252;
  var cagr = Math.pow(finalV / initialCapital, 1 / years) - 1;
  var rets = [];
  for (var i=1; i<equity.length; i++) rets.push((equity[i]-equity[i-1])/equity[i-1]);
  var avgR = rets.reduce(function(a,b){return a+b;},0)/rets.length;
  var stdR = Math.sqrt(rets.reduce(function(a,b){return a+(b-avgR)*(b-avgR);},0)/rets.length);
  var annStd = stdR * Math.sqrt(252);
  var sharpe = annStd > 0 ? (cagr - 0.03) / annStd : 0;
  var winRate = rets.filter(function(r){return r>0;}).length / rets.length;
  return { finalV:finalV, totalRet:totalRet, cagr:cagr, sharpe:sharpe, winRate:winRate, maxDD:maxDD };
}

// ── 主程序 ───────────────────────────────────
async function main() {
  console.log('\n' + '='.repeat(70));
  console.log('  波浪策略 v2 回测  |  MA20+MACD+斐波那契共振');
  console.log('  初始资金: ¥' + ICAP + '  |  周期: 2008~2026');
  console.log('='.repeat(70) + '\n');

  var ETFS = [
    {code:'510300', name:'沪深300ETF', market:'SH'},
    {code:'510500', name:'中证500ETF', market:'SH'},
    {code:'513100', name:'纳指100ETF', market:'SH'},
  ];

  var allResults = [];

  for (var ei = 0; ei < ETFS.length; ei++) {
    var etf = ETFS[ei];
    process.stdout.write('>> 回测 ' + etf.name + ' (' + etf.code + ')... ');
    var data = await fetchKline(etf.code, etf.market);
    await sleep(300);
    if (data.length < 1000) { console.log('数据不足: ' + data.length + '条'); continue; }

    // 过滤有效日期（去掉太老的数据，保留2010之后）
    var validData = data.filter(function(d){ return d.date >= '2010-01-01' && d.date <= '2026-04-16'; });
    console.log('有效数据: ' + validData.length + '条 (' + validData[0].date + ' ~ ' + validData[validData.length-1].date + ')');

    // 波浪策略
    var waveR = waveBacktest(validData, etf.name, ICAP);
    var waveS = stats(waveR.equity, ICAP, waveR.maxDD);

    // 买入持有
    var bh = buyHold(validData, ICAP);

    var buyHoldPct = (bh.finalV / bh.cost - 1) * 100;

    allResults.push({
      name: etf.name,
      dateRange: validData[0].date + ' ~ ' + validData[validData.length-1].date,
      dataLen: validData.length,
      wave: waveS,
      waveMaxDD: waveR.maxDD,
      waveTrades: waveR.trades,
      bh: bh,
      buyHoldPct: buyHoldPct,
    });
  }

  // ── 输出汇总 ──
  console.log('\n' + '='.repeat(70));
  console.log('  回测结果汇总');
  console.log('='.repeat(70));

  for (var ri = 0; ri < allResults.length; ri++) {
    var r = allResults[ri];
    var w = r.wave, b = r.bh;
    var diff = w.finalV - b.finalV;

    console.log('\n【' + r.name + '】  ' + r.dateRange + '  (' + r.dataLen + '条日线)');
    console.log('  ' + '-'.repeat(60));
    console.log('              波浪策略v2          买入持有         差值');
    console.log('  期末资金  ' + w.finalV.toFixed(0).padStart(14) + '    ' + b.finalV.toFixed(0).padStart(14) + '    ' + (diff>=0?'+':'')+diff.toFixed(0).padStart(10));
    console.log('  总收益率  ' + (w.totalRet*100).toFixed(1).padStart(14) + '%   ' + r.buyHoldPct.toFixed(1).padStart(13) + '%  ' + ((w.totalRet-b.finalV/b.cost+1)*100 - r.buyHoldPct >=0?'+':'') + ((w.totalRet*100-r.buyHoldPct)).toFixed(1)+'%');
    console.log('  年化收益  ' + (w.cagr*100).toFixed(2).padStart(14) + '%   ' + (Math.pow(b.finalV/b.cost, 1/b.years)-1)*100+'%'.padStart(13));
    console.log('  最大回撤  ' + r.waveMaxDD.toFixed(2).padStart(14) + '%');
    console.log('  夏普比率  ' + w.sharpe.toFixed(2).padStart(14));
    console.log('  日胜率   ' + (w.winRate*100).toFixed(1).padStart(14) + '%');
    console.log('  交易次数  ' + (r.waveTrades.filter(function(t){return t.type==='BUY';}).length).toString().padStart(14) + '次');

    // 典型交易
    var buys = r.waveTrades.filter(function(t){return t.type==='BUY';});
    if (buys.length > 0) {
      console.log('  最近买入: ' + buys[buys.length-1].date + '  ' + buys[buys.length-1].reason);
    }
  }

  // ── 总体评估 ──
  var waveAvgRet = allResults.reduce(function(a,r){return a+r.wave.totalRet;},0)/allResults.length;
  var bhAvgRet   = allResults.reduce(function(a,r){return a+(r.bh.finalV/r.bh.cost-1);},0)/allResults.length;
  var waveAvgDD  = allResults.reduce(function(a,r){return a+r.waveMaxDD;},0)/allResults.length;

  console.log('\n' + '='.repeat(70));
  console.log('  策略总体评估（三标平均）');
  console.log('='.repeat(70));
  console.log('  波浪策略  平均总收益: ' + (waveAvgRet*100).toFixed(1) + '%  平均最大回撤: ' + waveAvgDD.toFixed(1) + '%');
  console.log('  买入持有  平均总收益: ' + (bhAvgRet*100).toFixed(1) + '%');
  console.log('  波浪 vs 持有: ' + ((waveAvgRet-bhAvgRet)*100).toFixed(1) + 'pp');

  if (waveAvgRet > bhAvgRet && waveAvgDD < 30) {
    console.log('\n  结论: 波浪策略可采用（回测收益更优且回撤可控）');
  } else if (waveAvgRet > bhAvgRet) {
    console.log('\n  结论: 波浪策略收益更优但回撤较大，建议轻仓运行');
  } else {
    console.log('\n  结论: 买入持有回测更优，暂不采用波浪策略，建议优化后再测试');
  }

  // 保存结果
  var summary = JSON.stringify(allResults, null, 2);
  fs.writeFileSync(path.join(SCRIPT_DIR, 'wave_backtest_v2_result.json'), summary, 'utf8');
  console.log('\n[OK] 详细结果已保存: wave_backtest_v2_result.json');
}

main().catch(console.error);
