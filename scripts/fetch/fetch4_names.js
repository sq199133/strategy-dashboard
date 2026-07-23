const http = require('http');
const fs = require('fs');

// Use exec to run curl which handles encoding properly
function curl(url, headers) {
  const hArgs = Object.entries(headers||{}).flatMap(([k,v]) => ['-H', k+': '+v]);
  const cmd = 'curl -s -H "Referer: http://finance.sina.com.cn" ' + hArgs.map(a=>'"'+a+'"').join(' ')+' "'+url+'"';
  try {
    const out = execSync(cmd, {encoding:'utf8', timeout:8000});
    return out;
  } catch(e) { return ''; }
}

const { execSync } = require('child_process');

// Fetch 4 codes from Sina HQ with GBK
const codes = ['sz159329','sz159100','sz159980','sz159985'];
console.log('===== 实时行情 =====\n');
codes.forEach(c => {
  const cmd = 'curl -s --compressed -H "Referer: http://finance.sina.com.cn" -H "User-Agent: Mozilla/5.0" "http://hq.sinajs.cn/list='+c+'"';
  try {
    const out = execSync(cmd, {encoding:'gbk', timeout:8000});
    if (out.includes('"') && !out.includes('"",')) {
      const m = out.match(/"([^"]+)"/);
      if (m) {
        const fields = m[1].split(',');
        console.log(c.toUpperCase() + ': ' + fields[0] + ' 昨收=' + fields[2] + ' 当前=' + fields[3]);
      }
    } else {
      console.log(c + ': 无数据');
    }
  } catch(e) { console.log(c + ': curl失败'); }
});

console.log('\n===== 新浪ETF列表匹配 =====\n');
const sina = JSON.parse(fs.readFileSync('sina_etf.json','utf8'));
const em = JSON.parse(fs.readFileSync('etf_all_raw.json','utf8'));
const pool = require('./etf_pool_v4.js');
const emMap = {};
em.forEach(x => emMap[x.code] = x.size);
const poolCodes = new Set(pool.map(x => x.code));

['159329','159100','159980','159985'].forEach(code => {
  const s = sina.find(x => x.code === code);
  console.log(code + ': 新浪ETF=' + (s?'✅ '+s.name:'❌不在列表') + ' | EM规模=' + (emMap[code]||'?') + '亿 | 已入池=' + poolCodes.has(code));
});
