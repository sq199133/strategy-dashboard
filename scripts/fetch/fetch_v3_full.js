// fetch_v3_full.js - 更新 etf_pool_V1_full.json (194只) 到最新数据
// 用法: node fetch_v3_full.js [start_idx] [end_idx]
// 需要 curl.exe 在 PATH 中

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const POOL_FILE = 'D:\\QClaw_Trading\\data\\etf_pool_V1_full.json';
const HIST_DIR = 'D:\\QClaw_Trading\\data\\history';
const TARGET_END = '2026-12-31';  // 改为未来日期，确保下载到最新
const MAX_BARS = 600;

// 从代码判断市场
function getMarket(code) {
  const prefix = code.substring(0, 2);
  // 上海：50xxxx, 51xxxx, 56xxxx, 58xxxx, 60xxxx 等
  if (parseInt(prefix) >= 50 && parseInt(prefix) <= 60) return 'SH';
  return 'SZ';
}

function curl(url) {
  try {
    const r = execSync(
      'curl.exe -s --max-time 12 -H "Referer: https://gu.qq.com/" --url ' + JSON.stringify(url),
      { encoding: 'utf8', timeout: 15000, windowsHide: true }
    );
    return r;
  } catch(e) {
    return null;
  }
}

function fetchChunk(sym, startDate, endDate) {
  const url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' +
    sym + ',day,' + startDate + ',' + endDate + ',' + MAX_BARS + ',qfq';
  const raw = curl(url);
  if (!raw) return [];
  try {
    const j = JSON.parse(raw);
    const data = j.data && j.data[sym];
    return (data && (data.qfqday || data.day)) || [];
  } catch(e) {
    return [];
  }
}

function convert(arr) {
  return arr.map(function(p) {
    return {
      date: p[0],
      open: Number(p[1]),
      close: Number(p[2]),
      high: Number(p[3]),
      low: Number(p[4]),
      vol: parseInt(p[5]) || 0,
      amount: Number(p[6]) || 0,
      chg: Number(p[7]) || 0
    };
  });
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchAll(code, sym) {
  let all = [];
  let endDate = TARGET_END;
  let i = 0;

  while (i < 25) {
    process.stdout.write('c' + (i+1) + ' ');
    const data = fetchChunk(sym, '2000-01-01', endDate);
    if (!data.length) break;

    const records = convert(data);
    const seen = {};
    all.forEach(function(r) { seen[r.date] = true; });
    records.forEach(function(r) {
      if (!seen[r.date]) { all.push(r); seen[r.date] = true; }
    });
    all.sort(function(a, b) { return b.date.localeCompare(a.date); });

    if (data.length < MAX_BARS - 10) break;
    const oldest = records[records.length-1].date;
    const d = new Date(oldest);
    d.setDate(d.getDate() - 1);
    endDate = d.toISOString().split('T')[0];
    i++;
    await sleep(300);
  }

  return all;
}

async function processNext(batch, idx, startIdx, ok, skip, fail) {
  if (idx >= batch.length) {
    console.log('');
    console.log('=== DONE: ok=' + ok + ' skip=' + skip + ' fail=' + fail + ' ===');
    return;
  }

  const etf = batch[idx];
  const market = getMarket(etf.code);
  const prefix = market === 'SZ' ? 'sz' : 'sh';
  const sym = prefix + etf.code;
  const file = path.join(HIST_DIR, sym + '.json');
  const gi = startIdx + idx;

  process.stdout.write('[' + (gi+1) + '/' + pool.length + '] ' + sym + ' ' + etf.name + '... ');

  // 检查已有数据
  let needFetch = true;
  if (fs.existsSync(file)) {
    try {
      const d = JSON.parse(fs.readFileSync(file, 'utf8'));
      const r = d.records || [];
      if (r.length > 0) {
        const newest = r[0].date;
        const oldest = r[r.length-1].date;
        // 如果数据已覆盖到目标日期且开始日期足够早，跳过
        if (newest >= '2026-05-01' && oldest <= '2020-01-01') {
          console.log('SKIP ' + r.length + 'bars ' + oldest + '~' + newest);
          skip++;
          await processNext(batch, idx+1, startIdx, ok, skip, fail);
          return;
        }
        // 如果数据比较新，尝试增量更新
        if (newest >= '2026-05-01') {
          console.log('RECENT ' + r.length + 'bars ' + oldest + '~' + newest + ' (need update)');
        }
      }
    } catch(e) {}
  }

  // 下载数据
  try {
    const records = await fetchAll(etf.code, sym);
    if (records.length > 0) {
      fs.writeFileSync(file, JSON.stringify({ records: records }), 'utf8');
      console.log('OK ' + records.length + 'bars ' + records[records.length-1].date + '~' + records[0].date);
      ok++;
    } else {
      console.log('FAIL');
      fail++;
    }
  } catch(e) {
    console.log('FAIL: ' + e.message);
    fail++;
  }

  await sleep(400);
  await processNext(batch, idx+1, startIdx, ok, skip, fail);
}

// 主程序
let poolData;
try {
  let content = fs.readFileSync(POOL_FILE, 'utf8');
  content = content.replace(/\bNaN\b/g, 'null');
  poolData = JSON.parse(content);
} catch(e) {
  console.error('Failed to read pool file:', e.message);
  process.exit(1);
}

const pool = poolData.data;
const startIdx = parseInt(process.argv[2]) || 0;
const endIdx = parseInt(process.argv[3]) || pool.length;
const batch = pool.slice(startIdx, endIdx);

console.log('Pool: ' + pool.length + ' | Batch: ' + startIdx + '-' + (endIdx-1));
console.log('Target END: ' + TARGET_END);
console.log('');

processNext(batch, 0, startIdx, 0, 0, 0);
