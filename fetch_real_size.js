// fetch_real_size.js
// 从天天基金获取真实AUM规模，替换etf_pool.js中的size字段
const https = require('https');
const fs   = require('fs');
const path = require('path');

const ALL_ETFS = require('./data/etf_pool.js');

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://fundf10.eastmoney.com/'
      }
    }, res => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => resolve(data));
    });
    req.on('error', reject);
    req.setTimeout(10000, () => { req.destroy(); reject(new Error('timeout')); });
  });
}

async function getFundSize(code) {
  var url = 'https://fundgz.1234567.com.cn/js/' + code + '.js?rt=1';
  try {
    var raw = await httpGet(url);
    var m = raw.match(/jsonpgz\((.+)\)/);
    if (!m) return null;
    var j = JSON.parse(m[1]);
    // 基金规模可能在另一个接口
    return { code: code, name: j.name, gsz: j.gsz, gztime: j.gztime };
  } catch(e) { return null; }
}

// 天天基金基金概况接口（含真实规模）
async function getFundProfile(code) {
  var url = 'https://fundf10.eastmoney.com/jjbx/' + code + '.html';
  try {
    var raw = await httpGet(url);
    // 提取基金规模
    var scaleMatch = raw.match(/基金规模[：:\s\u00A0]*([0-9,.]+)\s*亿元/);
    var trackMatch = raw.match(/跟踪指数[：:\s\u00A0]*<[^>]+>([^<]{2,50})/);
    return {
      code: code,
      scale: scaleMatch ? parseFloat(scaleMatch[1].replace(/,/g,'')) : null,
      trackIndex: trackMatch ? trackMatch[1].trim() : null
    };
  } catch(e) { return { code: code }; }
}

async function main() {
  console.log('获取真实AUM规模...\n');
  var sizes = {};

  for (var i = 0; i < ALL_ETFS.length; i++) {
    var etf = ALL_ETFS[i];
    process.stdout.write('[' + String(i+1).padStart(3) + '/' + ALL_ETFS.length + '] ' + etf.code + ' ... ');

    var info = await getFundProfile(etf.code);
    if (info.scale) {
      console.log('' + info.scale + '亿' + (info.trackIndex ? ' | ' + info.trackIndex : ''));
    } else {
      console.log('(无数据)');
    }

    sizes[etf.code] = {
      code: etf.code,
      oldSize: etf.size,
      scale: info.scale,
      trackIndex: info.trackIndex || ''
    };

    if ((i+1) % 20 === 0) await new Promise(r=>setTimeout(r,2000));
    else await new Promise(r=>setTimeout(r,150));
  }

  // 打印规模异常（old=0但新数据有）的ETF
  console.log('\n\n━━━━━ 规模异常（原来=0，现在有数据）━━━━━');
  Object.values(sizes).filter(s=>s.oldSize===0&&s.scale).forEach(s=>
    console.log('  ' + s.code + '  原:0亿 → 新:' + s.scale + '亿  ' + s.trackIndex)
  );

  fs.writeFileSync(path.join(__dirname,'data','etf_real_sizes.json'), JSON.stringify(sizes,null,2),'utf8');
  console.log('\n[OK] data/etf_real_sizes.json');
}

main().catch(console.error);
