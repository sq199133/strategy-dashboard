// fetch_with_logging.js - 打印每个API调用的完整URL和返回
const { execSync } = require('child_process');
const fs = require('fs');

const symbol = process.argv[2] || 'sh510300';
const MAX_BARS = 600;

function curlWithLog(url, chunkNum) {
  console.log(`\n[c${chunkNum}] URL: ${url}`);
  
  try {
    const r = execSync(
      'curl.exe -s --max-time 15 -H "Referer: https://gu.qq.com/" --url ' + JSON.stringify(url),
      { encoding: 'utf8', timeout: 20000, windowsHide: true, maxBuffer: 10*1024*1024 }
    );
    
    const trimmed = r.trim();
    console.log(`  返回长度: ${trimmed.length}`);
    
    // 解析
    const j = JSON.parse(trimmed);
    const data = j.data && j.data[symbol];
    const bars = (data && (data.qfqday || data.day)) || [];
    
    console.log(`  解析条数: ${bars.length}`);
    if (bars.length > 0) {
      console.log(`  最新: ${bars[0][0]}`);
      console.log(`  最早: ${bars[bars.length-1][0]}`);
    }
    
    return bars;
  } catch(e) {
    console.log(`  ❌ 错误: ${e.message}`);
    return [];
  }
}

async function test() {
  console.log('=== 带日志的API调用测试 ===\n');
  console.log(`标的: ${symbol}\n`);
  
  let endDate = '2026-12-31';
  
  for (let chunk = 0; chunk < 5; chunk++) {
    const url = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,2000-01-01,${endDate},${MAX_BARS},qfq`;
    
    const bars = curlWithLog(url, chunk + 1);
    
    if (bars.length === 0) {
      console.log('  无数据，停止');
      break;
    }
    
    // 更新endDate
    const oldest = bars[bars.length - 1][0];
    console.log(`  更新endDate: ${oldest} - 1天`);
    
    const d = new Date(oldest);
    d.setDate(d.getDate() - 1);
    endDate = d.toISOString().split('T')[0];
    console.log(`  → ${endDate}`);
    
    await new Promise(r => setTimeout(r, 1000));
  }
}

test();
