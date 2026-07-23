// debug_tencent_pagination.js - 深度调试腾讯API分页
const { execSync } = require('child_process');

const symbol = 'sh510300';

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

function parseBars(raw, sym) {
  if (!raw) return [];
  try {
    const j = JSON.parse(raw);
    const data = j.data && j.data[sym];
    return (data && (data.qfqday || data.day)) || [];
  } catch(e) {
    return [];
  }
}

async function test() {
  console.log('=== 深度调试腾讯API分页 ===\n');
  console.log('标的:', symbol);
  console.log('');
  
  // 测试1：endDate设为未来（获取最近600条）
  console.log('【测试1】endDate=2026-12-31（未来）');
  const url1 = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,2000-01-01,2026-12-31,600,qfq`;
  const raw1 = curl(url1);
  const bars1 = parseBars(raw1, symbol);
  console.log(`  返回: ${bars1.length}条`);
  if (bars1.length > 0) {
    console.log(`  最新: ${bars1[0][0]}`);
    console.log(`  最早: ${bars1[bars1.length-1][0]}`);
  }
  
  await new Promise(r => setTimeout(r, 1000));
  
  // 测试2：endDate设为2023-01-01（应该获取2023年之前的数据）
  console.log('');
  console.log('【测试2】endDate=2023-01-01（过去）');
  const url2 = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,2000-01-01,2023-01-01,600,qfq`;
  const raw2 = curl(url2);
  const bars2 = parseBars(raw2, symbol);
  console.log(`  返回: ${bars2.length}条`);
  if (bars2.length > 0) {
    console.log(`  最新: ${bars2[0][0]}`);
    console.log(`  最早: ${bars2[bars2.length-1][0]}`);
  }
  
  await new Promise(r => setTimeout(r, 1000));
  
  // 测试3：endDate设为2020-01-01
  console.log('');
  console.log('【测试3】endDate=2020-01-01（更早）');
  const url3 = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,2000-01-01,2020-01-01,600,qfq`;
  const raw3 = curl(url3);
  const bars3 = parseBars(raw3, symbol);
  console.log(`  返回: ${bars3.length}条`);
  if (bars3.length > 0) {
    console.log(`  最新: ${bars3[0][0]}`);
    console.log(`  最早: ${bars3[bars3.length-1][0]}`);
  }
  
  // 对比测试2和测试3的结果
  console.log('');
  console.log('=== 对比结果 ===');
  if (bars2.length > 0 && bars3.length > 0) {
    if (bars2[bars2.length-1][0] === bars3[bars3.length-1][0]) {
      console.log('⚠️  测试2和测试3的最早日期相同！');
      console.log('    这说明改变endDate无效，API总是返回相同数据');
    } else {
      console.log('✅ 测试2和测试3返回不同数据，分页有效！');
    }
  }
  
  // 关键发现：检查API是否忽略endDate，总是返回最近600条
  console.log('');
  console.log('=== 关键发现 ===');
  if (bars1.length > 0 && bars2.length > 0) {
    if (bars1[0][0] === bars2[0][0]) {
      console.log('❌ 发现：测试1和测试2的【最新日期】相同！');
      console.log('    结论：腾讯API忽略endDate，总是返回【最近600条】');
      console.log('    解决方案：此API无法分页，需要换用其他数据源');
    } else {
      console.log('✅ 测试1和测试2返回不同数据，分页有效！');
    }
  }
}

test();
