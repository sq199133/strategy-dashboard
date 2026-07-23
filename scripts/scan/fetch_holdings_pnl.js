// 获取持仓当日+累计涨跌数据
var https = require('https');

var holdings = [
  { code: '159259', name: '成长ETF', buyPrice: 1.270, shares: 15800 },
  { code: '515700', name: '新能源车ETF', buyPrice: 2.703, shares: 7400 },
  { code: '513120', name: '港股创新药ETF', buyPrice: 1.314, shares: 15300 },
  { code: '513100', name: '纳指ETF', buyPrice: 1.902, shares: 10500 },
  { code: '518880', name: '黄金ETF', buyPrice: 10.029, shares: 2000 }
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
    https.get(url, {headers:{'Referer':'https://gu.qq.com'}}, function(r) {
      var chunks = [];
      r.on('data', function(c){chunks.push(c);});
      r.on('end', function(){
        try {
          var raw = Buffer.concat(chunks).toString('utf8');
          var j = JSON.parse(raw);
          var data = j.data[secid];
          var days = data.qfqday || data.day || [];
          var closes = days.map(function(d){return parseFloat(d[2]);});
          var last = days[days.length-1];
          var prev = days[days.length-2];
          var ma20 = closes.slice(-20).reduce(function(s,v){return s+v;},0)/20;
          var maDir = closes[closes.length-1] > closes[closes.length-20] ? '↗' : '↘';
          // MACD
          var ema12 = closes[closes.length-1], ema26 = closes[closes.length-1];
          var k12=2/13, k26=2/27;
          for(var i=closes.length-2;i>=0;i--){ema12=closes[i]*k12+ema12*(1-k12);ema26=closes[i]*k26+ema26*(1-k26);}
          var dif=ema12-ema26, signal=dif*0.2, bar=(dif-signal)*2;
          var aboveZero = dif > 0 ? '上' : '下';
          return resolve({
            close: parseFloat(last[2]),
            prevClose: parseFloat(prev[2]),
            ma20: ma20,
            maDir: maDir,
            dif: dif, signal: signal, bar: bar,
            aboveZero: aboveZero,
            closes: closes
          });
        }catch(e){resolve(null);}
      });
    }).on('error', function(){resolve(null);});
  });
}

async function main() {
  console.log('=== 2026-04-20 持仓详细数据 ===\n');
  var totalMarketValue = 0, totalCost = 0;
  var rows = [];
  
  for (var i = 0; i < holdings.length; i++) {
    var h = holdings[i];
    var d = await fetchKline(h.code, 25);
    if (!d) { console.log(h.code + ' ❌'); await new Promise(function(c){setTimeout(c,200);}); continue; }
    
    var pct1d = ((d.close / d.prevClose) - 1) * 100;
    var pctHold = ((d.close / h.buyPrice) - 1) * 100;
    var profit = (d.close - h.buyPrice) * h.shares;
    var marketValue = d.close * h.shares;
    var cost = h.buyPrice * h.shares;
    
    // 五星评分
    var score = 0;
    if (d.close > d.ma20) score += 3;
    if (d.maDir === '↗') score += 3;
    if (d.dif > 0) score += 3;
    if (pctHold > 0) score += 3;
    score += 1; // 基础分
    var stars = score >= 12 ? '⭐⭐⭐⭐⭐' : score >= 9 ? '⭐⭐⭐⭐' : score >= 6 ? '⭐⭐⭐' : score >= 3 ? '⭐⭐' : '⭐';
    
    totalMarketValue += marketValue;
    totalCost += cost;
    
    var ma20Ok = d.close > d.ma20 ? '✅' : '❌';
    var aboveZero = d.dif > 0 ? '上' : '下';
    
    rows.push({
      code: h.code, name: h.name,
      close: d.close, prevClose: d.prevClose,
      pct1d: pct1d, pctHold: pctHold,
      ma20: d.ma20, maDir: d.maDir,
      aboveZero: aboveZero,
      stars: stars, score: score,
      profit: profit, marketValue: marketValue,
      ma20Ok: ma20Ok
    });
    
    console.log(h.name + ' 收=' + d.close.toFixed(3) + ' 今日' + pct1d.toFixed(2) + '% 累计' + pctHold.toFixed(2) + '% 盈亏¥' + profit.toFixed(2) + ' MA20=' + d.ma20.toFixed(3) + d.maDir + ' 零轴' + aboveZero + ' ' + stars);
    await new Promise(function(c){setTimeout(c,200);});
  }
  
  var cash = 291.70;
  var totalAssets = totalMarketValue + cash;
  var totalProfit = totalAssets - 100000;
  
  console.log('\n=== 账户总览 ===');
  console.log('持仓市值: ¥' + totalMarketValue.toFixed(2));
  console.log('现金: ¥' + cash);
  console.log('总资产: ¥' + totalAssets.toFixed(2));
  console.log('累计收益率: ' + ((totalProfit/100000)*100).toFixed(2) + '%');
  console.log('累计盈亏: ¥' + totalProfit.toFixed(2));
  
  // 输出JSON方便后续使用
  console.log('\n=== JSON输出 ===');
  console.log(JSON.stringify({rows: rows, totalMarketValue: totalMarketValue, totalAssets: totalAssets, cash: cash, totalProfit: totalProfit, pctReturn: (totalProfit/100000)*100}, null, 2));
}
main();
