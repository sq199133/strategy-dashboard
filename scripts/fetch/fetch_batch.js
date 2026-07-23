// Batch fetch/update ETF historical data for v5.1 pool
// Handles Tencent API's ~640 bar limit by fetching in date-range chunks
// Updates existing data that ends before 2025-12-31
// Trims data that extends beyond 2025-12-31
// Usage: node fetch_batch.js [start_idx] [batch_size]

const https = require('https');
const fs = require('fs');
const path = require('path');

const POOL_FILE = 'D:\\QClaw_Trading\\scripts\\scan\\etf_pool.json';
const HIST_DIR = 'D:\\QClaw_Trading\\data\\history';
const TARGET_END = '2025-12-31';
const MAX_BARS = 600;

const pool = JSON.parse(fs.readFileSync(POOL_FILE, 'utf8'));

function fetchChunk(sym, startDate, endDate) {
  return new Promise((resolve) => {
    const url = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${sym},day,${startDate},${endDate},${MAX_BARS},qfq`;
    const req = https.get(url, {
      headers: { 'Referer': 'https://gu.qq.com/', 'User-Agent': 'Mozilla/5.0' }
    }, (res) => {
      let chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => {
        try {
          const j = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          const d = j.data && j.data[sym];
          resolve({ data: d && (d.qfqday || d.day) || [] });
        } catch(e) { resolve({ data: [] }); }
      });
    });
    req.on('error', () => resolve({ data: [] }));
    req.setTimeout(20000, function() { this.destroy(); resolve({ data: [] }); });
  });
}

function convert(arr) {
  return arr.map(p => ({
    date: p[0], open: +p[1], close: +p[2],
    high: +p[3], low: +p[4], vol: parseInt(p[5]) || 0,
    amount: +p[6] || 0, chg: +p[7] || 0
  }));
}

async function fetchAllForSymbol(sym) {
  let all = [];
  let endDate = TARGET_END;
  
  for (let i = 0; i < 25; i++) {
    const res = await fetchChunk(sym, '2000-01-01', endDate);
    if (!res.data.length) break;
    
    const records = convert(res.data);
    const dates = records.map(r => r.date).sort();
    const chunkEarliest = dates[0];
    
    const existing = new Set(all.map(r => r.date));
    all.push(...records.filter(r => !existing.has(r.date)));
    
    if (res.data.length < MAX_BARS - 10) break;
    
    const d = new Date(chunkEarliest);
    d.setDate(d.getDate() - 1);
    endDate = d.toISOString().split('T')[0];
    await new Promise(r => setTimeout(r, 350));
  }
  
  return all;
}

async function main() {
  const startIdx = parseInt(process.argv[2]) || 0;
  const batchSize = parseInt(process.argv[3]) || 999;
  
  // Build all tasks
  const tasks = [];
  pool.forEach(etf => {
    const prefix = (etf.market === 'SZ') ? 'sz' : 'sh';
    const code = prefix + etf.code;
    const file = path.join(HIST_DIR, code + '.json');
    
    tasks.push({ code, name: etf.name, file, exists: fs.existsSync(file) });
  });
  
  const batch = tasks.slice(startIdx, startIdx + batchSize);
  let trimmed = 0, fetched = 0, failed = 0, noAction = 0;
  
  console.log(`Total pool: ${tasks.length}, Batch: ${startIdx}-${startIdx + batch.length - 1}`);
  console.log(`Target: trim/filter to ${TARGET_END}\n`);
  
  for (let i = 0; i < batch.length; i++) {
    const task = batch[i];
    const idx = startIdx + i;
    process.stdout.write(`[${idx+1}/${tasks.length}] ${task.code} ${task.name}... `);
    
    if (!task.exists) {
      // No file - fetch from scratch
      const records = await fetchAllForSymbol(task.code);
      if (records.length > 0) {
        records.sort((a, b) => b.date.localeCompare(a.date));
        fs.writeFileSync(task.file, JSON.stringify({ records }), 'utf8');
        const oldest = records[records.length - 1].date;
        console.log(`NEW ${records.length} bars (${oldest} ~ ${records[0].date})`);
        fetched++;
      } else {
        console.log(`FAILED (no data)`);
        failed++;
      }
      await new Promise(r => setTimeout(r, 500));
      continue;
    }
    
    // File exists - check if it needs work
    try {
      const existing = JSON.parse(fs.readFileSync(task.file, 'utf8'));
      const records = existing.records || [];
      if (!records.length) throw new Error('empty');
      
      const newest = records[0].date;
      const oldest = records[records.length - 1].date;
      
      if (newest > TARGET_END && oldest < TARGET_END) {
        // Data spans across TARGET_END - just trim
        const trimmed_ = records.filter(r => r.date <= TARGET_END);
        fs.writeFileSync(task.file, JSON.stringify({ records: trimmed_ }), 'utf8');
        console.log(`TRIMMED ${records.length} -> ${trimmed_.length} bars`);
        trimmed++;
        continue;
      }
      
      if (newest >= TARGET_END && oldest <= TARGET_END) {
        // Already good
        console.log(`OK ${records.length} bars (${oldest} ~ ${newest})`);
        noAction++;
        continue;
      }
      
      // Data ends before TARGET_END - need to fetch
      const newRecords = await fetchAllForSymbol(task.code);
      if (newRecords.length > 0) {
        // Merge: combine existing (which may have older data) with new
        const existingDates = new Set(newRecords.map(r => r.date));
        const olderData = records.filter(r => r.date < newRecords[newRecords.length-1].date && !existingDates.has(r.date));
        const merged = [...newRecords, ...olderData];
        merged.sort((a, b) => b.date.localeCompare(a.date));
        fs.writeFileSync(task.file, JSON.stringify({ records: merged }), 'utf8');
        console.log(`UPDATED ${records.length} -> ${merged.length} bars (${merged[merged.length-1].date} ~ ${merged[0].date})`);
        fetched++;
      } else {
        console.log(`FAILED (no new data, kept ${records.length} bars ending ${newest})`);
        failed++;
      }
      await new Promise(r => setTimeout(r, 500));
    } catch(e) {
      console.log(`ERROR ${e.message}`);
      failed++;
    }
  }
  
  console.log(`\nSummary: Trimmed=${trimmed}, Fetched/Updated=${fetched}, Failed=${failed}, NoAction=${noAction}`);
}

main().catch(e => { console.error(e); process.exit(1); });
