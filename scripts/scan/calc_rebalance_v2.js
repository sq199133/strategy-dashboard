// 优化调仓方案 - 国债ETF太贵，考虑替代方案
// 方案1：去掉国债ETF，4只股票型ETF等权
// 方案2：保留国债ETF，调整分配

var https = require('https');

function getMarket(code) {
  if (code.startsWith('5') || code.startsWith('0')) return 'sh';
  if (code.startsWith('1')) return 'sz';
  return 'sh';
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
          resolve({ code: code, close: parseFloat(last[2]) });
        } catch(e) { resolve(null); }
      });
    }).on('error', function() { resolve(null); });
  });
}

async function main() {
  // 可用资金
  var availableCash = 80522.10;
  
  console.log('=== 方案对比 ===\n');
  
  // 方案A：4只股票型ETF（去掉国债ETF）
  console.log('--- 方案A：5只股票型ETF等权 ---\n');
  var codesA = ['159259', '515700', '513120', '513100'];
  // 需要找第5只低相关的标的
  
  // 先看看513120的HOLD级别是否足够
  // 扫描结果：513120 ⭐⭐⭐ HOLD 零轴上方 11.5%
  // 这只其实很合适

  // 方案B：保留国债ETF但调整权重
  console.log('--- 方案B：4只进攻 + 1只防御 ---\n');
  console.log('国债ETF 511010 价格140.754元/份');
  console.log('  100股 = ¥14,075（太少占比14%）');
  console.log('  200股 = ¥28,150（太多占比28%）');
  console.log('');
  
  // 方案C：不用国债ETF，用其他防御性标的
  // 扫描中WAIT但有防御性的：
  // 510880 红利ETF ⭐ WAIT -2.6%
  // 512800 银行ETF ⭐ HOLD -0.4%
  // 518880 黄金ETF ⭐ HOLD -1.0%
  
  console.log('--- 方案C：用黄金ETF替代国债ETF ---\n');
  // 黄金ETF 518880 与组合相关性约-0.08（与国债类似）
  // 价格10.029元/份，更容易等权配置
  
  var codesC = ['159259', '515700', '513120', '513100', '518880'];
  var prices = {};
  
  for (var i = 0; i < codesC.length; i++) {
    var p = await fetchKline(codesC[i]);
    if (p) {
      prices[codesC[i]] = p.close;
      console.log(codesC[i] + ': ' + p.close.toFixed(3));
    }
    await new Promise(function(c) { setTimeout(c, 200); });
  }
  
  // 等权配置
  var perETF = availableCash / 5;
  console.log('\n每只预算: ¥' + perETF.toFixed(2));
  var totalInvest = 0;
  
  codesC.forEach(function(code) {
    var price = prices[code];
    if (!price) return;
    var shares = Math.floor(perETF / price / 100) * 100;
    if (shares < 100) shares = 100;
    var amount = shares * price;
    totalInvest += amount;
    var names = {
      '159259': '成长ETF',
      '515700': '新能源车ETF',
      '513120': '港股创新药ETF',
      '513100': '纳指ETF',
      '518880': '黄金ETF'
    };
    console.log('买入 ' + code + ' ' + names[code] + ' ' + shares + '股 @' + price.toFixed(3) + ' = ¥' + amount.toFixed(2));
  });
  
  var remainCash = availableCash - totalInvest;
  console.log('\n投入合计: ¥' + totalInvest.toFixed(2));
  console.log('剩余现金: ¥' + remainCash.toFixed(2));
  
  // 也考虑513100保留的情况
  console.log('\n\n=== 最终方案：513100保留 + 4只新买入 ===\n');
  var keepValue = 10500 * (prices['513100'] || 1.892); // 513100保留
  var cashForNew = availableCash - keepValue + 19866; // 不卖513100
  // 实际上513100不卖，所以可用资金 = 589 + 卖出4只 = 80522
  // 513100继续持有（市值19866）
  // 用80522买4只新标的
  
  var codesFinal = ['159259', '515700', '513120', '518880'];
  var perETF2 = availableCash / 4;
  console.log('4只新标的每只预算: ¥' + perETF2.toFixed(2));
  var totalInvest2 = 0;
  
  for (var i = 0; i < codesFinal.length; i++) {
    var code = codesFinal[i];
    var price = prices[code];
    if (!price) {
      var p = await fetchKline(code);
      if (p) price = p.close;
      await new Promise(function(c) { setTimeout(c, 200); });
    }
    if (!price) continue;
    var shares = Math.floor(perETF2 / price / 100) * 100;
    if (shares < 100) shares = 100;
    var amount = shares * price;
    totalInvest2 += amount;
    var names = {
      '159259': '成长ETF',
      '515700': '新能源车ETF',
      '513120': '港股创新药ETF',
      '518880': '黄金ETF'
    };
    console.log('买入 ' + code + ' ' + names[code] + ' ' + shares + '股 @' + price.toFixed(3) + ' = ¥' + amount.toFixed(2));
  }
  
  console.log('\n513100 纳指ETF 保留 10500股 @' + (prices['513100']||1.892).toFixed(3));
  
  var remainCash2 = availableCash - totalInvest2;
  console.log('\n新买入合计: ¥' + totalInvest2.toFixed(2));
  console.log('剩余现金: ¥' + remainCash2.toFixed(2));
  
  var totalAssets = totalInvest2 + keepValue + remainCash2;
  console.log('总资产: ¥' + totalAssets.toFixed(2));
}
main();
