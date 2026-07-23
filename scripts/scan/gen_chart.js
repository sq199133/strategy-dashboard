// 收益率对比图生成器
// 策略组合 vs 沪深300 / 创业板指 / 恒生指数 / 标普500ETF(513500)
'use strict';
var fs = require('fs');
var path = require('path');

var INITIAL = 100000;
var START = '2026-04-17';
var TRADING = ['2026-04-17','2026-04-20','2026-04-21'];

// 当前持仓快照（按交易日分段）
var PORTFOLIO = {
  '2026-04-17': [
    {code:'159681',shares:11600,cost:1.717},
    {code:'512770',shares:8300,cost:2.395},
    {code:'512220',shares:6100,cost:3.235},
    {code:'516390',shares:18200,cost:1.094},
    {code:'513100',shares:10500,cost:1.902}
  ],
  '2026-04-20': [
    {code:'159259',shares:15800,cost:1.270},
    {code:'515700',shares:7400,cost:2.703},
    {code:'513120',shares:15300,cost:1.314},
    {code:'518880',shares:2000,cost:10.029},
    {code:'513100',shares:10500,cost:1.902}
  ],
  '2026-04-21': [
    {code:'159259',shares:15800,cost:1.270},
    {code:'515700',shares:7400,cost:2.703},
    {code:'513120',shares:15300,cost:1.314},
    {code:'518880',shares:2000,cost:10.029},
    {code:'513100',shares:10500,cost:1.902}
  ]
};

// 现金余额（从交易记录推算）
var CASH = {'2026-04-17': 590, '2026-04-20': 292, '2026-04-21': 292};

var INDICES = [
  {code:'sh000300', name:'沪深300', color:'#E74C3C'},
  {code:'sz399006', name:'创业板指', color:'#3498DB'},
  {code:'hkHSI', name:'恒生指数', color:'#9B59B6'},
  {code:'sz513500', name:'标普500ETF', color:'#2ECC71'}
];

// All ETF codes we need prices for
var ALL_CODES = {};
TRADING.forEach(function(d) {
  PORTFOLIO[d].forEach(function(h) { ALL_CODES[h.code] = true; });
});
INDICES.forEach(function(i) { ALL_CODES[i.code] = true; });

var sleep = function(ms) { return new Promise(function(r) { setTimeout(r, ms); }); };

// Determine market prefix for Tencent API
function txCode(code) {
  if (code.startsWith('sh') || code.startsWith('sz') || code.startsWith('hk')) return code;
  // A-share ETF: SH = 51xxxx, SZ = 15xxxx/16xxxx/56xxxx
  if (/^51/.test(code) || /^11/.test(code)) return 'sh' + code;
  return 'sz' + code;
}

async function fetchKline(code, days) {
  var txc = txCode(code);
  var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + txc + ',day,,,' + days + ',qfq';
  try {
    var r = await fetch(url, {signal: AbortSignal.timeout(8000)});
    var j = await r.json();
    var d = j.data && j.data[txc];
    var arr = d ? (d.qfqday || d.day || []) : [];
    return arr.map(function(k) { return {date: k[0], close: +k[2]}; });
  } catch(e) { return []; }
}

function getClose(data, date) {
  for (var i = data.length - 1; i >= 0; i--) {
    if (data[i].date === date) return data[i].close;
  }
  return null;
}

async function main() {
  console.log('>> Fetching price data...');
  
  // Fetch all needed codes
  var priceMap = {};
  var codes = Object.keys(ALL_CODES);
  for (var i = 0; i < codes.length; i++) {
    process.stdout.write('  [' + (i+1) + '/' + codes.length + '] ' + codes[i] + '... ');
    priceMap[codes[i]] = await fetchKline(codes[i], 30);
    console.log(priceMap[codes[i]].length + '条');
    await sleep(180);
  }

  // Calculate portfolio daily NAV
  console.log('\n>> Calculating portfolio NAV...');
  var portfolioReturn = [];
  var baseNav = null;

  for (var di = 0; di < TRADING.length; di++) {
    var date = TRADING[di];
    var holdings = PORTFOLIO[date];
    var cash = CASH[date];
    var nav = cash;
    var valid = true;

    for (var hi = 0; hi < holdings.length; hi++) {
      var h = holdings[hi];
      var close = getClose(priceMap[h.code], date);
      if (close === null) { valid = false; break; }
      nav += close * h.shares;
    }

    if (!valid) {
      console.log('  ' + date + ': MISSING PRICE');
      continue;
    }

    if (baseNav === null) baseNav = nav;
    var ret = (nav / baseNav - 1) * 100;
    portfolioReturn.push({date: date, ret: ret, nav: nav});
    console.log('  ' + date + ': NAV=' + nav.toFixed(0) + ' return=' + ret.toFixed(2) + '%');
  }

  // Calculate index returns (normalized to same start date)
  console.log('\n>> Calculating index returns...');
  var indexReturns = {};
  for (var ii = 0; ii < INDICES.length; ii++) {
    var idx = INDICES[ii];
    var data = priceMap[idx.code];
    if (data.length < 5) { console.log('  ' + idx.name + ': 数据不足'); continue; }
    
    indexReturns[idx.code] = [];
    var baseClose = null;

    for (var di2 = 0; di2 < TRADING.length; di2++) {
      var date2 = TRADING[di2];
      var close2 = getClose(data, date2);
      if (close2 === null) {
        // Try finding closest date
        for (var fi = data.length - 1; fi >= 0; fi--) {
          if (data[fi].date <= date2) { close2 = data[fi].close; break; }
        }
      }
      if (close2 === null) continue;
      if (baseClose === null) baseClose = close2;
      var ret2 = (close2 / baseClose - 1) * 100;
      indexReturns[idx.code].push({date: date2, ret: ret2});
      console.log('  ' + idx.name + ' ' + date2 + ': ' + ret2.toFixed(2) + '%');
    }
  }

  // Generate HTML chart
  console.log('\n>> Generating chart...');
  
  var labels = TRADING.filter(function(d) {
    return portfolioReturn.some(function(p) { return p.date === d; });
  });

  var portfolioData = labels.map(function(d) {
    var p = portfolioReturn.find(function(x) { return x.date === d; });
    return p ? p.ret : null;
  });

  var html = '<!DOCTYPE html>\n<html><head><meta charset="utf-8">\n';
  html += '<title>1号策略 v3.7 收益率对比</title>\n';
  html += '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"><\/script>\n';
  html += '<style>body{font-family:"Microsoft YaHei",sans-serif;background:#1a1a2e;color:#eee;margin:20px;padding:20px}\n';
  html += '.chart-box{background:#16213e;border-radius:12px;padding:24px;box-shadow:0 4px 20px rgba(0,0,0,0.3)}\n';
  html += 'h1{text-align:center;font-size:22px;margin-bottom:4px}\n';
  html += '.subtitle{text-align:center;color:#888;font-size:13px;margin-bottom:20px}\n';
  html += 'canvas{max-height:420px}</style></head><body>\n';
  html += '<div class="chart-box">\n';
  html += '<h1>1号策略 v3.7 · 收益率对比</h1>\n';
  html += '<p class="subtitle">起始资金 ¥100,000 | 建仓日 ' + START + ' | 截至最新交易日</p>\n';
  html += '<canvas id="chart"></canvas>\n';
  html += '</div>\n';
  html += '<script>\n';
  html += 'var ctx=document.getElementById("chart").getContext("2d");\n';
  html += 'new Chart(ctx,{type:"line",data:{labels:' + JSON.stringify(labels) + ',datasets:[\n';
  html += '{label:"1号策略组合",data:' + JSON.stringify(portfolioData) + ',borderColor:"#F39C12",backgroundColor:"rgba(243,156,18,0.1)",borderWidth:3,pointRadius:5,pointBackgroundColor:"#F39C12",tension:0.3},\n';

  for (var ii2 = 0; ii2 < INDICES.length; ii2++) {
    var idx2 = INDICES[ii2];
    var iData = indexReturns[idx2.code] || [];
    var iVals = labels.map(function(d) {
      var p = iData.find(function(x) { return x.date === d; });
      return p ? p.ret : null;
    });
    html += '{label:"' + idx2.name + '",data:' + JSON.stringify(iVals) + ',borderColor:"' + idx2.color + '",backgroundColor:"transparent",borderWidth:2,borderDash:[5,3],pointRadius:3,tension:0.3},\n';
  }

  html += ']},options:{responsive:true,plugins:{legend:{labels:{color:"#ccc",font:{size:13}},position:"bottom"},\n';
  html += 'tooltip:{callbacks:{label:function(c){return c.dataset.label+": "+c.parsed.y.toFixed(2)+"%"}}}},\n';
  html += 'scales:{x:{grid:{color:"#333"},ticks:{color:"#888"}},y:{grid:{color:"#333"},ticks:{color:"#888",callback:function(v){return v.toFixed(1)+"%"}}}}}});\n';
  html += '<\/script></body></html>';

  var outPath = path.join(__dirname, '..', '..', 'reviews', 'return_chart.html');
  fs.writeFileSync(outPath, html, 'utf8');
  console.log('\nChart saved: ' + outPath);
}

main().catch(function(e) { console.error('Fatal:', e); });
