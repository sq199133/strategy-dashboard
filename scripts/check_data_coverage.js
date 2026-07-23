const fs = require('fs');

// 读取ETF池
let content = fs.readFileSync('D:\\QClaw_Trading\\data\\etf_pool_V1_full.json', 'utf8');
content = content.replace(/\bNaN\b/g, 'null');
const poolData = JSON.parse(content);
const etfCodes = poolData.data.map(etf => etf.code);

// 读取history目录
const historyDir = 'D:\\QClaw_Trading\\data\\history';
const historyFiles = fs.readdirSync(historyDir)
  .filter(f => f.endsWith('.json'))
  .map(f => f.replace(/^(sh|sz)/, '').replace('.json', ''));

// 统计
const total = etfCodes.length;
const downloaded = etfCodes.filter(code => historyFiles.includes(code)).length;
const missing = etfCodes.filter(code => !historyFiles.includes(code));

console.log('=== ETF池V1全量版数据覆盖统计 ===');
console.log('标的池总数:', total);
console.log('已下载数量:', downloaded);
console.log('缺失数量:', missing.length);
console.log('');

if (missing.length > 0 && missing.length <= 50) {
  console.log('缺失的ETF代码:');
  console.log(missing.join(', '));
} else if (missing.length > 50) {
  console.log('缺失数量较多(' + missing.length + '只)，前30只:');
  console.log(missing.slice(0, 30).join(', ') + '...');
}

// 显示一些已下载的样本
console.log('');
console.log('已下载样本(前10只):');
const downloadedSamples = etfCodes.filter(code => historyFiles.includes(code)).slice(0, 10);
console.log(downloadedSamples.map(code => {
  const etf = poolData.data.find(e => e.code === code);
  return code + '(' + (etf ? etf.name : '?') + ')';
}).join(', '));
