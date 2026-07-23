// fetch_sina_complete.js - 使用新浪API下载完整历史数据（覆盖式）
// 用法: node fetch_sina_complete.js [start_idx] [end_idx]
// 特点: 强制重新下载，不使用已有数据

const https = require('https');
const fs = require('fs');
const path = require('path');

const POOL_FILE = 'D:\\QClaw_Trading\\data\\etf_pool_V1_full.json';
const HIST_DIR = 'D:\\QClaw_Trading\\data\\history';
const DATLEN = 10000; // 新浪API最大支持

// 从代码判断市场前缀
function getSinaCode(code) {
  const numPrefix = parseInt(code.substring(0, 2));
  if (numPrefix >= 50 && numPrefix <= 60) {
    return 'sh' + code;
  }
  return 'sz' + code;
}

// 使用https.get获取新浪数据
function fetchSina(symbol, datalen) {
  return new Promise((resolve, reject) => {
    const url = `https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=${symbol}&scale=240&ma=no&datalen=${datalen}`;
    
    const req = https.get(url, {
      headers: {
        'Referer': 'https://finance.sina.com.cn/',
        'User-Agent': 'Mozilla/5.0'
      },
      timeout: 15000
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(data.trim()));
    });
    
    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('timeout'));
    });
  });
}

// 解析新浪数据
function parseSinaData(raw) {
  if (!raw || raw === 'null' || raw === '') return [];
  try {
    const json = JSON.parse(raw);
    if (!Array.isArray(json) || json.length === 0) return [];
    
    return json.map(item => ({
      date: item.day || item.date,
      open: parseFloat(item.open),
      high: parseFloat(item.high),
      low: parseFloat(item.low),
      close: parseFloat(item.close),
      vol: parseInt(item.volume) || 0,
      amount: parseFloat(item.amount) || 0
    })).filter(item => item.date && !isNaN(item.open));
  } catch(e) {
    return [];
  }
}

// 睡眠
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// 下载单只ETF
async function fetchETF(symbol, code, name, idx, total) {
  process.stdout.write(`[${idx}/${total}] ${symbol} ${name}... `);
  
  try {
    const raw = await fetchSina(symbol, DATLEN);
    
    if (!raw || raw === 'null') {
      console.log('⚠️  返回为空');
      return null;
    }
    
    const records = parseSinaData(raw);
    
    if (records.length === 0) {
      console.log('⚠️  数据解析失败');
      return null;
    }
    
    // 按日期升序排列（方便后续使用）
    records.sort((a, b) => a.date.localeCompare(b.date));
    
    console.log(`✅ ${records.length}条 (${records[0].date} ~ ${records[records.length-1].date})`);
    
    return records;
    
  } catch(e) {
    console.log(`❌ 失败: ${e.message}`);
    return null;
  }
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
  
  console.log('=== 新浪API完整历史下载 (方案A) ===');
  console.log(`ETF池: ${pool.length}只 | 批次: ${startIdx+1}-${endIdx}`);
  console.log(`目标: 获取从上市开始的完整历史\n`);
  
  let ok = 0, fail = 0;
  const failed = [];
  
  for (let i = 0; i < batch.length; i++) {
    const etf = batch[i];
    const idx = startIdx + i + 1;
    const symbol = getSinaCode(etf.code);
    const file = path.join(HIST_DIR, symbol + '.json');
    
    const records = await fetchETF(symbol, etf.code, etf.name, idx, pool.length);
    
    if (records && records.length > 0) {
      // 覆盖写入
      fs.writeFileSync(file, JSON.stringify({ records: records }, null, 2), 'utf8');
      ok++;
    } else {
      fail++;
      failed.push({ code: etf.code, name: etf.name, symbol: symbol });
    }
    
    // 延迟，防止被封
    if (i < batch.length - 1) {
      await sleep(500);
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
