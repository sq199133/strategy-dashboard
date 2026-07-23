// fetch_etf_index.js
// 从东方财富抓取每只ETF跟踪的指数代码和名称（使用https模块）
const fs   = require('fs');
const path = require('path');
const https = require('https');

const ALL_ETFS = require('./data/etf_pool.js');

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://fundf10.eastmoney.com/',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9'
      }
    }, (res) => {
      if (res.statusCode !== 200) {
        reject(new Error('HTTP ' + res.statusCode));
        return;
      }
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch(e) { reject(new Error('JSON parse error: ' + e.message + ' | data: ' + data.slice(0, 200))); }
      });
    });
    req.on('error', reject);
    req.setTimeout(10000, () => { req.destroy(); reject(new Error('timeout')); });
  });
}

async function fetchETFIndex(code, market) {
  var secid = market === 'SH' ? '1.' + code : '0.' + code;
  var url = 'https://push2.eastmoney.com/api/qt/ulist.np/get?' +
    'secids=' + secid +
    '&fields=f12,f14,f100,f103,f104,f105,f128,f129,f130,f131,f132' +
    '&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2';

  var j = await httpGet(url);
  var items = j.data && j.data.diff;
  if (!items || items.length === 0) return null;

  var matched = items.find(item => String(item.f12) === code) || items[0];

  return {
    code:      code,
    name:      matched.f14 || '',
    trackName: matched.f104 || '',   // 跟踪指数名称
    trackCode: matched.f103 || '',  // 跟踪指数代码
    scale:     matched.f130 || '',   // 规模(亿)
    trackingDiff: matched.f105 || '', // 跟踪误差
    fee:       matched.f128 || '',
    listed:    matched.f129 || '',
  };
}

async function main() {
  console.log('ETF跟踪指数抓取工具');
  console.log('总计: ' + ALL_ETFS.length + ' 只\n');

  var results = [];
  var errors  = [];

  for (var i = 0; i < ALL_ETFS.length; i++) {
    var etf = ALL_ETFS[i];
    process.stdout.write('[' + String(i+1).padStart(3) + '/' + ALL_ETFS.length + '] ' + etf.code + ' ' + etf.name.slice(0,8) + ' ... ');

    try {
      var info = await fetchETFIndex(etf.code, etf.market);
      if (info && info.trackName) {
        results.push(Object.assign({}, etf, {
          trackName:  info.trackName,
          trackCode:  info.trackCode,
          scale2:     info.scale,
          trackingDiff: info.trackingDiff,
          fee:        info.fee,
          listed:     info.listed
        }));
        console.log('  -> [' + info.trackName + ']  规模:' + (info.scale||'-') + '亿');
      } else {
        errors.push({ code: etf.code, name: etf.name, msg: '无跟踪指数数据' });
        console.log('  !! 无跟踪指数数据');
      }
    } catch(e) {
      errors.push({ code: etf.code, name: etf.name, msg: e.message });
      console.log('  !! ' + e.message);
    }

    // 每20只休息2秒，防止限流
    if ((i+1) % 20 === 0) {
      console.log('\n--- 暂停2秒 ---');
      await new Promise(r => setTimeout(r, 2000));
    } else {
      await new Promise(r => setTimeout(r, 150));
    }
  }

  // ── 按跟踪指数分组 ──────────────────────
  var groups = {};
  results.forEach(function(r) {
    var key = r.trackName || '未知指数';
    if (!groups[key]) groups[key] = [];
    groups[key].push(r);
  });

  var sortedKeys = Object.keys(groups).sort(function(a,b){
    return groups[b].length - groups[a].length;
  });

  console.log('\n\n' + '═'.repeat(70));
  console.log('  抓取完成  成功:' + results.length + '  失败:' + errors.length);
  console.log('═'.repeat(70));
  console.log('\n【按跟踪指数分组】（括号内为保留的那只）\n');

  var toKeep = [];  // 最终保留的ETF
  var removed = []; // 被剔除的ETF

  sortedKeys.forEach(function(idx) {
    var group = groups[idx];
    console.log('━━ ' + idx + ' (' + group.length + '只) ━━');
    // 按规模降序，保留最大的
    group.sort(function(a,b){ return (b.scale2||b.size||0) - (a.scale2||a.size||0); });
    group.forEach(function(e, i) {
      var mark = i === 0 ? ' ✅ 保留' : ' ❌ 剔除';
      console.log('    ' + mark + '  ' + e.code + ' ' + e.name + '  规模:' + (e.scale2||e.size||'-') + '亿');
    });
    if (group[0]) toKeep.push(group[0]);
    removed.push(...group.slice(1));
  });

  console.log('\n总结: ' + results.length + '只获取到跟踪指数');
  console.log('保留: ' + toKeep.length + '只   剔除: ' + removed.length + '只');
  console.log('未获取到跟踪指数: ' + errors.length + '只');

  // 保存两份
  fs.writeFileSync(
    path.join(__dirname, 'data', 'etf_index_raw.json'),
    JSON.stringify({ results: results, errors: errors, groups: groups }, null, 2),
    'utf8'
  );
  fs.writeFileSync(
    path.join(__dirname, 'data', 'etf_pool_dedup_candidates.json'),
    JSON.stringify({ keep: toKeep, remove: removed, errors: errors }, null, 2),
    'utf8'
  );

  console.log('\n[OK] data/etf_index_raw.json         (完整抓取结果)');
  console.log('[OK] data/etf_pool_dedup_candidates.json (去重候选名单)');
  console.log('\n请确认后，我将用保留名单更新 etf_pool.js 和 scripts/scan/etf_pool.json');
}

main().catch(console.error);
