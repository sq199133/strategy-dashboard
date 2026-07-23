// ============================================================
// 波浪策略回测脚本
// 标的：沪深300ETF(510300)、中证500ETF(510500)、纳指100ETF(513100)
// 周期：2018-01-01 ~ 2026-04-16
// 对比：波浪策略 vs 买入持有
// ============================================================

var path = require('path');
var fs   = require('fs');
var SCRIPT_DIR = __dirname;

function sleep(ms) { return new Promise(function(r){ setTimeout(r, ms); }); }

function txSecid(code, market) {
  return market === 'SZ' ? 'sz' + code : 'sh' + code;
}

// ── K线获取 ───────────────────────────────────────
async function fetchKline(code, market, beg, end, limit) {
  var secid = txSecid(code, market);
  var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + secid + ',day,,,' + (limit||800) + ',qfq';
  try {
    var r = await fetch(url, { signal: AbortSignal.timeout(12000) });
    var j = await r.json();
    var arr = j.data && j.data[secid]
      ? (j.data[secid].qfqday || j.data[secid].day || [])
      : [];
    return arr.map(function(k) {
      return { date:k[0], open:+k[1], close:+k[2], high:+k[3], low:+k[4], vol:+k[5] };
    });
  } catch(e) { return []; }
}

// ── 指标 ────────────────────────────────────────────
function SMA(prices, n) {
  var out = new Array(prices.length).fill(null);
  for (var i = n-1; i < prices.length; i++) {
    var s = 0; for (var j = i-n+1; j<=i; j++) s += prices[j];
    out[i] = s / n;
  }
  return out;
}

function EMA(prices, n) {
  var k = 2/(n+1);
  var out = new Array(prices.length).fill(null);
  var seed = 0; for (var i=0; i<n; i++) seed += prices[i];
  out[n-1] = seed/n;
  for (var i=n; i<prices.length; i++) out[i] = prices[i]*k + out[i-1]*(1-k);
  return out;
}

function MACD(prices, f, s, sig) {
  f=f||12; s=s||26; sig=sig||9;
  var ef=EMA(prices,f), es=EMA(prices,s);
  var dif = new Array(prices.length).fill(null);
  for (var i=s-1; i<prices.length; i++) dif[i] = ef[i] - es[i];
  var sk=2/(sig+1), se = new Array(prices.length).fill(null);
  se[s-1]=dif[s-1];
  for (var i=s; i<dif.length; i++) se[i]=dif[i]*sk+se[i-1]*(1-sk);
  var hist=dif.map(function(v,i){ return v===null?null:v-se[i]; });
  return { dif:dif, sig:se, hist:hist };
}

// ── 简化波浪识别 ──────────────────────────────────
// 思路：找近期显著高低点，判断浪型阶段
// 只识别：2浪底（买入机会）、3浪突破（确认买入）、4浪顶（卖出）、5浪顶（清仓）
function detectWave(data, idx, params) {
  // params: lookback=最近N天找高低点
  var lookback = params.lookback || 60;
  var start = Math.max(0, idx - lookback);
  var end   = idx;

  var C = data.slice(start, end+1).map(function(d){return d.close;});
  var V = data.slice(start, end+1).map(function(d){return d.vol;});
  var dates = data.slice(start, end+1).map(function(d){return d.date;});
  var prices = C; // 收盘价序列

  if (prices.length < 20) return null;

  // 找近期最低点和最高点
  var minIdx = 0, maxIdx = 0;
  for (var i=1; i<prices.length-1; i++) {
    if (prices[i] < prices[minIdx]) minIdx = i;
    if (prices[i] > prices[maxIdx]) maxIdx = i;
  }

  var low  = prices[minIdx];
  var high = prices[maxIdx];
  var pivotLow = low;  // 近期低点
  var pivotHigh = high; // 近期高点

  // 当前价格
  var cur = prices[prices.length-1];
  var ma20 = SMA(prices, 20);
  var maCur = ma20[ma20.length-1];
  var macd = MACD(prices, 12, 26, 9);
  var macdCur = macd.hist[macd.hist.length-1];
  var macdPrev = macd.hist[macd.hist.length-2];
  var difCur = macd.dif[macd.dif.length-1];
  var sigCur = macd.sig[macd.sig.length-1];
  var difPrev = macd.dif[macd.dif.length-2];
  var sigPrev = macd.sig[macd.sig.length-1];

  var aboveMa  = cur > maCur;
  var maUp     = maCur >= ma20[ma20.length-2];

  // 量能：当前量 vs 20日均量
  var avgVol20 = V.slice(-20).reduce(function(a,b){return a+b;},0)/20;
  var volRatio = V[V.length-1] / avgVol20;

  // ── 关键比例计算 ──
  var range = high - low;
  var fib382 = high - range * 0.382;
  var fib500 = high - range * 0.500;
  var fib618 = high - range * 0.618;

  // 顶背离检测（简化版：价格创新高但MACD没创新高）
  var macdPeaks = [];
  for (var i=2; i<macd.dif.length; i++) {
    if (macd.dif[i] > macd.dif[i-1] && macd.dif[i-1] > macd.dif[i-2]) {
      macdPeaks.push({i:i, val:macd.dif[i]});
    }
  }
  var recentPeak = macdPeaks.length > 0 ? macdPeaks[macdPeaks.length-1] : null;

  // 底背离检测
  var macdTroughs = [];
  for (var i=2; i<macd.dif.length; i++) {
    if (macd.dif[i] < macd.dif[i-1] && macd.dif[i-1] < macd.dif[i-2]) {
      macdTroughs.push({i:i, val:macd.dif[i]});
    }
  }
  var recentTrough = macdTroughs.length > 0 ? macdTroughs[macdTroughs.length-1] : null;

  // ── 波浪阶段判断 ──
  // 简化判断逻辑：
  // 当前在低位区（接近 fib618 支撑） + MA20走平/向上 + MACD底背离 → 可能是2浪底/C浪底
  // 价格突破近期高点 + 放量 + MACD零轴上方金叉 → 3浪启动
  // 价格在高位 + MACD顶背离 → 可能5浪顶

  var phase = 'unknown';
  var entrySignal = null;
  var stopLoss = null;
  var target1 = null;
  var target2 = null;

  // 情况1：价格接近支撑区（fib618 附近），MA20向上，MACD底背离或零轴下金叉 → 2浪底/C浪底 买入机会
  var nearSupport = cur <= fib618 * 1.03;
  var macdGoldX = difPrev <= sigPrev && difCur > sigCur;  // 金叉
  var macdBelowZero = difCur < 0;
  var bottomSignal = nearSupport && maUp && (macdGoldX || (macdBelowZero && recentTrough && recentTrough.val > difCur));

  // 情况2：价格突破近期高点 + 放量1.5倍 + MA20向上 + MACD零轴上金叉 → 3浪启动（最强信号）
  var breakout = cur > high * 0.98 && volRatio >= 1.5;
  var strongUp = breakout && maUp && (macdGoldX || (difCur>0 && sigCur>0));

  if (strongUp) {
    phase = 'wave3_start';
    entrySignal = '3浪启动-强烈买入';
    stopLoss = low * 0.97; // 止损在近期低点下方3%
    target1 = low + range * 1.618;  // 3浪目标1: 1.618倍
    target2 = low + range * 2.618;  // 3浪目标2: 2.618倍
  } else if (bottomSignal) {
    phase = 'wave2_bottom';
    entrySignal = '2浪底/C浪末-买入';
    stopLoss = low * 0.97;
    target1 = high;
    target2 = high + range * 0.618;
  }

  // 卖出信号
  var exitSignal = null;
  var macdDeadX = difPrev >= sigPrev && difCur < sigCur;  // 死叉
  var topDivergence = recentPeak && difCur < recentPeak.val * 0.9 && cur > high * 0.98; // 顶背离
  var macdWeaken = macdCur < 0 && macdPrev > 0; // 红柱转绿

  if (phase !== 'unknown' && (macdDeadX || topDivergence || macdWeaken)) {
    exitSignal = topDivergence ? '5浪顶-顶背离清仓' : (macdWeaken ? 'MACD红柱转绿-减仓' : 'MACD死叉-减仓');
  }

  return {
    phase: phase,
    date: dates[dates.length-1],
    price: cur,
    low: low,
    high: high,
    ma20: maCur,
    maUp: maUp,
    aboveMa: aboveMa,
    dif: difCur,
    sig: sigCur,
    hist: macdCur,
    aboveZero: difCur > 0 && sigCur > 0,
    volRatio: volRatio,
    entrySignal: entrySignal,
    exitSignal: exitSignal,
    stopLoss: stopLoss,
    target1: target1,
    target2: target2,
    fib382: fib382,
    fib500: fib500,
    fib618: fib618,
  };
}

// ── 波浪策略回测 ─────────────────────────────────
function waveBacktest(data, name, initialCapital) {
  var capital = initialCapital;
  var position = 0;
  var avgCost = 0;
  var peak = initialCapital;
  var maxDD = 0;
  var trades = [];

  var posPhase = null; // null | 'watching' | 'wave3' | 'wave2'
  var buyDate = null, buyPrice = null;
  var stopLoss = null;
  var target1 = null, target2 = null;
  var wave3Started = false;

  for (var i = 60; i < data.length; i++) {
    var wave = detectWave(data, i, {lookback: 60});
    if (!wave) continue;

    var price = data[i].close;
    var date  = data[i].date;
    var totalValue = capital + position * price;

    // ── 买入逻辑 ──
    if (position === 0 && wave.entrySignal) {
      var shares = Math.floor(capital * 0.5 / price); // 先半仓
      if (shares > 0) {
        avgCost = price;
        position = shares;
        capital = capital - shares * price;
        buyDate = date;
        buyPrice = price;
        stopLoss = wave.stopLoss;
        target1 = wave.target1;
        target2 = wave.target2;
        posPhase = wave.phase;
        wave3Started = wave.phase === 'wave3_start';
        trades.push({
          type: 'BUY', date: date, price: price, shares: shares,
          value: shares * price, reason: wave.entrySignal,
          stopLoss: stopLoss ? stopLoss.toFixed(3) : '--',
          target1: target1 ? target1.toFixed(3) : '--',
        });
      }
    }

    // ── 二次加仓（3浪确认后回踩加仓）─
    if (position > 0 && wave3Started && capital > 0) {
      var near20ma = price <= wave.ma20 * 1.01 && price >= wave.ma20 * 0.99;
      if (near20ma) {
        var moreShares = Math.floor(capital * 0.3 / price); // 再加3成，总共不超8成
        if (moreShares > 0) {
          var newAvg = (position * avgCost + moreShares * price) / (position + moreShares);
          avgCost = newAvg;
          position += moreShares;
          capital -= moreShares * price;
          trades.push({
            type: 'BUY', date: date, price: price, shares: moreShares,
            value: moreShares * price, reason: '3浪确认-回踩加仓至8成',
          });
        }
      }
    }

    // ── 卖出/止损逻辑 ──
    if (position > 0) {
      var shouldSell = false;
      var sellReason = '';

      // 止损检查
      if (price < stopLoss) {
        shouldSell = true;
        sellReason = '止损(跌破' + stopLoss.toFixed(3) + ')';
      }
      // 止盈检查（到达目标1，减仓50%）
      else if (target1 && price >= target1 && !trades[trades.length-1].halfSell) {
        // 部分止盈50%
        var halfPos = Math.floor(position * 0.5);
        capital += halfPos * price;
        var remaining = position - halfPos;
        position = remaining;
        avgCost = remaining > 0 ? avgCost : 0;
        trades.push({
          type: 'SELL', date: date, price: price, shares: halfPos,
          value: halfPos * price, pnl: ((price - avgCost) / avgCost * 100).toFixed(2) + '%',
          reason: '止盈(到达目标1:' + target1.toFixed(3) + ')',
          halfSell: true,
        });
        stopLoss = avgCost * 1.0; // 移动止损到成本价
        target1 = target2;
        target2 = null;
      }
      // 到达目标2，全清
      else if (target2 && price >= target2) {
        shouldSell = true;
        sellReason = '止盈(到达目标2:' + target2.toFixed(3) + ')';
      }
      // MACD死叉/顶背离/红柱转绿
      else if (wave.exitSignal) {
        shouldSell = true;
        sellReason = wave.exitSignal;
      }

      if (shouldSell) {
        capital += position * price;
        var pnlPct = ((price - avgCost) / avgCost * 100).toFixed(2);
        trades.push({
          type: 'SELL', date: date, price: price, shares: position,
          value: position * price, pnl: pnlPct + '%',
          reason: sellReason,
        });
        position = 0; avgCost = 0; stopLoss = null;
        target1 = null; target2 = null; posPhase = null;
        wave3Started = false;
      }
    }

    // 净值记录
    var curValue = capital + position * price;
    if (curValue > peak) peak = curValue;
    var dd = (peak - curValue) / peak * 100;
    if (dd > maxDD) maxDD = dd;
  }

  // 强制平仓
  if (position > 0) {
    var lastPrice = data[data.length-1].close;
    capital += position * lastPrice;
    trades.push({
      type: 'SELL', date: data[data.length-1].date, price: lastPrice,
      shares: position, value: position * lastPrice,
      pnl: ((lastPrice - avgCost) / avgCost * 100).toFixed(2) + '%',
      reason: '回测结束强制平仓',
    });
  }

  return {
    name: name,
    finalValue: capital,
    finalCapital: capital,
    trades: trades,
    peak: peak,
    maxDD: maxDD,
  };
}

// ── 买入持有基准 ────────────────────────────────
function buyHold(data, initialCapital) {
  var firstPrice = data[0].close;
  var lastPrice  = data[data.length-1].close;
  var shares = Math.floor(initialCapital / firstPrice);
  var cost   = shares * firstPrice;
  var finalValue = shares * lastPrice;
  var years  = (new Date(data[data.length-1].date) - new Date(data[0].date)) / (365.25 * 864e5);
  return {
    cost: cost,
    finalValue: finalValue,
    shares: shares,
    years: years,
    cagr: Math.pow(finalValue / cost, 1 / years) - 1,
  };
}

// ── 绩效统计 ──────────────────────────────────
function stats(equity, initialCapital, maxDD) {
  var finalV = equity[equity.length-1];
  var totalRet = (finalV - initialCapital) / initialCapital;
  var n = equity.length;
  var years = n / 252;
  var cagr = Math.pow(finalV / initialCapital, 1 / years) - 1;

  var rets = [];
  for (var i=1; i<equity.length; i++)
    rets.push((equity[i]-equity[i-1])/equity[i-1]);

  var avgR = rets.reduce(function(a,b){return a+b;},0)/rets.length;
  var stdR = Math.sqrt(rets.reduce(function(a,b){return a+(b-avgR)*(b-avgR);},0)/rets.length);
  var annStd = stdR * Math.sqrt(252);
  var sharpe = annStd > 0 ? (cagr - 0.03) / annStd : 0;
  var winRate = rets.filter(function(r){return r>0;}).length / rets.length;

  return {
    finalV: finalV,
    totalRet: totalRet,
    cagr: cagr,
    sharpe: sharpe,
    winRate: winRate,
    maxDD: maxDD,
  };
}

// ── 主程序 ───────────────────────────────────
async function main() {
  console.log('\n' + '='.repeat(65));
  console.log('  波浪策略回测  |  沪深300ETF、中证500ETF、纳指100ETF');
  console.log('  周期: 2018-01-01 ~ 2026-04-16');
  console.log('='.repeat(65) + '\n');

  var ICAP = 100000;
  var ETFS = [
    {code:'510300', name:'沪深300ETF', market:'SH'},
    {code:'510500', name:'中证500ETF', market:'SH'},
    {code:'513100', name:'纳指100ETF', market:'SH'},
  ];

  var allResults = [];

  for (var ei = 0; ei < ETFS.length; ei++) {
    var etf = ETFS[ei];
    console.log('>> 正在回测 ' + etf.name + ' (' + etf.code + ')...');
    var data = await fetchKline(etf.code, etf.market, '20180101', '20260416', 800);
    if (data.length < 500) {
      console.log('  数据不足: ' + data.length + '条'); continue;
    }

    // 过滤日期
    data = data.filter(function(d){ return d.date >= '2018-01-01'; });

    // 波浪策略回测
    var waveResult = waveBacktest(data, etf.name, ICAP);

    // 计算净值曲线
    var equity = [ICAP];
    var capital = ICAP, position = 0, avgCost = 0;
    for (var i=60; i<data.length; i++) {
      var wave = detectWave(data, i, {lookback:60});
      var price = data[i].close;
      var date = data[i].date;
      var totalValue = capital + position * price;

      // 模拟买入
      if (position === 0 && wave && wave.entrySignal) {
        var shares = Math.floor(capital * 0.5 / price);
        if (shares > 0) {
          avgCost = price;
          position = shares;
          capital = capital - shares * price;
        }
      }
      // 模拟加仓
      if (position > 0 && wave && wave.phase === 'wave3_start' && capital > 0) {
        var near20 = price <= wave.ma20 * 1.01 && price >= wave.ma20 * 0.99;
        if (near20) {
          var more = Math.floor(capital * 0.3 / price);
          if (more > 0) {
            avgCost = (position * avgCost + more * price) / (position + more);
            position += more;
            capital -= more * price;
          }
        }
      }
      // 模拟卖出
      if (position > 0) {
        var stopLoss = wave ? wave.stopLoss : null;
        if (price < stopLoss || (wave && wave.exitSignal)) {
          capital += position * price;
          position = 0; avgCost = 0;
        }
      }
      equity.push(capital + position * price);
    }

    // 买入持有
    var bh = buyHold(data, ICAP);

    // 波浪统计
    var waveStats = stats(equity, ICAP, waveResult.maxDD);

    allResults.push({
      name: etf.name,
      dataLen: data.length,
      dateRange: data[0].date + ' ~ ' + data[data.length-1].date,
      wave: waveStats,
      bh: bh,
      trades: waveResult.trades,
    });

    console.log('  数据: ' + data.length + '条  |  ' + data[0].date + ' ~ ' + data[data.length-1].date);
    console.log('');
  }

  // ── 汇总输出 ──
  console.log('='.repeat(65));
  console.log('  回测结果汇总');
  console.log('='.repeat(65));

  for (var ri = 0; ri < allResults.length; ri++) {
    var r = allResults[ri];
    console.log('\n【' + r.name + '】  (' + r.dateRange + ')');
    console.log('  ──────────────────────────────────────────────');
    console.log('           波浪策略          买入持有');
    console.log('  期末资金   ' + r.wave.finalV.toFixed(0).padStart(10) + '    ' + r.bh.finalValue.toFixed(0).padStart(10));
    console.log('  总收益率  ' + (r.wave.totalRet*100).toFixed(2).padStart(9) + '%   ' + ((r.bh.finalValue/r.bh.cost-1)*100).toFixed(2).padStart(9) + '%');
    console.log('  年化收益  ' + (r.wave.cagr*100).toFixed(2).padStart(9) + '%   ' + (r.bh.cagr*100).toFixed(2).padStart(9) + '%');
    console.log('  最大回撤  ' + r.wave.maxDD.toFixed(2).padStart(9) + '%   ' + '--'.padStart(10));
    console.log('  夏普比率  ' + r.wave.sharpe.toFixed(2).padStart(10) + '    ' + '--'.padStart(10));
    console.log('  日胜率   ' + (r.wave.winRate*100).toFixed(1).padStart(9) + '%   ' + '--'.padStart(10));
    console.log('  交易次数  ' + (r.trades.length/2).toFixed(0).padStart(10) + '次  ' + '--'.padStart(10));
  }

  // ── 保存结果 ──
  var summaryLines = ['波浪策略回测结果汇总', ''];
  for (var si = 0; si < allResults.length; si++) {
    var s = allResults[si];
    var w = s.wave, b = s.bh;
    summaryLines.push('标的: ' + s.name);
    summaryLines.push('波浪策略: 期末=' + w.finalV.toFixed(0) + ' 总收益=' + (w.totalRet*100).toFixed(2) + '% 年化=' + (w.cagr*100).toFixed(2) + '% 最大回撤=' + w.maxDD.toFixed(2) + '% 夏普=' + w.sharpe.toFixed(2));
    summaryLines.push('买入持有: 期末=' + b.finalValue.toFixed(0) + ' 总收益=' + ((b.finalValue/b.cost-1)*100).toFixed(2) + '% 年化=' + (b.cagr*100).toFixed(2) + '%');
    summaryLines.push('');
  }
  fs.writeFileSync(path.join(SCRIPT_DIR, 'wave_backtest_result.txt'), summaryLines.join('\n'), 'utf8');
  console.log('\n[OK] 结果已保存: wave_backtest_result.txt');
}

main().catch(console.error);
