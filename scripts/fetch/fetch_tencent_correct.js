// fetch_tencent_correct.js - 正确的腾讯API分页逻辑
// 关键发现：endDate必须在【最近600条】范围外，否则API忽略它
// 用法: node fetch_tencent_correct.js [start_idx] [end_idx]

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
      { encoding: 'utf8', timeout: 20000, windowsHide: true, maxBuffer: 10*1024*1024 }
    );
    return r.trim();
  } catch(e) {
    return null;
  }
}

// 解析响应
function parseResponse(raw, sym) {
  if (!raw) return [];
  try {
    const j = JSON.parse(raw);
    const data = j.data && j.data[sym];
    const bars = (data && (data.qfqday || data.day)) || [];
    return bars;
  } catch(e) {
    return [];
  }
}

// 转换格式
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

// 【正确】下载完整历史
async function fetchCorrectly(symbol) {
  let allRecords = [];
  let seen = new Set();
  
  // 第1步：获取最近600条，找到"锚点"
  console.log('  [第1步] 获取最近600条...');
  let url = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,2000-01-01,2026-12-31,${MAX_BARS},qfq`;
  let raw = curl(url);
  let bars = parseResponse(raw, symbol);
  
  if (bars.length === 0) {
    console.log('  ❌ 无数据');
    return [];
  }
  
  // 添加到结果
  let records = convert(bars);
  records.forEach(r => {
    if (!seen.has(r.date)) {
      allRecords.push(r);
      seen.add(r.date);
    }
  });
  
  console.log(`  获取到 ${records.length} 条 (${records[records.length-1].date} ~ ${records[0].date})`);
  
  // 第2步：向前分页（关键：endDate必须早于当前数据的最早日期）
  let earliestDate = records[records.length - 1].date; // 当前数据的最早日期
  let endDate = earliestDate;
  
  console.log(`  [第2步] 向前分页，起始endDate=${endDate}...`);
  
  let chunkCount = 0;
  while (chunkCount < 100) { // 最多100次（足够获取14年数据）
    // 计算新的endDate（当前最早日期减1天）
    const d = new Date(earliestDate);
    d.setDate(d.getDate() - 1);
    endDate = d.toISOString().split('T')[0];
    
    console.log(`  c${chunkCount+1}: endDate=${endDate}...`);
    
    url = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,2000-01-01,${endDate},${MAX_BARS},qfq`;
    raw = curl(url);
    bars = parseResponse(raw, symbol);
    
    if (bars.length === 0) {
      console.log('  ✅ 无更多数据');
      break;
    }
    
    records = convert(bars);
    
    // 去重
    let newCount = 0;
    records.forEach(r => {
      if (!seen.has(r.date)) {
        allRecords.push(r);
        seen.add(r.date);
        newCount++;
      }
    });
    
    console.log(`    返回 ${records.length} 条，新增 ${newCount} 条`);
    
    if (newCount === 0) {
      console.log('  ✅ 无更多新数据');
      break;
    }
    
    // 更新earliestDate
    const sorted = records.sort((a, b) => a.date.localeCompare(b.date));
    earliestDate = sorted[0].date;
    
    chunkCount++;
    
    // 延迟
    await sleep(500);
  }
  
  // 排序
  allRecords.sort((a, b) => a.date.localeCompare(b.date));
  
  console.log(`  ✅ 完成：共 ${allRecords.length} 条 (${allRecords[0].date} ~ ${allRecords[allRecords.length-1].date})`);
  
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
  
  console.log('=== 腾讯API完整历史下载（正确版） ===');
  console.log(`ETF总数: ${pool.length} | 批次: ${startIdx+1}-${endIdx}`);
  console.log(`目标: 正确分页获取完整历史\n`);
  
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
      const records = await fetchCorrectly(symbol);
      
      if (records.length > 0) {
        // 保存
        fs.writeFileSync(file, JSON.stringify({ records: records }, null, 2), 'utf8');
        console.log(`✅ ${records.length}条 (${records[0].date} ~ ${records[records.length-1].date})`);
        ok++;
      } else {
        console.log(`❌ 无数据`);
        fail++;
        failed.push({ code: etf.code, name: etf.name, symbol: symbol });
      }
    } catch(e) {
      console.log(`❌ 错误: ${e.message}`);
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
