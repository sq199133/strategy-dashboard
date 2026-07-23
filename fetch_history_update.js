/**
 * fetch_history_update.js - 增量更新本地历史数据
 *
 * 每次运行只下载最新日期之后的K线，避免重复下载全量数据
 * 数据源：东方财富 push2his.eastmoney.com
 *
 * 使用方法：
 *   node fetch_history_update.js          # 更新全部ETF
 *   node fetch_history_update.js 159338  # 只更新单只ETF
 */

const fs   = require('fs');
const path = require('path');
const https = require('https');

const ETF_POOL = require('./data/etf_pool.js');
const OUT_DIR  = path.join(__dirname, 'data', 'history');

function fetchKlineEM(code, market, since) {
  return new Promise(function(resolve, reject) {
    var secid = (market === 'SH' ? '1.' : '0.') + code;
    var beg = since ? since.replace(/-/g, '') : '19900101';
    var url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?' +
      'secid=' + secid +
      '&fields1=f1,f2,f3,f4,f5,f6' +
      '&fields2=f51,f52,f53,f54,f55,f56,f57,f58' +
      '&klt=101&fqt=1&beg=' + beg + '&end=20991231&lmt=100';

    var req = https.get(url, {
      headers: {
        'Referer': 'https://quote.eastmoney.com',
        'User-Agent': 'Mozilla/5.0'
      }
    }, function(res) {
      var d = '';
      res.on('data', function(c){ d += c; });
      res.on('end', function(){
        try {
          var j = JSON.parse(d);
          var klines = j.data ? (j.data.klines || []) : [];
          var records = klines.map(function(line){
            var p = line.split(',');
            return { date: p[0], open: +p[1], close: +p[2], high: +p[3], low: +p[4], vol: +p[5], amount: +p[6], chg: +p[7] };
          });
          resolve(records);
        } catch(e) { reject(new Error('解析失败')); }
      });
    });
    req.on('error', function(e){ reject(e); });
    req.setTimeout(12000, function(){ req.abort(); reject(new Error('超时')); });
  });
}

function getLastDate(filepath) {
  if (!fs.existsSync(filepath)) return null;
  try {
    var raw = require(filepath);
    var recs = raw.records || [];
    if (recs.length === 0) return null;
    return recs[recs.length - 1].date;
  } catch(e) { return null; }
}

async function updateAll(targetCodes) {
  var etfs = targetCodes
    ? ETF_POOL.filter(function(e){ return targetCodes.indexOf(e.code) >= 0; })
    : ETF_POOL;

  console.log('═══════════════════════════════════════');
  console.log('  增量更新本地K线数据');
  console.log('  目标: ' + etfs.length + ' 只ETF');
  console.log('═══════════════════════════════════════\n');

  var updated = 0, skipped = 0, failed = 0;

  for (var i = 0; i < etfs.length; i++) {
    var etf = etfs[i];
    var fn = (etf.market || 'sh').toLowerCase() + etf.code + '.json';
    var fp = path.join(OUT_DIR, fn);

    var lastDate = getLastDate(fp);
    process.stdout.write('\r[' + (i+1) + '/' + etfs.length + '] ' + etf.code + ' ' + etf.name + ' (本地末:' + (lastDate||'无') + ') ...');

    try {
      var newBars = await fetchKlineEM(etf.code, etf.market, lastDate);
      if (newBars.length === 0) {
        console.log('  ⏭ 无新数据');
        skipped++;
      } else {
        // 合并：去重（按日期）
        var existing = {};
        if (fs.existsSync(fp)) {
          try {
            var raw = require(fp);
            (raw.records || []).forEach(function(r){ existing[r.date] = r; });
          } catch(e){}
        }
        newBars.forEach(function(r){ existing[r.date] = r; });
        var merged = Object.keys(existing).sort().map(function(d){ return existing[d]; });

        var data = { code: etf.code, market: etf.market, total: merged.length, records: merged };
        fs.writeFileSync(fp, JSON.stringify(data, null, 2), 'utf8');
        console.log('  ✅ +' + newBars.length + '条 (' + merged.length + '条总计)');
        updated++;
      }
    } catch(e) {
      console.log('  ❌ ' + e.message);
      failed++;
    }

    await new Promise(function(r){ setTimeout(r, 150); });
  }

  console.log('\n更新完成: ' + updated + '只已更新, ' + skipped + '只无需更新, ' + failed + '只失败');
}

// 入口
var targets = process.argv.slice(2).filter(function(a){ return /^\d{6}$/.test(a); });
updateAll(targets.length > 0 ? targets : null).catch(console.error);
