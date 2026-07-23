// ============================================================
// 双均线策略（MA20+MA60）回测
// 标的：沪深300ETF (510300)
// 规则：双均线趋势跟踪，60%建仓+40%预留加仓
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
  // 去重+排序
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

function MACD(prices,f,s,sig) {
  f=f||12;s=s||26;sig=sig||9;
  var ef=EMA(prices,f), es=EMA(prices,s);
  var dif=new Array(prices.length).fill(null);
  for(var i=s-1;i<prices.length;i++) dif[i]=ef[i]-es[i];
  var sk=2/(sig+1),se=new Array(prices.length).fill(null);
  se[s-1]=dif[s-1];
  for(var i=s;i<dif.length;i++) se[i]=dif[i]*sk+se[i-1]*(1-sk);
  var hist=dif.map(function(v,i){return v===null?null:v-se[i];});
  return {dif:dif,sig:se,hist:hist};
}

function EMA(prices,n) {
  var k=2/(n+1);
  var out=new Array(prices.length).fill(null);
  var seed=0; for(var i=0;i<n;i++) seed+=prices[i];
  out[n-1]=seed/n;
  for(var i=n;i<prices.length;i++) out[i]=prices[i]*k+out[i-1]*(1-k);
  return out;
}

// ── 双均线核心策略 ────────────────────────────────
function analyzeDualMA(data, idx) {
  if (idx < 65) return null;
  var lookback = 5;

  var closes = data.slice(0, idx+1).map(function(d){return d.close;});
  var vols   = data.slice(0, idx+1).map(function(d){return d.vol;});
  var ma20   = SMA(closes, 20);
  var ma60   = SMA(closes, 60);
  var macd   = MACD(closes, 12, 26, 9);

  var cur = closes[idx];
  var curV = vols[idx];
  var avgVol20 = vols.slice(-20).reduce(function(a,b){return a+b;},0)/20;

  // 当前均线值
  var m20 = ma20[idx];
  var m20_1 = ma20[idx-1];
  var m20_2 = ma20[idx-2];
  var m20_3 = ma20[idx-3];
  var m60 = ma60[idx];
  var m60_1 = ma60[idx-1];

  // 前一根K线
  var prev2_close = closes[idx-2]; // i-2的收盘（用于"连续2天"判断）
  var prev2_vol  = vols[idx-2];

  // MACD
  var dif = macd.dif[idx];
  var dif_1 = macd.dif[idx-1];
  var sig = macd.sig[idx];
  var hist = macd.hist[idx];
  var aboveZero = dif > 0 && sig > 0;

  // ── 均线方向判断 ──
  var priceAboveMA20 = cur > m20;
  var ma20_turningUp = (m20_1 < m20_2 && m20 >= m20_1); // 从向下/走平转为向上
  var ma20AboveMA60  = m20 > m60;
  var ma60FlatOrUp   = m60 >= m60_1; // 60日均线走平或向上

  // ── 买入条件（两个同时满足）──
  // 条件1：收盘价站上MA20 + MA20拐头向上
  var cond1 = priceAboveMA20 && ma20_turningUp;
  // 条件2：MA20在MA60上方 + MA60走平/向上
  var cond2 = ma20AboveMA60 && ma60FlatOrUp;
  var buySignal = cond1 && cond2;

  // ── 加仓条件 ──
  // 价格回调至MA20附近 + 缩量 + 连续2天未有效跌破
  var nearMA20 = cur >= m20 * 0.99 && cur <= m20 * 1.01;
  var volShrink = curV < avgVol20 * 0.9;
  var prev2Above = prev2_close >= m20_1 * 0.99; // i-2收在MA20上方
  var addSignal = nearMA20 && volShrink && prev2Above;

  // ── 卖出/止损条件 ──
  // 信号1：收盘价跌破MA20 + 连续2天在下方 + 放量下跌
  var belowMA20_today = cur < m20;
  var belowMA20_prev2 = prev2_close < m20_1;
  var volBig = curV > avgVol20 * 1.5;
  var sellSignal1 = belowMA20_today && belowMA20_prev2 && volBig;

  // 信号2：MA20拐头向下 或 MA20跌破MA60（金叉变死叉）
  var ma20_turningDown = m20_1 >= m20_2 && m20 < m20_1;
  var ma20BelowMA60_now = m20 < m60;
  var ma20AboveMA60_prev = ma20[idx-1] >= m60_1;
  var deadCross = ma20BelowMA60_now && ma20AboveMA60_prev;
  var sellSignal2 = ma20_turningDown || deadCross;

  // 信号3：偏离MA20超过15% + 放量滞涨
  var deviation = (cur - m20) / m20 * 100;
  var stalling = cur < data[idx-1].close; // 今日收跌（相对昨日）
  var sellSignal3 = deviation > 15 && volBig && stalling;

  // ── 持仓状态判断 ──
  var posStatus = '空仓';
  if (m60 >= m60_1 && m20 > m60) {
    posStatus = '上升趋势'; // MA20>MA60 且 MA60向上 = 持仓信号
  } else if (m20 < m60 || m60 < m60_1) {
    posStatus = '下降趋势(空仓)';
  } else {
    posStatus = '震荡';
  }

  return {
    date: data[idx].date,
    price: cur,
    m20: m20, m20_1: m20_1, m20_2: m20_2,
    m60: m60, m60_1: m60_1,
    ma20_turningUp: ma20_turningUp,
    ma20AboveMA60: ma20AboveMA60,
    ma60FlatOrUp: ma60FlatOrUp,
    aboveZero: aboveZero,
    deviation: deviation,
    volRatio: curV / avgVol20,
    buySignal: buySignal,
    addSignal: addSignal,
    sellSignal1: sellSignal1,
    sellSignal2: sellSignal2,
    sellSignal3: sellSignal3,
    posStatus: posStatus,
  };
}

// ── 回测引擎 ───────────────────────────────────
function backtest(data, name, initialCapital) {
  var capital   = initialCapital;
  var position  = 0;
  var avgCost   = 0;
  var peak      = initialCapital;
  var maxDD     = 0;
  var trades    = [];
  var equity    = [];

  // 持仓状态
  var posPhase  = 'empty'; // 'empty' | 'partial' | 'full'
  var firstBuyDone = false; // 首次60%建仓是否完成

  for (var i = 65; i < data.length; i++) {
    var sig = analyzeDualMA(data, i);
    if (!sig) { equity.push(capital + position * data[i].close); continue; }

    var price = data[i].close;
    var date  = data[i].date;

    // ── 买入逻辑 ──
    if (position === 0 && sig.buySignal) {
      // 首次建仓60%
      var shares60 = Math.floor(capital * 0.6 / price);
      if (shares60 > 0) {
        avgCost  = price;
        position = shares60;
        capital  = capital - shares60 * price;
        posPhase = 'partial';
        firstBuyDone = true;
        trades.push({
          type:'BUY', date:date, price:price, shares:shares60,
          value:shares60*price, reason:'双均线金叉-首次建仓60%',
          m20:sig.m20.toFixed(3), m60:sig.m60.toFixed(3),
        });
      }
    }

    // ── 加仓逻辑（剩余40%分2次，每次20%）──
    if (position > 0 && sig.addSignal) {
      var remaining = capital * 0.5; // 剩余资金的一半
      var addShares = Math.floor(remaining / price);
      if (addShares > 0) {
        avgCost  = (position * avgCost + addShares * price) / (position + addShares);
        position += addShares;
        capital  -= addShares * price;
        posPhase = 'full';
        trades.push({
          type:'BUY', date:date, price:price, shares:addShares,
          value:addShares*price, reason:'回调MA20缩量-加仓20%',
          m20:sig.m20.toFixed(3),
        });
      }
    }

    // ── 卖出逻辑 ──
    if (position > 0) {
      var sellReason = '';

      // 信号1：跌破MA20 + 连续2天 + 放量 → 减仓50%
      if (sig.sellSignal1 && !trades[trades.length-1].halfSelled) {
        var halfPos = Math.floor(position * 0.5);
        capital += halfPos * price;
        position -= halfPos;
        avgCost = position > 0 ? avgCost : 0;
        trades.push({
          type:'SELL', date:date, price:price, shares:halfPos,
          value:halfPos*price,
          pnl:((price-avgCost)/avgCost*100).toFixed(2)+'%',
          reason:'跌破MA20+放量-减仓50%',
          halfSelled:true,
        });
        posPhase = position > 0 ? 'partial' : 'empty';
      }

      // 信号2：MA20拐头向下 或 MA20死叉MA60 → 清仓
      else if (sig.sellSignal2) {
        capital += position * price;
        var pnl = ((price - avgCost) / avgCost * 100).toFixed(2);
        trades.push({
          type:'SELL', date:date, price:price, shares:position,
          value:position*price, pnl:pnl+'%',
          reason:sig.ma20_turningDown?'MA20拐头向下-清仓':'MA20死叉MA60-清仓',
        });
        position=0; avgCost=0; posPhase='empty'; firstBuyDone=false;
      }

      // 信号3：偏离MA20>15% + 放量滞涨 → 止盈50%
      else if (sig.sellSignal3 && !trades[trades.length-1].profitTakeed) {
        var halfP = Math.floor(position * 0.5);
        capital += halfP * price;
        position -= halfP;
        avgCost = position > 0 ? avgCost : 0;
        trades.push({
          type:'SELL', date:date, price:price, shares:halfP,
          value:halfP*price,
          pnl:((price-avgCost)/avgCost*100).toFixed(2)+'%',
          reason:'偏离MA20>'+(sig.deviation.toFixed(1))+'%放量滞涨-止盈50%',
          profitTakeed:true,
        });
        posPhase = position > 0 ? 'partial' : 'empty';
      }
    }

    equity.push(capital + position * price);
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

// ── 买入持有基准 ────────────────────────────────
function buyHold(data, ICAP) {
  var firstP = data[0].close, lastP = data[data.length-1].close;
  var shares = Math.floor(ICAP / firstP);
  var cost   = shares * firstP;
  var finalV  = shares * lastP;
  var years  = (new Date(data[data.length-1].date) - new Date(data[0].date)) / (365.25 * 864e5);
  return { cost:cost, finalV:finalV, years:years };
}

// ── 绩效统计 ─────────────────────────────────
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
  console.log('  双均线策略（MA20+MA60）回测');
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

  var waveR = backtest(data, '沪深300ETF', ICAP);
  var waveS = stats(waveR.equity, ICAP, waveR.maxDD);
  var bh    = buyHold(data, ICAP);

  var buyTrades  = waveR.trades.filter(function(t){return t.type==='BUY';});
  var sellTrades = waveR.trades.filter(function(t){return t.type==='SELL';});

  console.log('='.repeat(70));
  console.log('  回测结果  |  ' + data[0].date + ' ~ ' + data[data.length-1].date);
  console.log('  数据区间: ' + data.length + '个交易日');
  console.log('='.repeat(70));

  console.log('\n  ┌──────────────────┬─────────────────┬─────────────────┐');
  console.log('  │ 指标             │  双均线MA20+60  │     买入持有     │');
  console.log('  ├──────────────────┼─────────────────┼─────────────────┤');
  console.log('  │ 期末资金         │ ' + waveS.finalV.toFixed(0).padStart(15) + ' │ ' + bh.finalV.toFixed(0).padStart(15) + ' │');
  console.log('  │ 总收益率         │ ' + (waveS.totalRet*100).toFixed(2).padStart(14) + '% │ ' + ((bh.finalV/bh.cost-1)*100).toFixed(2).padStart(14) + '% │');
  console.log('  │ 年化收益率(CAGR) │ ' + (waveS.cagr*100).toFixed(2).padStart(14) + '% │ ' + (Math.pow(bh.finalV/bh.cost,1/bh.years)-1)*100+'%'.padStart(14) + ' │');
  console.log('  │ 最大回撤         │ ' + waveS.maxDD.toFixed(2).padStart(14) + '% │       —        │');
  console.log('  │ 夏普比率         │ ' + waveS.sharpe.toFixed(2).padStart(15) + ' │       —        │');
  console.log('  │ 日胜率           │ ' + (waveS.winRate*100).toFixed(1).padStart(14) + '% │       —        │');
  console.log('  └──────────────────┴─────────────────┴─────────────────┘');

  var diff = waveS.finalV - bh.finalV;
  console.log('\n  💡 策略 vs 买入持有: ' + (diff>=0?'+':'') + diff.toFixed(0) + '元 (' + (diff>=0?'跑赢':'跑输') + Math.abs(diff)/bh.finalV*100+'%)');
  console.log('  💡 最大回撤对比: 策略' + waveS.maxDD.toFixed(1) + '% vs 买入持有 约' + ((1-bh.finalV/(data[data.length-1].close/data[0].close))*100).toFixed(1) + '%（估算）');

  // ── 交易统计 ──
  console.log('\n' + '-'.repeat(70));
  console.log('  交易统计');
  console.log('-'.repeat(70));
  console.log('  总交易次数: ' + (buyTrades.length + sellTrades.length) + '次 (' + buyTrades.length + '次买入 / ' + sellTrades.length + '次卖出)');
  console.log('  持仓天数: ' + waveR.trades.filter(function(t){return t.type==='SELL';}).reduce(function(a,t){ return a + (t.shares||0); }, 0) + '天（估算）');

  // 完整交易记录
  console.log('\n  完整交易记录:');
  console.log('  ' + '-'.repeat(70));
  for (var ti = 0; ti < waveR.trades.length; ti++) {
    var t = waveR.trades[ti];
    if (t.type === 'BUY') {
      console.log('  ' + t.date + ' 【买入】 ' + t.shares.toLocaleString() + '股 @ ¥' + t.price.toFixed(3) + '  理由: ' + t.reason);
    } else {
      console.log('  ' + t.date + ' 【卖出】 ' + t.shares.toLocaleString() + '股 @ ¥' + t.price.toFixed(3) + '  ' + (t.pnl||'') + '  理由: ' + t.reason);
    }
  }

  // ── 年度分析 ──
  console.log('\n' + '-'.repeat(70));
  console.log('  年度收益明细');
  console.log('-'.repeat(70));

  var yearlyStats = {};
  for (var yi = 0; yi < waveR.equity.length; yi++) {
    var yr = data[yi+65].date.substring(0,4);
    if (!yearlyStats[yr]) yearlyStats[yr] = { equity: [], bhStart: null, bhEnd: null };
    yearlyStats[yr].equity.push(waveR.equity[yi]);
  }

  // BH yearly
  var bhShares = Math.floor(ICAP / data[0].close);
  for (var yi2 = 0; yi2 < data.length; yi2++) {
    var yr2 = data[yi2].date.substring(0,4);
    if (!yearlyStats[yr2]) continue;
    if (yearlyStats[yr2].bhStart === null) yearlyStats[yr2].bhStart = data[yi2].close;
    yearlyStats[yr2].bhEnd = data[yi2].close;
  }

  var years = Object.keys(yearlyStats).sort();
  for (var yi3 = 0; yi3 < years.length; yi3++) {
    var yr3 = years[yi3];
    var ys = yearlyStats[yr3];
    var stratRet = ys.equity.length > 1
      ? (ys.equity[ys.equity.length-1] - ys.equity[0]) / ys.equity[0] * 100
      : 0;
    var bhRet = ys.bhStart ? (ys.bhEnd - ys.bhStart) / ys.bhStart * 100 : 0;
    var flag = stratRet >= 0 ? '+' : '';
    var flag2 = bhRet >= 0 ? '+' : '';
    console.log('  ' + yr3 + '年  双均线: ' + flag + stratRet.toFixed(1) + '%  买入持有: ' + flag2 + bhRet.toFixed(1) + '%');
  }

  // ── 保存结果 ──
  var summary = {
    strategy: {
      finalValue: waveS.finalV,
      totalRet: (waveS.totalRet*100).toFixed(2)+'%',
      cagr: (waveS.cagr*100).toFixed(2)+'%',
      maxDD: waveS.maxDD.toFixed(2)+'%',
      sharpe: waveS.sharpe.toFixed(2),
      winRate: (waveS.winRate*100).toFixed(1)+'%',
      tradeCount: buyTrades.length + sellTrades.length,
    },
    buyhold: {
      finalValue: bh.finalV,
      totalRet: ((bh.finalV/bh.cost-1)*100).toFixed(2)+'%',
      cagr: (Math.pow(bh.finalV/bh.cost,1/bh.years)-1)*100+'%',
    },
    dataRange: data[0].date + ' ~ ' + data[data.length-1].date,
    dataLen: data.length,
  };
  fs.writeFileSync(path.join(SCRIPT_DIR, 'ma_double_backtest_result.json'), JSON.stringify(summary, null, 2), 'utf8');
  console.log('\n[OK] 结果已保存: ma_double_backtest_result.json');
}

main().catch(console.error);
