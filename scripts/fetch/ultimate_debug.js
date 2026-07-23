// ultimate_debug.js - 逐字节对比手动测试 vs 脚本调用
const { execSync } = require('child_process');
const fs = require('fs');

const symbol = 'sh510300';

function curlRaw(url, label) {
  console.log(`\n【${label}】`);
  console.log('URL:', url);
  console.log('');
  
  try {
    const r = execSync(
      'curl.exe -s --max-time 15 -H "Referer: https://gu.qq.com/" --url ' + JSON.stringify(url),
      { encoding: 'utf8', timeout: 20000, windowsHide: true, maxBuffer: 10*1024*1024 }
    );
    
    console.log('返回长度:', r.length);
    
    // 解析
    const j = JSON.parse(r.trim());
    const data = j.data && j.data[symbol];
    const bars = (data && (data.qfqday || data.day)) || [];
    
    console.log('解析条数:', bars.length);
    if (bars.length > 0) {
      console.log('最新:', bars[0][0]);
      console.log('最早:', bars[bars.length-1][0]);
      
      // 保存原始返回供对比
      const filename = `D:\\QClaw_Trading\\data\\debug_${label.replace(/[^a-zA-Z0-9]/g, '_')}.json`;
      fs.writeFileSync(filename, JSON.stringify(bars, null, 2));
      console.log('已保存:', filename);
    }
    
    return bars;
  } catch(e) {
    console.log('错误:', e.message);
    return [];
  }
}

async function test() {
  console.log('=== 终极调试：对比手动 vs 脚本 ===\n');
  
  // 测试A：手动测试成功的URL（endDate=2023-01-01）
  const urlA = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,2000-01-01,2023-01-01,600,qfq`;
  const barsA = curlRaw(urlA, '测试A_手动成功');
  
  await new Promise(r => setTimeout(r, 2000));
  
  // 测试B：脚本中构造的URL（完全相同的参数）
  const endDateB = '2023-01-01';
  const urlB = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,2000-01-01,${endDateB},600,qfq`;
  const barsB = curlRaw(urlB, '测试B_脚本相同');
  
  await new Promise(r => setTimeout(r, 2000));
  
  // 测试C：脚本第2次循环后的URL（endDate=2023-11-23）
  const endDateC = '2023-11-23';
  const urlC = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,2000-01-01,${endDateC},600,qfq`;
  const barsC = curlRaw(urlC, '测试C_脚本第2次');
  
  // 对比结果
  console.log('\n\n=== 对比结果 ===');
  console.log('');
  
  if (barsA.length > 0 && barsB.length > 0) {
    if (barsA[0][0] === barsB[0][0] && barsA[barsA.length-1][0] === barsB[barsB.length-1][0]) {
      console.log('✅ 测试A和测试B返回相同 → URL构造正确');
    } else {
      console.log('❌ 测试A和测试B返回不同 → URL构造有差异！');
      console.log('  A最新:', barsA[0][0], ' B最新:', barsB[0][0]);
      console.log('  A最早:', barsA[barsA.length-1][0], ' B最早:', barsB[barsB.length-1][0]);
    }
  }
  
  console.log('');
  
  if (barsA.length > 0 && barsC.length > 0) {
    if (barsA[0][0] !== barsC[0][0]) {
      console.log('✅ 测试A和测试C返回不同 → endDate参数生效！');
      console.log('  A区间:', barsA[barsA.length-1][0], '~', barsA[0][0]);
      console.log('  C区间:', barsC[barsC.length-1][0], '~', barsC[0][0]);
    } else {
      console.log('❌ 测试A和测试C返回相同 → endDate参数无效！');
    }
  }
  
  console.log('\n=== 结论 ===');
  console.log('如果测试A/B/C都返回不同数据，说明API支持分页，脚本有bug');
  console.log('如果测试B/C返回相同数据，说明URL构造有问题');
}

test();
