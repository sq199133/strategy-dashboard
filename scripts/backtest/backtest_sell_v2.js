// backtest_sell_v2.js
// 回测：对比 连续N天绿柱(N=1,2,3,4) vs MACD死叉 vs 无MACD
// 数据：沪深300ETF (510300) 东方财富 2018-2026
var fs   = require('fs');

// ── 指标 ────────────────────────────────────────
function SMA(prices, n) {
  var out = new Array(prices.length).fill(null);
  for (var i = n-1; i < prices.length; i++) {
    var s = 0;
    for (var j = i-n+1; j <= i; j++) s += prices[j];
    out[i] = s / n;
  }
  return out;
}

function EMA(prices, n) {
  var k = 2/(n+1);
  var out = new Array(prices.length).fill(null);
  var seed = 0;
  for (var i = 0; i < n; i++) seed += prices[i];
  out[n-1] = seed / n;
  for (var i = n; i < prices.length; i++)
    out[i] = prices[i] * k + out[i-1] * (1-k);
  return out;
}

function MACD(prices, f, s, sig) {
  f=f||12; s=s||26; sig=sig||9;
  var ef=EMA(prices,f), es=EMA(prices,s);
  var dif=new Array(prices.length).fill(null);
  for(var i=s-1;i<prices.length;i++) dif[i]=ef[i]-es[i];
  var sk=2/(sig+1);
  var se=new Array(prices.length).fill(null);
  se[s-1]=dif[s-1];
  for(var i=s;i<dif.length;i++) se[i]=dif[i]*sk+se[i-1]*(1-sk);
  var hist=dif.map(function(v,i){return v===null?null:v-se[i];});
  return {dif:dif, sig:se, hist:hist};
}

// ── 加载数据（东方财富3段式）────────────────────
async function fetchEM(code, market, beg, end, lmt) {
  var secid = market === 'SZ' ? '0.' + code : '1.' + code;
  var url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get' +
    '?secid=' + secid +
    '&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61' +
    '&klt=101&fqt=0&beg=' + beg + '&end=' + end + '&lmt=' + lmt;
  try {
    var r = await fetch(url, {signal:AbortSignal.timeout(10000)});
    var j = await r.json();
    var klines = (j.data && j.data.klines) ? j.data.klines : [];
    return klines.map(function(k){
      var p = k.split(',');
      return {date:p[0], close:+p[2]};
    });
  } catch(e) { return []; }
}

async function loadData() {
  var [s1,s2,s3] = await Promise.all([
    fetchEM('510300','SH','20180101','20201231',200),
    fetchEM('510300','SH','20210101','20231231',200),
    fetchEM('510300','SH','20240101','20260417',200)
  ]);
  var all = s1.concat(s2).concat(s3);
  var seen={};
  all = all.filter(function(d){
    if(seen[d.date]) return false;
    seen[d.date]=true;
    return true;
  });
  all.sort(function(a,b){return a.date<b.date?-1:1;});
  return all;
}

// ── 主回测函数（每日盯市，正确计算最大回撤）──────────────
function runBacktest(data, sellRule) {
  var C = data.map(function(d){return d.close;});
  var ma20 = SMA(C, 20);
  var macd = MACD(C, 12, 26, 9);

  var cash  = 100000;
  var shares = 0;
  var entryPrice = 0;
  var trades = [];

  // 权益曲线（每日）
  var equityCurve = [];

  for (var i = 1; i < data.length; i++) {
    var price = C[i];
    var ma = ma20[i];
    var d  = macd.dif[i],  dP1  = macd.dif[i-1];
    var s  = macd.sig[i],  sP1  = macd.sig[i-1];
    var h  = macd.hist[i], hP1  = macd.hist[i-1];
    var h2 = i>=2 ? macd.hist[i-2] : null;
    var h3 = i>=3 ? macd.hist[i-3] : null;
    var h4 = i>=4 ? macd.hist[i-4] : null;

    // 权益（每日收盘价盯市）
    var equity = shares > 0 ? shares * price : cash;
    equityCurve.push({date:data[i].date, equity:equity});

    // ── 买入条件（统一）─────────────
    var buySig = (price > ma) &&
                 (ma >= ma20[i-1]) &&
                 (dP1 <= sP1 && d > s) &&
                 (d > 0 && s > 0);

    // ── 卖出条件─────────────
    var sellSig = false;
    if (sellRule === 'none') {
      sellSig = (shares > 0) && (price < ma);
    } else if (sellRule === 'deathX') {
      sellSig = (shares > 0) && (dP1 >= sP1 && d < s);
    } else if (sellRule === 'green1') {
      sellSig = (shares > 0) && (h < 0);
    } else if (sellRule === 'green2') {
      sellSig = (shares > 0) && (h < 0 && hP1 < 0);
    } else if (sellRule === 'green3') {
      sellSig = (shares > 0) && (h < 0 && hP1 < 0 && h2 < 0);
    } else if (sellRule === 'green4') {
      sellSig = (shares > 0) && (h < 0 && hP1 < 0 && h2 < 0 && h3 < 0);
    }

    // ── 执行 ──────────────────────
    if (buySig && shares === 0) {
      shares = Math.floor(cash / price);
      cash = cash - shares * price;
      entryPrice = price;
      trades.push({ date:data[i].date, action:'BUY', price:price, shares:shares, equity:equity.toFixed(2) });
    }
    if (sellSig && shares > 0) {
      var sellPrice = price;
      cash = cash + shares * sellPrice;
      var ret = (sellPrice - entryPrice) / entryPrice * 100;
      trades.push({ date:data[i].date, action:'SELL', price:sellPrice, shares:shares, ret:ret.toFixed(2)+'%', equity:cash.toFixed(2) });
      shares = 0;
    }
  }

  // 最终平仓
  if (shares > 0) {
    var finalPrice = C[C.length-1];
    cash = cash + shares * finalPrice;
    equityCurve[equityCurve.length-1] = {date:data[data.length-1].date, equity:cash};
    var ret = (finalPrice - entryPrice) / entryPrice * 100;
    trades.push({ date:data[data.length-1].date, action:'SELL', price:finalPrice, shares:shares, ret:ret.toFixed(2)+'%', equity:cash.toFixed(2) });
  }

  // ── 统计 ──────────────────────
  var buyCount = trades.filter(function(t){return t.action==='BUY'}).length;
  var totalDays = data.length - 20; // 去除MA20预热期
  var years = totalDays / 250;
  var totalReturn = (cash - 100000) / 100000 * 100;
  var annualized = (Math.pow(cash/100000, 1/years) - 1) * 100;

  // 最大回撤（每日权益曲线）
  var peak = 100000, maxDD = 0;
  for (var ei = 0; ei < equityCurve.length; ei++) {
    if (equityCurve[ei].equity > peak) peak = equityCurve[ei].equity;
    var dd = (peak - equityCurve[ei].equity) / peak * 100;
    if (dd > maxDD) maxDD = dd;
  }

  return {
    rule: sellRule,
    totalReturn: totalReturn.toFixed(2),
    annualized: annualized.toFixed(2),
    maxDrawdown: maxDD.toFixed(2),
    trades: buyCount,
    finalCash: cash.toFixed(2)
  };
}

// ── 主程序 ───────────────────────────────────────
async function main() {
  console.log('正在加载沪深300ETF(510300)历史数据...');
  var data = await loadData();
  console.log('加载到 ' + data.length + ' 条K线  ' + data[0].date + ' ~ ' + data[data.length-1].date + '\n');

  var rules = [
    {id:'none',   label:'仅MA20跌破(无MACD)'},
    {id:'deathX', label:'MACD死叉'},
    {id:'green1', label:'当天绿柱(无连续要求)'},
    {id:'green2', label:'连续2天绿柱'},
    {id:'green3', label:'连续3天绿柱(策略v3.1)'},
    {id:'green4', label:'连续4天绿柱'},
  ];

  console.log('======================================================================');
  console.log('  卖出规则回测  |  沪深300ETF  |  2018-2026  |  买入条件统一');
  console.log('======================================================================');
  console.log('  卖出规则                      总收益    年化     最大回撤   交易次数');
  console.log('  ' + '-'.repeat(72));

  var results = [];
  for (var i = 0; i < rules.length; i++) {
    var r = runBacktest(data, rules[i].id);
    console.log(
      '  ' + rules[i].label.padEnd(30) +
      '  ' + r.totalReturn.padStart(8) + '%' +
      '  ' + r.annualized.padStart(7) + '%' +
      '  ' + r.maxDrawdown.padStart(9) + '%' +
      '  ' + r.trades + '笔'
    );
    results.push(r);
  }

  // 买入持有基准
  var C = data.map(function(d){return d.close;});
  var bh_ret = (C[C.length-1] - C[0]) / C[0] * 100;
  var bh_years = (data.length - 20) / 250;
  var bh_ann = (Math.pow(C[C.length-1]/C[0], 1/bh_years)-1)*100;
  console.log('  ' + '买入持有'.padEnd(30) + '  ' + bh_ret.toFixed(2).padStart(8) + '%' +
    '  ' + bh_ann.toFixed(2).padStart(7) + '%  ' + '基准'.padStart(9) + '\n');

  console.log('======================================================================');
  console.log('结论分析：');
  var best = results.reduce(function(a,b){return parseFloat(a.annualized)>parseFloat(b.annualized)?a:b;});
  var noMacd = results.find(function(r){return r.rule==='none';});
  var diff = (parseFloat(best.annualized)-parseFloat(noMacd.annualized)).toFixed(2);
  console.log('  最佳卖出规则: ' + best.rule + ' (年化' + best.annualized + '% / 回撤' + best.maxDrawdown + '% / ' + best.trades + '笔)');
  console.log('  vs 无MACD: ' + (diff>=0?'+' : '')+ diff + '%');
  console.log('  vs 买入持有: ' + (parseFloat(best.annualized)-bh_ann).toFixed(2) + '%\n');

  // 保存结果
  fs.writeFileSync('D:/QClaw_Trading/scripts/backtest/backtest_sell_v2_result.json', JSON.stringify(results, null, 2));
  console.log('[OK] 结果已保存');
}

main().catch(console.error);
