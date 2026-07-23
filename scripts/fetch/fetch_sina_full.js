// fetch_sina_full.js - 使用新浪财经API下载完整历史数据
// 用法: node fetch_sina_full.js [start_idx] [end_idx]

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const POOL_FILE = 'D:\\QClaw_Trading\\data\\etf_pool_V1_full.json';
const HIST_DIR = 'D:\\QClaw_Trading\\data\\history';
const MAX_RECORDS = 10000; // 新浪支持的最大条数

// 从代码判断市场前缀
function getSinaCode(code) {
  const prefix = code.substring(0, 1);
  // ETF代码规则：51xxxx/56xxxx/58xxxx/60xxxx = 上海(sh)，其他 = 深圳(sz)
  const numPrefix = parseInt(code.substring(0, 2));
  if (numPrefix >= 50 && numPrefix <= 60) {
    return 'sh' + code;
  }
  return 'sz' + code;
}

// 使用curl调用新浪API
function curlSina(symbol) {
  // 新浪API：scale=240是日线，datalen=10000获取全部
  const url = `https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=${symbol}&scale=240&ma=no&datalen=${MAX_RECORDS}`;
  
  try {
    const r = execSync(
      'curl.exe -s --max-time 15 -H "Referer: https://finance.sina.com.cn/" ' + JSON.stringify(url),
      { encoding: 'utf8', timeout: 20000, windowsHide: true }
    );
    return r.trim();
  } catch(e) {
    return null;
  }
}

// 解析新浪数据格式
function parseSinaData(raw) {
  if (!raw || raw === 'null' || raw === '') return [];
  
  try {
    const json = JSON.parse(raw);
    if (!Array.isArray(json) || json.length === 0) return [];
    
    return json.map(item => ({
      date: item.day || item.date,
      open: parseFloat(item.open),
      close: parseFloat(item.close),
      high: parseFloat(item.high),
      low: parseFloat(item.low),
      vol: parseInt(item.volume) || 0,
      amount: parseFloat(item.amount) || 0
    })).filter(item => item.date && !isNaN(item.open));
  } catch(e) {
    console.log('  解析失败: ' + e.message);
    return [];
  }
}

// 睡眠函数
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// 下载单只ETF数据
async function fetchETF(symbol, code) {
  console.log(`  正在下载 ${symbol}...`);
  
  const raw = curlSina(symbol);
  if (!raw) {
    console.log(`  ❌ 网络请求失败`);
    return null;
  }
  
  const records = parseSinaData(raw);
  if (records.length === 0) {
    console.log(`  ⚠️ 数据为空`);
    return null;
  }
  
  console.log(`  ✅ 获取 ${records.length} 条数据: ${records[records.length-1].date} ~ ${records[0].date}`);
  return records;
}

// 主处理函数
async function processBatch(batch, startIdx) {
  let ok = 0, fail = 0, skip = 0;
  
  for (let i = 0; i < batch.length; i++) {
    const etf = batch[i];
    const gi = startIdx + i;
    const symbol = getSinaCode(etf.code);
    const file = path.join(HIST_DIR, symbol + '.json');
    
    console.log(`[${gi+1}/194] ${symbol} ${etf.name}...`);
    
    // 检查已有数据
    if (fs.existsSync(file)) {
      try {
        const d = JSON.parse(fs.readFileSync(file, 'utf8'));
        const r = d.records || [];
        if (r.length > 0) {
          const newest = r[0].date;
          // 如果数据已最新，跳过
          if (newest >= '2026-05-20') {
            console.log(`  SKIP (已有${r.length}条，最新: ${newest})`);
            skip++;
            continue;
          }
        }
      } catch(e) {}
    }
    
    // 下载数据
    const records = await fetchETF(symbol, etf.code);
    
    if (records && records.length > 0) {
      fs.writeFileSync(file, JSON.stringify({ records: records }), 'utf8');
      ok++;
    } else {
      // 如果新浪失败，尝试腾讯API作为备份
      console.log(`  ⚠️ 新浪失败，尝试腾讯API...`);
      const tencentRecords = await fetchTencentBackup(etf.code, symbol);
      if (tencentRecords && tencentRecords.length > 0) {
        fs.writeFileSync(file, JSON.stringify({ records: tencentRecords }), 'utf8');
        console.log(`  ✅ 腾讯备份成功: ${tencentRecords.length}条`);
        ok++;
      } else {
        console.log(`  ❌ 全部失败`);
        fail++;
      }
    }
    
    // 延迟，防止被封
    if (i < batch.length - 1) {
      await sleep(500);
    }
  }
  
  console.log(`\n=== 完成: ok=${ok} skip=${skip} fail=${fail} ===`);
}

// 腾讯API备份方案
async function fetchTencentBackup(code, symbol) {
  const { execSync } = require('child_process');
  const MAX_BARS = 600;
  let all = [];
  let endDate = '2026-12-31';
  
  for (let i = 0; i < 30; i++) {
    const url = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,2000-01-01,${endDate},${MAX_BARS},qfq`;
    
    try {
      const raw = execSync(
        'curl.exe -s --max-time 12 -H "Referer: https://gu.qq.com/" ' + JSON.stringify(url),
        { encoding: 'utf8', timeout: 15000, windowsHide: true }
      );
      
      if (!raw) break;
      
      const j = JSON.parse(raw);
      const data = j.data && j.data[symbol];
      const chunk = (data && (data.qfqday || data.day)) || [];
      
      if (chunk.length === 0) break;
      
      const records = chunk.map(p => ({
        date: p[0],
        open: Number(p[1]),
        close: Number(p[2]),
        high: Number(p[3]),
        low: Number(p[4]),
        vol: parseInt(p[5]) || 0,
        amount: Number(p[6]) || 0
      }));
      
      // 去重合并
      const seen = {};
      all.forEach(r => seen[r.date] = true);
      records.forEach(r => {
        if (!seen[r.date]) {
          all.push(r);
          seen[r.date] = true;
        }
      });
      
      all.sort((a, b) => b.date.localeCompare(a.date));
      
      if (chunk.length < MAX_BARS - 10) break;
      
      const oldest = records[records.length-1].date;
      const d = new Date(oldest);
      d.setDate(d.getDate() - 1);
      endDate = d.toISOString().split('T')[0];
      
      await sleep(300);
    } catch(e) {
      break;
    }
  }
  
  return all.length > 0 ? all : null;
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
  
  console.log(`=== 新浪API下载 (方案A) ===`);
  console.log(`ETF池: ${pool.length}只 | 批次: ${startIdx+1}-${endIdx}`);
  console.log(`目标: 获取完整历史数据\n`);
  
  await processBatch(batch, startIdx);
})();
