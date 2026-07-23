// 获取4月20日持仓数据用于复盘
var https = require('https');

var holdings = [
  { code: '159259', name: '成长ETF', buyPrice: 1.270, shares: 15800 },
  { code: '515700', name: '新能源车ETF', buyPrice: 2.703, shares: 7400 },
  { code: '513120', name: '港股创新药ETF', buyPrice: 1.314, shares: 15300 },
  { code: '513100', name: '纳指ETF', buyPrice: 1.902, shares: 10500 },
  { code: '518880', name: '黄金ETF', buyPrice: 10.029, shares: 2000 }
];

// 昨日收盘价（4月17日）
var prevPrices = {
  '159259': 1.270, '515700': 2.703, '513120': 1.314,
  '513100': 1.892, '518880': 10.029
};

var indices = [
  { code: 'sh000001', name: '上证指数' },
  { code: 'sz399006', name: '创业板指' },
  { code: 'sh000300', name: '沪深300' },
  { code: 'sh000688', name: '科创50' }
];

function getMarket(code) {
  if (code.startsWith('5') || code.startsWith('0')) return 'sh';
  if (code.startsWith('1')) return 'sz';
  return 'sh';
}

function fetchKline(code, limit) {
  return new Promise(function(resolve) {
    var market = getMarket(code);
    var secid = market + code;
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + secid + ',day,,,' + limit + ',qfq';
    https.get(url, {headers: {'Referer': 'https://gu.qq.com'}}, function(r) {
      var chunks = [];
      r.on('data', function(c) { chunks.push(c); });
      r.on('end', function() {
        try {
          var raw = Buffer.concat(chunks).toString('utf8');
          var j = JSON.parse(raw);
          var data = j.data[secid];
          var days = data.qfqday || data.day || [];
          var last = days[days.length - 1];
          var prev = days[days.length - 2];
          resolve({
            date: last[0],
            close: parseFloat(last[2]),
            open: parseFloat(last[1]),
            high: parseFloat(last[3]),
            low: parseFloat(last[4]),
            prevClose: prev ? parseFloat(prev[2]) : null
          });
        } catch(e) { resolve(null); }
      });
    }).on('error', function() { resolve(null); });
  });
}

function calcMA(closes, period) {
  var n = closes.length;
  if (n < period) return null;
  var sum = 0;
  for (var i = n - period; i < n; i++) sum += closes[i];
  return sum / period;
}

function calcMACD(closes) {
  var ema12 = closes[closes.length-1];
  var ema26 = closes[closes.length-1];
  var k12 = 2 / 13, k26 = 2 / 27;
  for (var i = closes.length - 2; i >= 0; i--) {
    ema12 = closes[i] * k12 + ema12 * (1 - k12);
    ema26 = closes[i] * k26 + ema26 * (1 - k26);
  }
  var dif = ema12 - ema26;
  var signal = dif * 0.2;
  var bar = (dif - signal) * 2;
  return { dif: dif, signal: signal, bar: bar };
}

async function main() {
  console.log('=== 2026-04-20 持仓复盘数据 ===\n');
  
  // 获取指数
  console.log('--- 指数数据 ---\n');
  var indexData = {};
  for (var i = 0; i < indices.length; i++) {
    var idx = indices[i];
    var d = await fetchKline(idx.code, 25);
    if (d && d.prevClose) {
      var pct1 = ((d.close / d.prevClose) - 1) * 100;
      var closes = []; // 需要重建
      indexData[idx.name] = { close: d.close, pct1d: pct1 };
      console.log(idx.name + ' 收=' + d.close.toFixed(2) + ' 今日' + pct1.toFixed(2) + '%');
    }
    await new Promise(function(c) { setTimeout(c, 300); });
  }
  
  // 获取持仓数据
  console.log('\n--- 持仓数据 ---\n');
  var holdingsData = [];
  for (var i = 0; i < holdings.length; i++) {
    var h = holdings[i];
    var d = await fetchKline(h.code, 25);
    if (!d) { console.log(h.code + ' ❌'); await new Promise(function(c){setTimeout(c,300);}); continue; }
    
    // 获取25天数据计算MA20
    var d2 = await fetchKline(h.code, 25);
    var closes = [];
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + getMarket(h.code) + h.code + ',day,,,25,qfq';
    var data = await new Promise(function(resolve) {
      https.get(url, {headers:{'Referer':'https://gu.qq.com'}}, function(r) {
        var chunks = [];
        r.on('data', function(c){chunks.push(c);});
        r.on('end', function(){
          try {
            var raw = Buffer.concat(chunks).toString('utf8');
            var j = JSON.parse(raw);
            var sec = j.data[getMarket(h.code)+h.code];
            var days = sec.qfqday || sec.day || [];
            resolve(days.map(function(d){return parseFloat(d[2]);}));
          } catch(e){resolve([]);}
        });
      }).on('error', function(){resolve([]);});
    });
    var ma20 = calcMA(data, 20);
    var macd = calcMACD(data);
    var pct1d = d.prevClose ? ((d.close / d.prevClose) - 1) * 100 : 0;
    var pctHold = ((d.close / h.buyPrice) - 1) * 100;
    var profit = (d.close - h.buyPrice) * h.shares;
    
    holdingsData.push({
      code: h.code,
      name: h.name,
      buyPrice: h.buyPrice,
      shares: h.shares,
      todayClose: d.close,
      prevClose: d.prevClose,
      ma20: ma20,
      macd: macd,
      pct1d: pct1d,
      pctHold: pctHold,
      profit: profit,
      aboveMA20: d.close > ma20
    });
    
    var maDir = ma20 ? (data[data.length-1] > data[data.length-20] ? '↗' : '↘') : '-';
    console.log(h.name + ' 收=' + d.close.toFixed(3) + ' 今日' + pct1d.toFixed(2) + '% 累计' + pctHold.toFixed(2) + '% MA20=' + (ma20?ma20.toFixed(3):'N/A') + maDir + ' 盈亏¥' + profit.toFixed(2));
    await new Promise(function(c) { setTimeout(c, 300); });
  }
  
  // 总览
  var totalAssets = 0, totalCost = 0, todayProfit = 0, holdProfit = 0;
  holdingsData.forEach(function(h) {
    totalAssets += h.todayClose * h.shares;
    totalCost += h.buyPrice * h.shares;
    todayProfit += h.profit * (h.pct1d / h.pctHold); // 当日比例
    holdProfit += h.profit;
  });
  totalAssets += 291.70; // 现金
  totalCost += 589; // 原始现金
  
  console.log('\n=== 账户总览 ===');
  console.log('持仓市值: ¥' + totalAssets.toFixed(2));
  console.log('现金: ¥291.70');
  console.log('总资产: ¥' + (totalAssets + 291.70).toFixed(2));
  console.log('累计收益率: ' + (((totalAssets+291.70-100000)/100000)*100).toFixed(2) + '%');
}
main();
