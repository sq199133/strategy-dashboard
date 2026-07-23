const https = require('https');

const ITEMS = [
  {code:'sh000001', name:'上证指数'},
  {code:'sz399006', name:'创业板指'},
  {code:'sh000001', name:'上证指数60'},
  {code:'sh510300', name:'沪深300ETF'},
  {code:'sz159915', name:'创业板ETF'},
  {code:'sh159681', name:'创业板50ETF'},
  {code:'sh512770', name:'战略新兴ETF'},
  {code:'sh512220', name:'TMTETF'},
  {code:'sh516390', name:'新能源汽车ETF'},
  {code:'sh513100', name:'纳指ETF'},
  {code:'sh588080', name:'科创50ETF易方达'},
];

function fetch(code, count) {
  return new Promise(function(resolve) {
    var c = count || 60;
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=x&param='+code+',day,2025-10-01,2027-01-01,'+c+',qfq';
    https.get(url, {headers:{'Referer':'https://gu.qq.com'}}, function(r) {
      var d = '';
      r.on('data', function(s){ d += s; });
      r.on('end', function(){
        try {
          var txt = d.replace(/^[^=]+=/, '');
          var j = JSON.parse(txt);
          var key = Object.keys(j.data)[0];
          var arr = j.data[key].qfqday || j.data[key].day || [];
          resolve(arr.map(function(p){ return {date:p[0], close:parseFloat(p[2]), high:parseFloat(p[3]), low:parseFloat(p[4]), vol:parseFloat(p[5])}; }));
        } catch(e) { resolve([]); }
      });
    }).on('error', function(){ resolve([]); });
  });
}

function calcMA(arr, period) {
  return arr.map(function(v, i){
    if (i < period - 1) return null;
    var sum = 0;
    for (var j = 0; j < period; j++) sum += arr[i-j].close;
    return sum / period;
  });
}

function calcMACD(closes, fast, slow, signal) {
  var ema = function(data, p) {
    var k = 2 / (p + 1);
    var e = [data[0]];
    for (var i = 1; i < data.length; i++) e.push(data[i] * k + e[i-1] * (1-k));
    return e;
  };
  var ef = ema(closes, fast);
  var es = ema(closes, slow);
  var dif = ef.map(function(v, i){ return v - es[i]; });
  var k = 2 / (signal + 1);
  var dea = new Array(dif.length).fill(null);
  dea[slow - 1] = dif[slow - 1];
  for (var i = slow; i < dif.length; i++) dea[i] = dif[i] * k + dea[i-1] * (1 - k);
  return { dif: dif, dea: dea };
}

function trend(arr, period) {
  if (arr.length < period) return '—';
  var cur = arr[arr.length-1];
  var prev = arr[arr.length-period];
  if (cur === null || prev === null) return '—';
  if (cur > prev) return '↗ 向上';
  if (cur < prev) return '↘ 向下';
  return '→ 走平';
}

async function run() {
  for (var i = 0; i < ITEMS.length; i++) {
    var item = ITEMS[i];
    var arr = await fetch(item.code);
    if (arr.length < 26) { console.log(item.name + ': 数据不足'); await new Promise(r=>setTimeout(r,200)); continue; }
    var closes = arr.map(function(v){ return v.close; });
    var ma5 = calcMA(arr, 5);
    var ma20 = calcMA(arr, 20);
    var ma50 = calcMA(arr, 50);
    var macd = calcMACD(closes, 12, 26, 9);

    var last = arr[arr.length-1];
    var prev = arr[arr.length-2];
    var chgPct = ((last.close - prev.close) / prev.close * 100).toFixed(2);
    var price = last.close;
    var ma20v = ma20[ma20.length-1];
    var ma50v = ma50[ma50.length-1];
    var dif = macd.dif[macd.dif.length-1];
    var dea = macd.dea[macd.dea.length-1];
    var difP = macd.dif[macd.dif.length-2];
    var deaP = macd.dea[macd.dea.length-2];
    var hist = dif - dea;

    var maStatus = price > ma20v ? '✅站上' : '❌跌破';
    var maDir = trend(ma20, 5);
    var macdZero = dif > 0 && dea > 0 ? '零轴上' : '零轴下';
    var goldX = difP < deaP && dif > dea ? '✅金叉' : '—';
    var deathX = difP > deaP && dif < dea ? '❌死叉' : '—';

    var score = 0;
    if (price > ma20v) score += 1;
    if (ma20v > ma50v) score += 1;
    if (price > ma20v && ma20v > ma50v) score += 2;
    if (trend(ma20, 5) === '↗ 向上') score += 1;
    if (dif > 0) score += 1;
    if (goldX === '✅金叉' && dif > 0) score += 2;
    if (dif > dea && difP <= deaP) score += 1;
    var stars = score >= 11 ? '⭐⭐⭐⭐⭐' : score >= 9 ? '⭐⭐⭐⭐' : score >= 6 ? '⭐⭐⭐' : score >= 4 ? '⭐⭐' : '⭐';

    console.log('【' + item.name + '】 ' + last.date);
    console.log('  收盘:' + price + '  涨跌:' + chgPct + '%');
    console.log('  MA20:' + ma20v.toFixed(2) + ' MA50:' + ma50v.toFixed(2) + '  MA20' + maDir);
    console.log('  MACD: DIF=' + dif.toFixed(4) + ' DEA=' + (dea||0).toFixed(4) + ' 柱=' + hist.toFixed(4) + ' [' + macdZero + ']');
    console.log('  信号: ' + maStatus + 'MA20  ' + (goldX||deathX||'—') + '  评分:' + score + '分 ' + stars);
    console.log('');
    await new Promise(function(r){ setTimeout(r, 250); });
  }
}

run();
