// test_api_raw.js - 直接打印API原始返回
const { execSync } = require('child_process');

const symbol = 'sh510300';

// 测试1：未来日期
const url1 = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,2000-01-01,2026-12-31,600,qfq`;
console.log('【测试1】endDate=2026-12-31 (未来)');
console.log('URL:', url1);
console.log('');

try {
  const r1 = execSync(
    'curl.exe -s --max-time 15 -H "Referer: https://gu.qq.com/" "' + url1 + '"',
    { encoding: 'utf8', timeout: 20000, windowsHide: true }
  );
  console.log('返回长度:', r1.length);
  console.log('返回前500字符:');
  console.log(r1.substring(0, 500));
  console.log('');
  
  // 解析
  try {
    const j1 = JSON.parse(r1);
    const data1 = j1.data && j1.data[symbol];
    const bars1 = (data1 && (data1.qfqday || data1.day)) || [];
    console.log('解析成功，条数:', bars1.length);
    if (bars1.length > 0) {
      console.log('最新:', bars1[0][0]);
      console.log('最早:', bars1[bars1.length-1][0]);
    }
  } catch(e) {
    console.log('解析失败:', e.message);
  }
} catch(e) {
  console.log('请求失败:', e.message);
}

console.log('\n' + '='.repeat(50) + '\n');

// 测试2：过去日期
const url2 = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,2000-01-01,2023-01-01,600,qfq`;
console.log('【测试2】endDate=2023-01-01 (过去)');
console.log('URL:', url2);
console.log('');

try {
  const r2 = execSync(
    'curl.exe -s --max-time 15 -H "Referer: https://gu.qq.com/" "' + url2 + '"',
    { encoding: 'utf8', timeout: 20000, windowsHide: true }
  );
  console.log('返回长度:', r2.length);
  console.log('返回前500字符:');
  console.log(r2.substring(0, 500));
  console.log('');
  
  // 解析
  try {
    const j2 = JSON.parse(r2);
    const data2 = j2.data && j2.data[symbol];
    const bars2 = (data2 && (data2.qfqday || data2.day)) || [];
    console.log('解析成功，条数:', bars2.length);
    if (bars2.length > 0) {
      console.log('最新:', bars2[0][0]);
      console.log('最早:', bars2[bars2.length-1][0]);
    }
  } catch(e) {
    console.log('解析失败:', e.message);
  }
} catch(e) {
  console.log('请求失败:', e.message);
}
