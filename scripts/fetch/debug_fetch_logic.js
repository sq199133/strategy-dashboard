// debug_fetch_logic.js - 调试为什么只获取到649条而不是完整历史
const { execSync } = require('child_process');
const fs = require('fs');

const symbol = process.argv[2] || 'sh510300';
const HIST_DIR = 'D:\\QClaw_Trading\\data\\history';
const MAX_BARS = 600;

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
    const bars = (data && (data.qfqday || data.day)) || [];
    return bars.map(p => ({
      date: p[0],
      open: Number(p[1]),
      close: Number(p[2]),
      high: Number(p[3]),
      low: Number(p[4]),
      vol: parseInt(p[5]) || 0,
      amount: Number(p[6]) || 0
    })).filter(r => r.date && !isNaN(r.open));
  } catch(e) {
    return [];
  }
}

async function debugFetch(symbol) {
  let allRecords = [];
  let seen = new Set();
  let endDate = '2026-12-31';
  
  for (let chunk = 0; chunk < 10; chunk++) {
    const url = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,2000-01-01,${endDate},${MAX_BARS},qfq`;
    process.stdout.write(`c${chunk+1} `);
    
    const raw = curl(url);
    if (!raw) {
      console.log('\n❌ 连接失败');
      break;
    }
    
    const records = parseResponse(raw, symbol);
    if (records.length === 0) {
      console.log('\n❌ 无数据');
      break;
    }
    
    // 详细日志：这次获取了多少新数据
    let newCount = 0;
    records.forEach(r => {
      if (!seen.has(r.date)) {
        allRecords.push(r);
        seen.add(r.date);
        newCount++;
      }
    });
    
    console.log(`(${records.length}条, 新增${newCount}条, 总计${allRecords.length}条, 区间${records[records.length-1].date}~${records[0].date})`);
    
    if (newCount === 0) {
      console.log('⚠️  没有新数据，停止');
      break;
    }
    
    if (records.length < MAX_BARS - 10) {
      console.log('✅ 已到达最早数据');
      break;
    }
    
    // 更新endDate
    const oldest = records[records.length-1].date;
    const d = new Date(oldest);
    d.setDate(d.getDate() - 1);
    endDate = d.toISOString().split('T')[0];
    
    await new Promise(r => setTimeout(r, 500));
  }
  
  // 排序
  allRecords.sort((a, b) => a.date.localeCompare(b.date));
  
  console.log(`\n=== 最终结果 ===`);
  console.log(`总条数: ${allRecords.length}`);
  if (allRecords.length > 0) {
    console.log(`区间: ${allRecords[0].date} ~ ${allRecords[allRecords.length-1].date}`);
  }
}

debugFetch(symbol);
