const { execSync } = require('child_process');
const fs = require('fs');

// Fetch 4 codes via curl with GBK encoding
const codes = ['sz159329', 'sz159100', 'sz159980', 'sz159985'];
console.log('===== 实时行情 + 名称 =====\n');
codes.forEach(c => {
  try {
    const out = execSync('curl -s --compressed -H "Referer: http://finance.sina.com.cn" -H "User-Agent: Mozilla/5.0" "http://hq.sinajs.cn/list=' + c + '"', { encoding: 'binary', timeout: 8000 });
    const buf = Buffer.from(out, 'binary');
    const text = buf.toString('gbk');
    if (text.includes('"') && !text.includes('"",')) {
      const m = text.match(/"([^"]+)"/);
      if (m) {
        const f = m[1].split(',');
        console.log(c.toUpperCase() + ': ' + f[0] + ' | 昨收=' + f[2] + ' 当前=' + f[3]);
      }
    } else {
      console.log(c + ': 无数据');
    }
  } catch(e) {
    console.log(c + ': 请求失败');
  }
});

console.log('\n===== 已确认名称对照 =====\n');
console.log('159329 = 沙特ETF (新能源/商品类)');
console.log('159100 = 巴西 (跨境QDII·南美新兴)');
console.log('159980 = 待确认（需EM接口）');
console.log('159985 = 待确认（需EM接口）');

// Try EM for remaining two
console.log('\n===== 东方财富核实 =====\n');
['159980', '159985'].forEach(c => {
  try {
    const out = execSync('curl -s "http://fundgz.1234567.com.cn/js/' + c + '.js?rt=1"', { encoding: 'utf8', timeout: 8000 });
    console.log(c + ' EM: ' + out.trim());
  } catch(e) {
    console.log(c + ': EM请求失败');
  }
});
