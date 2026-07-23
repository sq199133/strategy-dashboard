var execSync = require('child_process').execSync;
var fs = require('fs');

var pool = require('D:/QClaw_Trading/data/etf_pool.js');

function prefix(code) {
  if (code.startsWith('5') || code.startsWith('51') ||
      code.startsWith('512') || code.startsWith('515') ||
      code.startsWith('517') || code.startsWith('518') ||
      code.startsWith('588') || code.startsWith('560') ||
      code.startsWith('513') || code.startsWith('589')) {
    return 'sh';
  }
  return 'sz';
}

function fetchQuotes(codes) {
  var results = {};
  var batches = [];
  for (var i = 0; i < codes.length; i += 46) {
    batches.push(codes.slice(i, i + 46));
  }

  for (var b = 0; b < batches.length; b++) {
    var batch = batches[b];
    var q = batch.map(function(c) { return prefix(c) + c; }).join(',');
    var out = '';
    try {
      out = execSync('curl.exe -s --max-time 15 "https://qt.gtimg.cn/q=' + q + '"', {
        encoding: 'utf8', timeout: 20000
      });
    } catch(e) {
      console.log('curl batch failed: ' + e.message);
      continue;
    }

    var lines = out.trim().split('\n');
    for (var l = 0; l < lines.length; l++) {
      var line = lines[l];
      var m = line.match(/v_(sh|sz)(\d+)[^=]*="([^"]*)"/);
      if (!m) continue;
      var code = m[2];
      var f = m[3].split('~');
      results[code] = {
        price: f[3] || null,
        close: f[4] || null,
        change: f[31] || null,
        pct: f[32] || null,
        nav: f[34] || null,
        high52w: f[47] || null,
        low52w: f[48] || null,
        ytd: f[51] || null,
      };
    }
  }
  return results;
}

function main() {
  console.log('Fetching 91 ETF quotes...');
  var results = fetchQuotes(pool.map(function(e) { return e.code; }));

  var enriched = pool.map(function(etf) {
    var r = results[etf.code] || {};
    var price = r.price ? parseFloat(r.price) : null;
    var nav = r.nav ? parseFloat(r.nav) : null;
    var premium = null;
    if (price && nav && nav > 0) {
      premium = ((price - nav) / nav * 100).toFixed(2);
    }
    return {
      '序号': etf.index,
      '代码': etf.code,
      '名称': etf.name,
      '市场': etf.market,
      '类别': etf.category,
      '现价': price,
      '昨收': r.close ? parseFloat(r.close) : null,
      '涨跌额': r.change ? parseFloat(r.change) : null,
      '涨跌幅(%)': r.pct ? parseFloat(r.pct) : null,
      '估算净值NAV': nav,
      '折溢价率(%)': premium,
      '52W最高': r.high52w ? parseFloat(r.high52w) : null,
      '52W最低': r.low52w ? parseFloat(r.low52w) : null,
      '年初至今': r.ytd ? parseFloat(r.ytd) : null,
      '数据状态': r.price ? 'OK' : '无数据',
    };
  });

  fs.writeFileSync('D:/QClaw_Trading/data/etf_pool_enriched.json', JSON.stringify(enriched, null, 2), 'utf8');

  var success = enriched.filter(function(e) { return e['数据状态'] === 'OK'; }).length;
  console.log('Done: ' + success + '/91 have data\n');

  var cats = {};
  for (var i = 0; i < enriched.length; i++) {
    var e = enriched[i];
    if (!cats[e['类别']]) cats[e['类别']] = [];
    cats[e['类别']].push(e);
  }

  for (var cat in cats) {
    var items = cats[cat];
    var s = items.filter(function(x) { return x['数据状态'] === 'OK'; }).length;
    console.log('[' + cat + '] ' + s + '/' + items.length);
  }

  console.log('\nJSON saved to data/etf_pool_enriched.json');
}

main();