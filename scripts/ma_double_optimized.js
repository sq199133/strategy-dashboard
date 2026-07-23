// ============================================================
// 双均线策略优化版 v2（MACD+双均线共振+ATR过滤）
// 优化点：
// 1. 卖出：MACD死叉（比MA60死叉更快）
// 2. 买入：MACD零轴上金叉 + MA20>MA60
// 3. ATR波动率过滤：ATR/价格<1.5%时视为低波动震荡，空仓观望
// ============================================================

var path = require('path');
var fs   = require('fs');
var SCRIPT_DIR = __dirname;
var ICAP = 100000;

function sleep(ms) { return new Promise(function(r){ setTimeout(r,ms); }); }

function txSecid(code, market) { return market === 'SZ' ? 'sz' + code : 'sh' + code; }

async function fetchKline(code, market) {
  var secid = txSecid(code, market);
  var periods = [
    ['2018-01-01','2020-12-31'],
    ['2021-01-01','2023-12-31'],
    ['2024-01-01','2026-12-31'],
  ];
  var all = [];
  for (var pi = 0; pi < periods.length; pi++) {
    var beg = periods[pi][0], end = periods[pi][1];
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + secid + ',day,' + beg + ',' + end + ',500,qfq';
    try {
      var r = await fetch(url, { signal: AbortSignal.timeout(10000) });
      var j = await r.json();
      var arr = j.data && j.data[secid] ? (j.data[secid].qfqday || j.data[secid].day || []) : [];
      all = all.concat(arr);
      await sleep(250);
    } catch(e) {}
  }
  var seen = {};
  var uniq = all.filter(function(k){ if(seen[k[0]]) return false; seen[k[0]]=true; return true; });
  uniq.sort(function(a,b){ return a[0].localeCompare(b[0]); });
  return uniq.map(function(k){ return {date:k[0],open:+k[1],close:+k[2],high:+k[3],low:+k[4],vol:+k[5]}; });
}

function SMA(prices, n) {
  var out = new Array(prices.length).fill(null);
  for (var i=n-1; i<prices.length; i++) {
    var s=0; for(var j=i-n+1;j<=i;j++) s+=prices[j];
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
  f=f||12; s=s||26; sig=sig||9;
  var ef=EMA(prices,f), es=EMA(prices,s);
  var dif=new Array(prices.length).fill(null);
  for(var i=s-1;i<prices.length;i++) dif[i]=ef[i]-es[i];
  var sk=2/(sig+1), se=new Array(prices.length).fill(null);
  se[s-1]=dif[s-1];
  for(var i=s;i<dif.length;i++) se[i]=dif[i]*sk+se[i-1]*(1-sk);
  var hist=dif.map(function(v,i){return v===null?null:v-se[i];});
  return {dif:dif, sig:se, hist:hist};
}

// ATR计算（14日）
function ATR(data, n) {
  n = n || 14;
  var tr = [];
  for (var i = 1; i < data.length; i++) {
    var h = data[i].high, l = data[i].low, pc = data[i-1].close;
    var tr1 = h - l;
    var tr2 = Math.abs(h - pc);
    var tr3 = Math.abs(l - pc);
    tr.push(Math.max(tr1, tr2, tr3));
  }
  var atr = new Array(data.length).fill(null);
  var seed = 0;
  for (var i = 0; i < n && i < tr.length; i++) seed += tr[i];
  atr[n] = seed / n;
  for (var i = n+1; i < data.length; i++) {
    atr[i] = (atr[i-1] * (n-1) + tr[i-1]) / n;
  }
  return atr;
}

// ── 优化版核心策略 ────────────────────────────────
function analyzeOptimized(data, idx) {
  if (idx < 70) return null;

  var closes = data.slice(0, idx+1).map(function(d){return d.close;});
  var highs  = data.slice(0, idx+1).map(function(d){return d.high;});
  var lows   = data.slice(0, idx+1).map(function(d){return d.low;});
  var vols   = data.slice(0, idx+1).map(function(d){return d.vol;});

  var ma20 = SMA(closes, 20);
  var ma60 = SMA(closes, 60);
  var macd = MACD(closes, 12, 26, 9);
  var atr  = ATR(data, 14);

  var cur = closes[idx];
  var curV = vols[idx];
  var avgVol20 = vols.slice(-20).reduce(function(a,b){return a+b;},0)/20;

  // 当前值
  var m20 = ma20[idx], m20_1 = ma20[idx-1], m20_2 = ma20[idx-2];
  var m60 = ma60[idx], m60_1 = ma60[idx-1];
  var dif = macd.dif[idx], dif_1 = macd.dif[idx-1];
  var sig = macd.sig[idx], sig_1 = macd.sig[idx-1];
  var hist = macd.hist[idx];
  var atrCur = atr[idx];

  // ATR波动率（当前ATR/当前价格）
  var atrPct = atrCur ? (atrCur / cur * 100) : 0;
  var lowVolatility = atrPct < 1.5; // ATR<1.5%视为低波动震荡

  // ── 买入条件（优化后）─────────────────────────
  // 条件1：MACD零轴上方金叉（dif上穿sig，且都在零轴上方）
  var macdGoldX = dif_1 <= sig_1 && dif > sig && dif > 0 && sig > 0;
  // 条件2：MA20在MA60上方（中期趋势向上）
  var ma20Above60 = m20 > m60;
  // 条件3：非低波动（避开震荡市）
  var buySignal = macdGoldX && ma20Above60 && !lowVolatility;

  // ── 加仓条件（回调至MA20附近+缩量）─────────────
  var nearMA20 = cur >= m20 * 0.985 && cur <= m20 * 1.015;
  var volShrink = curV < avgVol20 * 0.85;
  var addSignal = nearMA20 && volShrink && !lowVolatility;

  // ── 卖出条件（优化后）─────────────────────────
  // 信号1：MACD死叉（dif下穿sig）→ 比MA60死叉快1-2周
  var macdDeadX = dif_1 >= sig_1 && dif < sig;
  // 信号2：MACD顶背离（价格新高但dif没新高）+ 放量
  var priceHigh = cur >= Math.max.apply(null, closes.slice(-20));
  var difNotHigh = dif < Math.max.apply(null, macd.dif.slice(-20)) * 0.95;
  var topDivergence = priceHigh && difNotHigh && curV > avgVol20 * 1.3;
  // 信号3：跌破MA20且放量（确认跌破）
  var belowMA20 = cur < m20 && curV > avgVol20 * 1.3;
  // 信号4：偏离MA20超15%且放量滞涨
  var deviation = (cur - m20) / m20 * 100;
  var overBought = deviation > 15 && curV > avgVol20 * 1.5 && cur < closes[idx-1];

  var sellSignal = macdDeadX || topDivergence || belowMA20 || overBought;

  // ── 持仓状态 ──────────────────────────────────
  var posStatus = '空仓';
  if (dif > 0 && sig > 0 && m20 > m60 && !lowVolatility) {
    posStatus = '上升趋势(持仓)';
  } else if (dif < 0 || m20 < m60) {
    posStatus = '下降趋势(空仓)';
  } else {
    posStatus = '震荡观望';
  }

  return {
    date: data[idx].date,
    price: cur,
    m20: m20, m60: m60,
    dif: dif, sig: sig, hist: hist,
    atrPct: atrPct,
    lowVolatility: lowVolatility,
    macdGoldX: macdGoldX,
    macdDeadX: macdDeadX,
    topDivergence: topDivergence,
    deviation: deviation,
    buySignal: buySignal,
    addSignal: addSignal,
    sellSignal: sellSignal,
    posStatus: posStatus,
  };
}

// ── 回测引擎 ───────────────────────────────────
function backtest(data, name, initialCapital) {
  var capital = initialCapital;
  var position = 0;
  var avgCost = 0;
  var peak = initialCapital;
  var maxDD = 0;
  var trades = [];
  var equity = [];

  for (var i = 70; i < data.length; i++) {
    var sig = analyzeOptimized(data, i);
    if (!sig) { equity.push(capital + position * data[i].close); continue; }

    var price = data[i].close;
    var date = data[i].date;

    // ── 买入 ──
    if (position === 0 && sig.buySignal) {
      var shares60 = Math.floor(capital * 0.6 / price);
      if (shares60 > 0) {
        avgCost = price;
        position = shares60;
        capital -= shares60 * price;
        trades.push({
          type:'BUY', date:date, price:price, shares:shares60,
          value:shares60*price,
          reason:'MACD零轴上金叉+MA20>MA60-首次建仓60%',
          m20:sig.m20.toFixed(3), m60:sig.m60.toFixed(3),
          atr:sig.atrPct.toFixed(2)+'%',
        });
      }
    }

    // ── 加仓 ──
    if (position > 0 && sig.addSignal && capital > 0) {
      var addShares = Math.floor(capital * 0.5 / price);
      if (addShares > 0) {
        avgCost = (position * avgCost + addShares * price) / (position + addShares);
        position += addShares;
        capital -= addShares * price;
        trades.push({
          type:'BUY', date:date, price:price, shares:addShares,
          value:addShares*price, reason:'回调MA20缩量-加仓',
        });
      }
    }

    // ── 卖出 ──
    if (position > 0) {
      var shouldSell = false;
      var sellReason = '';

      if (sig.macdDeadX) {
        shouldSell = true;
        sellReason = 'MACD死叉-清仓';
      } else if (sig.topDivergence) {
        shouldSell = true;
        sellReason = 'MACD顶背离-清仓';
      } else if (sig.belowMA20) {
        shouldSell = true;
        sellReason = '跌破MA20放量-清仓';
      } else if (sig.overBought) {
        // 部分止盈50%
        var halfPos = Math.floor(position * 0.5);
        if (halfPos > 0 && !trades[trades.length-1].profitTaken) {
          capital += halfPos * price;
          position -= halfPos;
          trades.push({
            type:'SELL', date:date, price:price, shares:halfPos,
            value:halfPos*price,
            pnl:((price-avgCost)/avgCost*100).toFixed(2)+'%',
            reason:'偏离MA20>'+sig.deviation.toFixed(1)+'%-止盈50%',
            profitTaken:true,
          });
        }
      }

      if (shouldSell) {
        capital += position * price;
        var pnl = ((price - avgCost) / avgCost * 100).toFixed(2);
        trades.push({
          type:'SELL', date:date, price:price, shares:position,
          value:position*price, pnl:pnl+'%', reason:sellReason,
        });
        position = 0; avgCost = 0;
      }
    }

    equity.push(capital + position * data[i].close);
    var curV = equity[equity.length-1];
    if (curV > peak) peak = curV;
    var dd = (peak - curV) / peak * 100;
    if (dd > maxDD) maxDD = dd;
  }

  // 强制平仓
  if (position > 0) {
    var lastP = data[data.length-1].close;
    capital += position * lastP;
    trades.push({
      type:'SELL', date:data[data.length-1].date, price:lastP,
      shares:position, value:position*lastP,
      pnl:((lastP-avgCost)/avgCost*100).toFixed(2)+'%',
      reason:'回测结束强制平仓',
    });
  }

  return { equity:equity, trades:trades, finalValue:capital, peak:peak, maxDD:maxDD };
}

function buyHold(data, ICAP) {
  var firstP = data[0].close, lastP = data[data.length-1].close;
  var shares = Math.floor(ICAP / firstP);
  var cost = shares * firstP;
  var finalV = shares * lastP;
  var years = (new Date(data[data.length-1].date) - new Date(data[0].date)) / (365.25 * 864e5);
  return { cost:cost, finalV:finalV, years:years };
}

function stats(equity, ICAP, maxDD) {
  var finalV = equity[equity.length-1];
  var totalRet = (finalV - ICAP) / ICAP;
  var n = equity.length;
  var years = n / 252;
  var cagr = Math.pow(finalV / ICAP, 1/years) - 1;
  var rets = [];
  for (var i=1; i<equity.length; i++) rets.push((equity[i]-equity[i-1])/equity[i-1]);
  var avgR = rets.reduce(function(a,b){return a+b;},0)/rets.length;
  var stdR = Math.sqrt(rets.reduce(function(a,b){return a+(b-avgR)*(b-avgR);},0)/rets.length);
  var annStd = stdR * Math.sqrt(252);
  var sharpe = annStd > 0 ? (cagr - 0.03) / annStd : 0;
  var winRate = rets.filter(function(r){return r>0;}).length / rets.length;
  return {finalV:finalV, totalRet:totalRet, cagr:cagr, sharpe:sharpe, winRate:winRate, maxDD:maxDD};
}

// ── 主程序 ───────────────────────────────────
async function main() {
  console.log('\n' + '='.repeat(70));
  console.log('  双均线策略优化版 v2（MACD+ATR过滤）');
  console.log('  标的: 沪深300ETF (510300)');
  console.log('  初始资金: ¥' + ICAP);
  console.log('='.repeat(70));

  process.stdout.write('>> 获取数据中... ');
  var rawData = await fetchKline('510300', 'SH');
  await sleep(500);
  console.log(rawData.length + '条原始数据');

  var data = rawData.filter(function(d){ return d.date >= '2018-01-01'; });
  console.log('>> 有效数据: ' + data.length + '条 (' + data[0].date + ' ~ ' + data[data.length-1].date + ')\n');

  if (data.length < 1000) { console.log('数据不足'); return; }

  var optR = backtest(data, '沪深300ETF', ICAP);
  var optS = stats(optR.equity, ICAP, optR.maxDD);
  var bh = buyHold(data, ICAP);

  var buyTrades = optR.trades.filter(function(t){return t.type==='BUY';});
  var sellTrades = optR.trades.filter(function(t){return t.type==='SELL';});

  console.log('='.repeat(70));
  console.log('  回测结果  |  ' + data[0].date + ' ~ ' + data[data.length-1].date);
  console.log('  数据区间: ' + data.length + '个交易日');
  console.log('='.repeat(70));

  console.log('\n  ┌──────────────────┬─────────────────┬─────────────────┐');
  console.log('  │ 指标             │  优化版v2       │     买入持有     │');
  console.log('  ├──────────────────┼─────────────────┼─────────────────┤');
  console.log('  │ 期末资金         │ ' + optS.finalV.toFixed(0).padStart(15) + ' │ ' + bh.finalV.toFixed(0).padStart(15) + ' │');
  console.log('  │ 总收益率         │ ' + (optS.totalRet*100).toFixed(2).padStart(14) + '% │ ' + ((bh.finalV/bh.cost-1)*100).toFixed(2).padStart(14) + '% │');
  console.log('  │ 年化收益率(CAGR) │ ' + (optS.cagr*100).toFixed(2).padStart(14) + '% │ ' + (Math.pow(bh.finalV/bh.cost,1/bh.years)-1)*100+'%'.padStart(14) + ' │');
  console.log('  │ 最大回撤         │ ' + optS.maxDD.toFixed(2).padStart(14) + '% │       —        │');
  console.log('  │ 夏普比率         │ ' + optS.sharpe.toFixed(2).padStart(15) + ' │       —        │');
  console.log('  │ 日胜率           │ ' + (optS.winRate*100).toFixed(1).padStart(14) + '% │       —        │');
  console.log('  │ 交易次数         │ ' + (buyTrades.length+sellTrades.length).toString().padStart(14) + '次 │       —        │');
  console.log('  └──────────────────┴─────────────────┴─────────────────┘');

  var diff = optS.finalV - bh.finalV;
  console.log('\n  💡 优化版 vs 买入持有: ' + (diff>=0?'+':'') + diff.toFixed(0) + '元 (' + (diff>=0?'跑赢':'跑输') + Math.abs(diff)/bh.finalV*100+'%)');

  // ── 交易记录 ──
  console.log('\n  完整交易记录:');
  console.log('  ' + '-'.repeat(70));
  for (var ti = 0; ti < optR.trades.length; ti++) {
    var t = optR.trades[ti];
    if (t.type === 'BUY') {
      console.log('  ' + t.date + ' 【买入】 ' + t.shares.toLocaleString() + '股 @ ¥' + t.price.toFixed(3) + '  ' + t.reason);
    } else {
      console.log('  ' + t.date + ' 【卖出】 ' + t.shares.toLocaleString() + '股 @ ¥' + t.price.toFixed(3) + '  ' + (t.pnl||'') + '  ' + t.reason);
    }
  }

  // ── 年度对比 ──
  console.log('\n' + '-'.repeat(70));
  console.log('  年度收益明细');
  console.log('-'.repeat(70));

  var yearly = {};
  for (var yi = 0; yi < optR.equity.length; yi++) {
    var yr = data[yi+70].date.substring(0,4);
    if (!yearly[yr]) yearly[yr] = { equity: [], bhStart: null, bhEnd: null };
    yearly[yr].equity.push(optR.equity[yi]);
  }
  var bhShares = Math.floor(ICAP / data[0].close);
  for (var yi2 = 0; yi2 < data.length; yi2++) {
    var yr2 = data[yi2].date.substring(0,4);
    if (!yearly[yr2]) continue;
    if (yearly[yr2].bhStart === null) yearly[yr2].bhStart = data[yi2].close;
    yearly[yr2].bhEnd = data[yi2].close;
  }
  var years = Object.keys(yearly).sort();
  for (var yi3 = 0; yi3 < years.length; yi3++) {
    var yr3 = years[yi3];
    var ys = yearly[yr3];
    var stratRet = ys.equity.length > 1 ? (ys.equity[ys.equity.length-1] - ys.equity[0]) / ys.equity[0] * 100 : 0;
    var bhRet = ys.bhStart ? (ys.bhEnd - ys.bhStart) / ys.bhStart * 100 : 0;
    var flag = stratRet >= 0 ? '+' : '';
    var flag2 = bhRet >= 0 ? '+' : '';
    console.log('  ' + yr3 + '年  优化版: ' + flag + stratRet.toFixed(1) + '%  买入持有: ' + flag2 + bhRet.toFixed(1) + '%');
  }

  // ── 对比原始版 ──
  console.log('\n' + '='.repeat(70));
  console.log('  优化效果对比（vs原始双均线）');
  console.log('='.repeat(70));
  console.log('  优化点：');
  console.log('  1. 买入：MACD零轴上金叉（更快识别趋势）');
  console.log('  2. 卖出：MACD死叉（比MA60死叉快1-2周）');
  console.log('  3. ATR过滤：ATR<1.5%时视为震荡，空仓观望');
  console.log('');
  console.log('  原始版：总收益 -9.6%  最大回撤 11.1%');
  console.log('  优化版：总收益 ' + (optS.totalRet*100).toFixed(1) + '%  最大回撤 ' + optS.maxDD.toFixed(1) + '%');

  // 保存
  var summary = {
    strategy: { finalValue: optS.finalV, totalRet: (optS.totalRet*100).toFixed(2)+'%', cagr: (optS.cagr*100).toFixed(2)+'%', maxDD: optS.maxDD.toFixed(2)+'%', sharpe: optS.sharpe.toFixed(2), winRate: (optS.winRate*100).toFixed(1)+'%', tradeCount: buyTrades.length+sellTrades.length },
    buyhold: { finalValue: bh.finalV, totalRet: ((bh.finalV/bh.cost-1)*100).toFixed(2)+'%', cagr: (Math.pow(bh.finalV/bh.cost,1/bh.years)-1)*100+'%' },
    dataRange: data[0].date + ' ~ ' + data[data.length-1].date,
  };
  fs.writeFileSync(path.join(SCRIPT_DIR, 'ma_double_optimized_result.json'), JSON.stringify(summary, null, 2), 'utf8');
  console.log('\n[OK] 结果已保存: ma_double_optimized_result.json');
}

main().catch(console.error);
