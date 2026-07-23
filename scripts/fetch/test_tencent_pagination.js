// test_tencent_pagination.js - 测试腾讯API是否支持分页获取完整历史
const { execSync } = require('child_process');

const symbol = 'sh510300'; // 沪深300ETF

function curl(url) {
  try {
    const r = execSync(
      'curl.exe -s --max-time 15 -H "Referer: https://gu.qq.com/" --url ' + JSON.stringify(url),
      { encoding: 'utf8', timeout: 20000, windowsHide: true }
    );
    return r.trim();
  } catch(e) {
    return null;
  }
}

function parseResponse(raw, sym) {
  if (!raw) return [];
  try {
    const j = JSON.parse(raw);
    const data = j.data && j.data[sym];
    return (data && (data.qfqday || data.day)) || [];
  } catch(e) {
    return [];
  }
}

console.log('=== 测试腾讯API分页功能 ===\n');
console.log('标的:', symbol);
console.log('');

// 测试1：获取最近600条
console.log('【测试1】获取最近600条 (endDate=2026-12-31)');
const url1 = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,2000-01-01,2026-12-31,600,qfq`;
const raw1 = curl(url1);
const bars1 = parseResponse(raw1, symbol);
console.log(`  返回: ${bars1.length}条`);
if (bars1.length > 0) {
  console.log(`  最早: ${bars1[bars1.length-1][0]}`);
  console.log(`  最新: ${bars1[0][0]}`);
}

console.log('');

// 测试2：获取2023年之前的600条
if (bars1.length > 0) {
  const oldestDate = bars1[bars1.length-1][0];
  const testEndDate = '2023-01-01';
  
  console.log(`【测试2】获取2023年之前的600条 (endDate=${testEndDate})`);
  const url2 = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,2000-01-01,${testEndDate},600,qfq`;
  const raw2 = curl(url2);
  const bars2 = parseResponse(raw2, symbol);
  console.log(`  返回: ${bars2.length}条`);
  if (bars2.length > 0) {
    console.log(`  最早: ${bars2[bars2.length-1][0]}`);
    console.log(`  最新: ${bars2[0][0]}`);
    
    // 检查是否与测试1的数据不同
    if (bars2.length > 0 && bars1.length > 0) {
      if (bars2[0][0] === bars1[bars1.length-1][0]) {
        console.log('  ⚠️ 数据相同！API可能不支持分页');
      } else {
        console.log('  ✅ 数据不同！API支持分页');
      }
    }
  }
}

console.log('');
console.log('=== 测试结论 ===');
console.log('如果两次返回的数据不同，则说明腾讯API支持分页，可以获取完整历史');
console.log('如果两次返回的数据相同，则只能获取最近600条');
