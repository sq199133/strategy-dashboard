// ============================================================
// ETF持仓相关性矩阵计算脚本
// 用途：对指定ETF列表两两计算日收益率Pearson相关系数
// 数据窗口：120个交易日
// 输出：完整相关性矩阵 + maxCorr报告
// ============================================================

'use strict';

var path = require('path');
var fs   = require('fs');

var SCRIPT_DIR = __dirname;

// ════════════════════════════════════════════════════════════
// 技术指标（仅SMA用于MA20方向判断）
// ════════════════════════════════════════════════════════════

function SMA(prices, n) {
  var out = new Array(prices.length).fill(null);
  for (var i = n - 1; i < prices.length; i++) {
    var s = 0;
    for (var j = i - n + 1; j <= i; j++) s += prices[j];
    out[i] = s / n;
  }
  return out;
}

// ════════════════════════════════════════════════════════════
// Pearson相关系数（基于日收益率，120日）
// ════════════════════════════════════════════════════════════

function pearsonCorr(prices1, prices2) {
  function toReturns(arr) {
    var r = [];
    for (var i = 1; i < arr.length; i++) {
      if (arr[i] > 0 && arr[i - 1] > 0) {
        r.push((arr[i] - arr[i - 1]) / arr[i - 1]);
      }
    }
    return r;
  }
  var r1 = toReturns(prices1);
  var r2 = toReturns(prices2);
  var n  = Math.min(r1.length, r2.length, 120);
  if (n < 10) return NaN;
  var s1 = r1.length - n, s2 = r2.length - n;
  var sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;
  for (var i = 0; i < n; i++) {
    var x = r1[s1 + i], y = r2[s2 + i];
    sumX += x; sumY += y; sumXY += x * y; sumX2 += x * x; sumY2 += y * y;
  }
  var den = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));
  return den === 0 ? 0 : (n * sumXY - sumX * sumY) / den;
}

// ════════════════════════════════════════════════════════════
// 数据获取
// ════════════════════════════════════════════════════════════

var sleep = function(ms) { return new Promise(function(r) { setTimeout(r, ms); }); };

function txSecid(code, market) {
  return market === 'SZ' ? 'sz' + code : 'sh' + code;
}

async function fetchTx(code, market) {
  var secid = txSecid(code, market);
  var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + secid + ',day,,,180,qfq';
  try {
    var r = await fetch(url, { signal: AbortSignal.timeout(10000) });
    var j = await r.json();
    var arr = j.data && j.data[secid]
      ? (j.data[secid].qfqday || j.data[secid].day || [])
      : [];
    return arr.map(function(k) {
      return { date: k[0], close: +k[2], vol: +k[5] };
    });
  } catch(e) { return []; }
}

async function fetchEM(code, market) {
  var secid = market === 'SZ' ? '0.' + code : '1.' + code;
  var url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get' +
    '?secid=' + secid +
    '&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61' +
    '&klt=101&fqt=0&beg=20200101&end=20500101&lmt=200';
  try {
    var r = await fetch(url, { signal: AbortSignal.timeout(8000) });
    var j = await r.json();
    var klines = (j.data && j.data.klines) ? j.data.klines : [];
    return klines.map(function(k) {
      var p = k.split(',');
      return { date: p[0], close: +p[2], vol: +p[5] };
    });
  } catch(e) { return []; }
}

// ════════════════════════════════════════════════════════════
// 主程序
// ════════════════════════════════════════════════════════════

async function main() {
  // 解析命令行参数：ETF列表，格式 "code:market:name,code:market:name,..."
  var args = process.argv.slice(2);
  if (args.length === 0) {
    console.log('用法: node corr_etf.js "159259:SZ:成长ETF,515700:SH:新能源车ETF,..."');
    console.log('  或: node corr_etf.js --portfolio  (自动从portfolio.md读取持仓)');
    process.exit(1);
  }

  var etfList = [];

  if (args[0] === '--portfolio') {
    // 从portfolio.md读取持仓
    var pfPath = path.join(SCRIPT_DIR, '..', '..', 'data', 'portfolio.md');
    if (!fs.existsSync(pfPath)) {
      console.error('portfolio.md 不存在: ' + pfPath);
      process.exit(1);
    }
    var pfContent = fs.readFileSync(pfPath, 'utf8');
    // 解析持仓表格中的 代码|名称
    var re = /\|\s*(\d{6})\s*\|\s*([^|]+)\s*\|/g;
    var match;
    var inHolding = false;
    var lines = pfContent.split('\n');
    for (var li = 0; li < lines.length; li++) {
      var line = lines[li];
      if (/当前持仓/.test(line)) inHolding = true;
      if (/调仓记录|候补标的|账户概览/.test(line)) inHolding = false;
      if (inHolding && /^\|.*\|.*\|/.test(line)) {
        var m = line.match(/^\|\s*(\d{6})\s*\|\s*([^|]+)\s*\|/);
        if (m) {
          var code = m[1];
          var name = m[2].trim();
          var market = code.startsWith('1') || code.startsWith('3') ? 'SZ' : 'SH';
          etfList.push({ code: code, market: market, name: name });
        }
      }
    }
    if (etfList.length === 0) {
      console.error('未从portfolio.md中解析到持仓');
      process.exit(1);
    }
  } else {
    // 解析命令行ETF列表
    var parts = args[0].split(',');
    parts.forEach(function(p) {
      var fields = p.split(':');
      if (fields.length >= 3) {
        etfList.push({ code: fields[0], market: fields[1], name: fields.slice(2).join(':') });
      }
    });
  }

  console.log('═══════════════════════════════════════════════════');
  console.log('  ETF相关性矩阵  |  ' + etfList.length + '只  |  120日日收益率Pearson');
  console.log('═══════════════════════════════════════════════════\n');

  // 获取数据
  var priceData = {};
  for (var i = 0; i < etfList.length; i++) {
    var etf = etfList[i];
    process.stdout.write('  获取 ' + etf.name + '(' + etf.code + ')... ');
    var data = await fetchTx(etf.code, etf.market);
    if (data.length < 60) {
      await sleep(350);
      data = await fetchEM(etf.code, etf.market);
    }
    await sleep(200);
    if (data.length < 60) {
      console.log('FAIL（仅' + data.length + '条）');
      continue;
    }
    priceData[etf.code] = data.map(function(d) { return d.close; });
    var ma20 = SMA(priceData[etf.code], 20);
    var price = priceData[etf.code][priceData[etf.code].length - 1];
    var ma20c = ma20[ma20.length - 1];
    var pctFromMA20 = ma20c ? ((price - ma20c) / ma20c * 100).toFixed(1) + '%' : '--';
    console.log('OK (' + data.length + '条)  MA20距=' + pctFromMA20);
  }
  console.log('');

  // 计算相关性矩阵
  var codes = Object.keys(priceData);
  var names = {};
  etfList.forEach(function(e) { names[e.code] = e.name; });

  var matrix = {};
  for (var ai = 0; ai < codes.length; ai++) {
    for (var bi = ai; bi < codes.length; bi++) {
      var r = pearsonCorr(priceData[codes[ai]], priceData[codes[bi]]);
      var key = codes[ai] + '_' + codes[bi];
      matrix[key] = r;
      if (ai !== bi) {
        matrix[codes[bi] + '_' + codes[ai]] = r;
      }
    }
  }

  // 打印矩阵
  console.log('>> 相关性矩阵（日收益率，120日）：\n');

  // 表头
  var shortNames = codes.map(function(c) { return (names[c] || c).substring(0, 6); });
  var headerRow = '           ';
  shortNames.forEach(function(n) { headerRow += pad(n, 8); });
  console.log(headerRow);

  for (var ri = 0; ri < codes.length; ri++) {
    var row = pad((names[codes[ri]] || codes[ri]).substring(0, 10), 10);
    for (var ci = 0; ci < codes.length; ci++) {
      var key = codes[ri] + '_' + codes[ci];
      var val = matrix[key];
      if (ri === ci) {
        row += pad('1.00', 8);
      } else if (isNaN(val)) {
        row += pad('N/A', 8);
      } else {
        var flag = val > 0.70 ? '⚠️' : '';
        row += pad(val.toFixed(2) + flag, 8);
      }
    }
    console.log(row);
  }
  console.log('');

  // maxCorr报告
  console.log('>> maxCorr报告（每只ETF与其他持仓的最大相关性）：\n');
  for (var mi = 0; mi < codes.length; mi++) {
    var maxR = 0;
    var maxWith = '';
    for (var ni = 0; ni < codes.length; ni++) {
      if (mi === ni) continue;
      var key2 = codes[mi] + '_' + codes[ni];
      var val2 = matrix[key2];
      if (!isNaN(val2) && val2 > maxR) {
        maxR = val2;
        maxWith = names[codes[ni]] || codes[ni];
      }
    }
    var status = maxR > 0.70 ? '🔴 超阈值!' : (maxR > 0.50 ? '🟡 中高' : '🟢 OK');
    console.log('  ' + pad(names[codes[mi]] || codes[mi], 16) + ' maxCorr=' + maxR.toFixed(2) + ' (vs ' + maxWith + ')  ' + status);
  }
  console.log('');
}

function pad(s, n) {
  s = String(s === null || s === undefined ? '--' : s);
  while (s.length < n) s += ' ';
  return s;
}

main().catch(function(e) { console.error('Fatal error:', e); process.exit(1); });
