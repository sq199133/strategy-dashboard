// fetch_tencent_fixed.js - 修复分页bug，正确获取完整历史
// 用法: node fetch_tencent_fixed.js [start_idx] [end_idx]

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const POOL_FILE = 'D:\\QClaw_Trading\\data\\etf_pool_V1_full.json';
const HIST_DIR = 'D:\\QClaw_Trading\\data\\history';
const MAX_BARS = 600;

// 从代码判断市场
function getMarket(code) {
  const prefix = parseInt(code.substring(0, 2));
  if (prefix >= 50 && prefix <= 60) return 'SH';
  return 'SZ';
}

// 调用腾讯API
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

// 解析响应（返回原始格式）
function parseResponseRaw(raw, sym) {
  if (!raw) return [];
  try {
    const j = JSON.parse(raw);
    const data = j.data && j.data[sym];
    return (data && (data.qfqday || data.day)) || [];
  } catch(e) {
    return [];
  }
}

// 转换为标准格式
function convert(bars) {
  return bars.map(p => ({
    date: p[0],
    open: Number(p[1]),
    close: Number(p[2]),
    high: Number(p[3]),
    low: Number(p[4]),
    vol: parseInt(p[5]) || 0,
    amount: Number(p[6]) || 0
  })).filter(r => r.date && !isNaN(r.open));
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// 下载单只ETF的完整历史（修复版）
async function fetchCompleteFixed(symbol) {
  let allRecords = [];
  let seen = new Set();
  let endDate = '2026-12-31';
  let chunkCount = 0;
  
  while (chunkCount < 50) {
    const url = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,2000-01-01,${endDate},${MAX_BARS},qfq`;
    process.stdout.write(`c${chunkCount+1} `);
    
    const raw = curl(url);
    if (!raw) {
      console.log('\n❌ 连接失败');
      break;
    }
    
    const bars = parseResponseRaw(raw, symbol);
    if (bars.length === 0) {
      console.log('\n❌ 无数据');
      break;
    }
    
    // 转换为标准格式
    const records = convert(bars);
    
    // 去重并添加
    let newCount = 0;
    records.forEach(r => {
      if (!seen.has(r.date)) {
        allRecords.push(r);
        seen.add(r.date);
        newCount++;
      }
    });
    
    console.log(`(${records.length}条, 新增${newCount}条)`);
    
    // 如果这一批没有新数据，结束
    if (newCount === 0) {
      break;
    }
    
    // 如果返回的数据少于MAX_BARS，说明已经到底了
    if (records.length < MAX_BARS - 10) {
      console.log('✅ 已到达最早数据');
      break;
    }
    
    // 【关键修复】使用【本次API返回的最早日期】来更新endDate
    // 注意：API返回的是降序（最新在前），所以bars[bars.length-1]是最早日期
    const oldestInThisChunk = bars[bars.length - 1][0];
    const d = new Date(oldestInThisChunk);
    d.setDate(d.getDate() - 1);
    endDate = d.toISOString().split('T')[0];
    
    console.log(`  更新endDate: ${endDate}`);
    
    chunkCount++;
    
    // 延迟
    await sleep(500);
  }
  
  // 按日期升序排列
  allRecords.sort((a, b) => a.date.localeCompare(b.date));
  
  return allRecords;
}

// 主程序
(async () => {
  // 读取ETF池
  let poolData;
  try {
    let content = fs.readFileSync(POOL_FILE, 'utf8');
    content = content.replace(/\bNaN\b/g, 'null');
    poolData = JSON.parse(content);
  } catch(e) {
    console.error('读取ETF池失败:', e.message);
    process.exit(1);
  }
  
  const pool = poolData.data;
  const startIdx = parseInt(process.argv[2]) || 0;
  const endIdx = parseInt(process.argv[3]) || pool.length;
  const batch = pool.slice(startIdx, endIdx);
  
  console.log('=== 腾讯API完整历史下载（修复版v2） ===');
  console.log(`ETF总数: ${pool.length} | 批次: ${startIdx+1}-${endIdx}`);
  console.log(`目标: 通过分页获取完整历史\n`);
  
  let ok = 0, fail = 0;
  const failed = [];
  
  for (let i = 0; i < batch.length; i++) {
    const etf = batch[i];
    const idx = startIdx + i + 1;
    const market = getMarket(etf.code);
    const prefix = market === 'SZ' ? 'sz' : 'sh';
    const symbol = prefix + etf.code;
    const file = path.join(HIST_DIR, symbol + '.json');
    
    process.stdout.write(`[${idx}/${pool.length}] ${symbol} ${etf.name}... `);
    
    try {
      const records = await fetchCompleteFixed(symbol);
      
      if (records.length > 0) {
        // 保存
        fs.writeFileSync(file, JSON.stringify({ records: records }, null, 2), 'utf8');
        console.log(`\n✅ ${records.length}条 (${records[0].date} ~ ${records[records.length-1].date})`);
        ok++;
      } else {
        console.log('\n❌ 无数据');
        fail++;
        failed.push({ code: etf.code, name: etf.name, symbol: symbol });
      }
    } catch(e) {
      console.log(`\n❌ 错误: ${e.message}`);
      fail++;
      failed.push({ code: etf.code, name: etf.name, symbol: symbol });
    }
    
    // 延迟
    if (i < batch.length - 1) {
      await sleep(800);
    }
  }
  
  console.log(`\n=== 下载完成 ===`);
  console.log(`✅ 成功: ${ok}`);
  console.log(`❌ 失败: ${fail}`);
  
  if (failed.length > 0) {
    console.log(`\n失败列表:`);
    failed.forEach(f => console.log(`  ${f.symbol} ${f.name} (${f.code})`));
  }
})();
