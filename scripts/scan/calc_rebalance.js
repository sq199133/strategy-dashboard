// 获取调仓标的的4月17日收盘价
var https = require('https');

var targets = [
  // 卖出
  { code: '159681', name: '创业板50ETF', action: 'SELL' },
  { code: '512770', name: '战略新兴ETF', action: 'SELL' },
  { code: '512220', name: 'TMTETF', action: 'SELL' },
  { code: '516390', name: '新能源汽车ETF', action: 'SELL' },
  // 买入
  { code: '159259', name: '成长ETF', action: 'BUY' },
  { code: '515700', name: '新能源车ETF平安', action: 'BUY' },
  { code: '513120', name: '港股创新药ETF', action: 'BUY' },
  { code: '511010', name: '国债ETF', action: 'BUY' },
  // 保留
  { code: '513100', name: '纳指ETF', action: 'KEEP' }
];

function getMarket(code) {
  if (code.startsWith('5') || code.startsWith('0')) return 'sh';
  if (code.startsWith('1')) return 'sz';
  return 'sh';
}

function fetchQuote(code) {
  return new Promise(function(resolve) {
    var market = getMarket(code);
    var secid = market + code;
    // 用实时行情接口获取最新价
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/minute/query?_var=min_data&code=' + secid;
    https.get(url, {headers: {'Referer': 'https://gu.qq.com'}}, function(r) {
      var chunks = [];
      r.on('data', function(c) { chunks.push(c); });
      r.on('end', function() {
        try {
          var raw = Buffer.concat(chunks).toString('utf8');
          // 试试日K线接口获取最新收盘价
          resolve(null);
        } catch(e) { resolve(null); }
      });
    }).on('error', function() { resolve(null); });
  });
}

function fetchKline(code) {
  return new Promise(function(resolve) {
    var market = getMarket(code);
    var secid = market + code;
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + secid + ',day,,,5,qfq';
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
          resolve({
            code: code,
            date: last[0],
            open: parseFloat(last[1]),
            close: parseFloat(last[2]),
            high: parseFloat(last[3]),
            low: parseFloat(last[4])
          });
        } catch(e) { resolve(null); }
      });
    }).on('error', function() { resolve(null); });
  });
}

async function main() {
  console.log('=== 调仓价格确认 ===\n');
  
  var prices = {};
  for (var i = 0; i < targets.length; i++) {
    var t = targets[i];
    var p = await fetchKline(t.code);
    if (p) {
      prices[t.code] = p;
      console.log(t.action + ' ' + t.code + ' ' + t.name + ' 日期:' + p.date + ' 收盘:' + p.close.toFixed(3));
    } else {
      console.log(t.action + ' ' + t.code + ' ' + t.name + ' ❌获取失败');
    }
    await new Promise(function(c) { setTimeout(c, 300); });
  }
  
  // 计算调仓
  console.log('\n=== 调仓计算（假设按4月17日收盘价执行）===\n');
  
  // 当前持仓
  var holdings = {
    '159681': { shares: 11600, buyPrice: 1.717 },
    '512770': { shares: 8300, buyPrice: 2.395 },
    '512220': { shares: 6100, buyPrice: 3.235 },
    '516390': { shares: 18200, buyPrice: 1.094 },
    '513100': { shares: 10500, buyPrice: 1.902 }
  };
  
  // 卖出回收金额
  var sellCodes = ['159681', '512770', '512220', '516390'];
  var totalSell = 0;
  var sellDetails = [];
  
  sellCodes.forEach(function(code) {
    var h = holdings[code];
    var p = prices[code];
    if (!p) return;
    var sellAmount = h.shares * p.close;
    var profit = (p.close - h.buyPrice) * h.shares;
    var profitPct = ((p.close / h.buyPrice) - 1) * 100;
    totalSell += sellAmount;
    sellDetails.push({
      code: code,
      shares: h.shares,
      price: p.close,
      amount: sellAmount,
      profit: profit,
      profitPct: profitPct
    });
    console.log('卖出 ' + code + ' ' + h.shares + '股 @' + p.close.toFixed(3) + ' = ¥' + sellAmount.toFixed(2) + '  盈亏:' + (profit >= 0 ? '+' : '') + profit.toFixed(2) + ' (' + profitPct.toFixed(2) + '%)');
  });
  
  console.log('卖出合计: ¥' + totalSell.toFixed(2));
  
  // 可用资金（原有589 + 卖出回收）
  var availableCash = 589 + totalSell;
  console.log('可用资金: ¥' + availableCash.toFixed(2));
  
  // 买入4只，保留513100
  var buyCodes = ['159259', '515700', '513120', '511010'];
  var perETF = availableCash / 4;
  console.log('\n每只买入预算: ¥' + perETF.toFixed(2));
  
  buyCodes.forEach(function(code) {
    var p = prices[code];
    if (!p) return;
    var shares = Math.floor(perETF / p.close / 100) * 100; // 整百股
    if (shares < 100) shares = 100;
    var amount = shares * p.close;
    console.log('买入 ' + code + ' ' + shares + '股 @' + p.close.toFixed(3) + ' = ¥' + amount.toFixed(2));
  });
  
  // 保留513100
  var keepPrice = prices['513100'];
  if (keepPrice) {
    var keepValue = holdings['513100'].shares * keepPrice.close;
    console.log('\n保留 513100 纳指ETF ' + holdings['513100'].shares + '股 @' + keepPrice.close.toFixed(3) + ' = ¥' + keepValue.toFixed(2));
  }
}
main();
