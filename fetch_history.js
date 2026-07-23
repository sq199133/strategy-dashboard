/**
 * fetch_history.js - ETF历史K线本地数据下载
 * 
 * 数据源：东方财富 push2his.eastmoney.com
 * 覆盖：从ETF成立日到2025-12-31
 * 格式：JSON，每只ETF一个文件
 * 路径：data/history/{market}{code}.json
 * 
 * 使用方法：
 *   node fetch_history.js           # 下载全部104只ETF
 *   node fetch_history.js 159338  # 只下载单只ETF
 */

const fs   = require('fs');
const path = require('path');
const https = require('https');

const ETF_POOL = require('./data/etf_pool.js');
const OUT_DIR  = path.join(__dirname, 'data', 'history');

// 确保目录存在
if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

// ── 东方财富K线接口 ──────────────────────────
function fetchKlineEM(code, market) {
  return new Promise(function(resolve, reject) {
    // secid: 1=上交所, 0=深交所
    var secid = (market === 'SH' ? '1.' : '0.') + code;
    var url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?' +
      'secid=' + secid +
      '&fields1=f1,f2,f3,f4,f5,f6' +
      '&fields2=f51,f52,f53,f54,f55,f56,f57,f58' +
      '&klt=101&fqt=1' +                    // 日线，前复权
      '&beg=19900101&end=20251231' +        // 从成立开始
      '&lmt=5000';                          // 最多5000条

    var req = https.get(url, {
      headers: {
        'Referer': 'https://quote.eastmoney.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
      }
    }, function(res) {
      var d = '';
      res.on('data', function(c) { d += c; });
      res.on('end', function() {
        try {
          var j = JSON.parse(d);
          var klines = j.data ? (j.data.klines || []) : [];
          if (klines.length === 0) {
            reject(new Error('无数据: ' + j.msg));
            return;
          }
          // 解析每行，字段：日期,开,收,高,低,成交量,成交额,涨跌幅
          var records = klines.map(function(line) {
            var parts = line.split(',');
            return {
              date:   parts[0],
              open:   parseFloat(parts[1]),
              close:  parseFloat(parts[2]),
              high:   parseFloat(parts[3]),
              low:    parseFloat(parts[4]),
              vol:    parseFloat(parts[5]),
              amount: parseFloat(parts[6]),
              chg:    parseFloat(parts[7])  // 涨跌幅%
            };
          });
          resolve({ code: code, market: market, total: records.length, records: records });
        } catch(e) {
          reject(new Error('解析失败: ' + e.message));
        }
      });
    });
    req.on('error', function(e) { reject(e); });
    req.setTimeout(12000, function() { req.abort(); reject(new Error('超时')); });
  });
}

// ── 保存单只ETF数据 ───────────────────────────
function saveEtfData(data) {
  var filename = data.market.toLowerCase() + data.code + '.json';
  var filepath = path.join(OUT_DIR, filename);
  fs.writeFileSync(filepath, JSON.stringify(data, null, 2), 'utf8');
  return filepath;
}

// ── 批量下载 ──────────────────────────────────
async function downloadAll(targetCodes) {
  var etfs = targetCodes
    ? ETF_POOL.filter(function(e){ return targetCodes.indexOf(e.code) >= 0; })
    : ETF_POOL;

  console.log('═══════════════════════════════════════════════');
  console.log('  ETF历史K线数据下载');
  console.log('  目标: ' + etfs.length + ' 只ETF');
  console.log('  输出: ' + OUT_DIR);
  console.log('  截止: 2025-12-31');
  console.log('═══════════════════════════════════════════════\n');

  var success = 0, failed = 0;
  var results = [];

  for (var i = 0; i < etfs.length; i++) {
    var etf = etfs[i];
    var idx = i + 1;
    var pct = Math.round(idx / etfs.length * 100);
    process.stdout.write('\r[' + pct + '%] ' + idx + '/' + etfs.length + '  正在下载: ' + etf.code + ' ' + etf.name + ' ...');

    try {
      var data = await fetchKlineEM(etf.code, etf.market);
      var fp = saveEtfData(data);
      var dateRange = data.records[0].date + ' → ' + data.records[data.records.length-1].date;
      console.log('  ✅ ' + data.total + '条 ' + dateRange);
      results.push({ code: etf.code, name: etf.name, total: data.total, first: data.records[0].date, last: data.records[data.records.length-1].date, file: fp });
      success++;
    } catch(e) {
      console.log('  ❌ ' + e.message);
      results.push({ code: etf.code, name: etf.name, error: e.message });
      failed++;
    }

    // 每请求间隔 200ms（避免过快触发限流）
    await new Promise(function(r){ setTimeout(r, 200); });
  }

  console.log('\n' + '='.repeat(50));
  console.log('下载完成！');
  console.log('  成功: ' + success + ' 只');
  if (failed > 0) console.log('  失败: ' + failed + ' 只');
  console.log('  目录: ' + OUT_DIR);

  // 汇总统计
  var byCategory = {};
  results.filter(function(r){ return r.total; }).forEach(function(r){
    if (!byCategory[r.code]) {
      var etf = ETF_POOL.find(function(e){ return e.code === r.code; });
      var cat = etf ? etf.category : '未知';
      if (!byCategory[cat]) byCategory[cat] = { count: 0, totalBars: 0 };
      byCategory[cat].count++;
      byCategory[cat].totalBars += r.total;
    }
  });

  console.log('\n按类别统计:');
  Object.keys(byCategory).sort().forEach(function(cat){
    var v = byCategory[cat];
    console.log('  ' + cat + ': ' + v.count + '只, 共' + v.totalBars + '条K线');
  });

  var totalBars = results.reduce(function(s,r){ return s + (r.total||0); }, 0);
  console.log('\n总计: ' + success + '只ETF, ' + totalBars + '条日K线');
  console.log('\n下一步: 在回测脚本中用 require("./data/history/sh159338.json") 读取数据');
  return results;
}

// ── 入口 ──────────────────────────────────────
var targetCodes = process.argv.slice(2);  // 可传代码: node fetch_history.js 159338 510300
downloadAll(targetCodes.length > 0 ? targetCodes : null).catch(console.error);
