const fs = require('fs');

// 读取ETF池
let content = fs.readFileSync('D:\\QClaw_Trading\\data\\etf_pool_V1_full.json', 'utf8');
content = content.replace(/\bNaN\b/g, 'null');
const poolData = JSON.parse(content);
const codes = poolData.data.map(e => e.code);

// 读取history目录（带前缀）
const historyDir = 'D:\\QClaw_Trading\\data\\history';
const historyFiles = fs.readdirSync(historyDir)
  .filter(f => f.endsWith('.json'))
  .map(f => f.replace(/^(sh|sz)/, '').replace('.json', ''));

// 检查缺失
const missing = codes.filter(c => !historyFiles.includes(c));
const withData = codes.filter(c => historyFiles.includes(c));

console.log('=== 数据更新完成验证 ===');
console.log('ETF总数:', codes.length);
console.log('已下载:', withData.length);
console.log('缺失:', missing.length);
console.log('');

if (missing.length > 0) {
  console.log('缺失的ETF代码:');
  console.log(missing.join(', '));
} else {
  console.log('✅ 所有194只ETF数据已完整下载！');
}

// 抽样检查数据日期
console.log('');
console.log('=== 抽样检查数据日期 ===');
const samples = withData.slice(0, 10);
samples.forEach(code => {
  try {
    const prefix = (parseInt(code.substring(0, 2)) >= 50 && parseInt(code.substring(0, 2)) <= 60) ? 'sh' : 'sz';
    const file = historyDir + '\\' + prefix + code + '.json';
    const data = JSON.parse(fs.readFileSync(file, 'utf8'));
    const records = data.records || [];
    if (records.length > 0) {
      console.log(prefix + code + ': ' + records[records.length-1].date + ' ~ ' + records[0].date + ' (' + records.length + '条)');
    }
  } catch(e) {
    console.log(code + ': 读取失败');
  }
});
