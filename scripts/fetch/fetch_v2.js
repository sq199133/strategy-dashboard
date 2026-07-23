// fetch_v2.js - 使用curl.exe获取ETF历史K线（解决node fetch TLS问题）
// 用法: node fetch_v2.js [start_idx] [end_idx]

var execSync = require('child_process').execSync;
var fs = require('fs');
var path = require('path');

var POOL_FILE = 'D:\\QClaw_Trading\\scripts\\scan\\etf_pool.json';
var HIST_DIR = 'D:\\QClaw_Trading\\data\\history';
var TARGET_END = '2025-12-31';
var MAX_BARS = 600;

var pool = JSON.parse(fs.readFileSync(POOL_FILE, 'utf8'));

function curl(url) {
  try {
    var r = execSync(
      'curl.exe -s --max-time 12 -H "Referer: https://gu.qq.com/" --url ' + JSON.stringify(url),
      { encoding: 'utf8', timeout: 15000, windowsHide: true }
    );
    return r;
  } catch(e) {
    return null;
  }
}

function fetchChunk(sym, startDate, endDate) {
  var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' +
    sym + ',day,' + startDate + ',' + endDate + ',' + MAX_BARS + ',qfq';
  var raw = curl(url);
  if (!raw) return [];
  try {
    var j = JSON.parse(raw);
    var data = j.data && j.data[sym];
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

function sleep(ms, cb) {
  setTimeout(cb, ms);
}

function fetchAll(code, name, cb) {
  var all = [];
  var endDate = TARGET_END;
  var i = 0;

  function next() {
    if (i >= 25) { cb(all); return; }
    process.stdout.write('c' + (i+1) + ' ');
    var data = fetchChunk(code, '2000-01-01', endDate);
    if (!data.length) { cb(all); return; }

    var records = convert(data);
    var seen = {};
    all.forEach(function(r) { seen[r.date] = true; });
    records.forEach(function(r) {
      if (!seen[r.date]) { all.push(r); seen[r.date] = true; }
    });
    all.sort(function(a, b) { return b.date.localeCompare(a.date); });

    if (data.length < MAX_BARS - 10) { cb(all); return; }
    var oldest = records[records.length-1].date;
    var d = new Date(oldest);
    d.setDate(d.getDate() - 1);
    endDate = d.toISOString().split('T')[0];
    i++;
    sleep(300, next);
  }

  next();
}

var startIdx = parseInt(process.argv[2]) || 0;
var endIdx = parseInt(process.argv[3]) || pool.length;
var batch = pool.slice(startIdx, endIdx);

console.log('Pool: ' + pool.length + ' | Batch: ' + startIdx + '-' + (endIdx-1));
console.log('');

var ok = 0, fail = 0, skip = 0, done = 0;

function processNext() {
  if (done >= batch.length) {
    console.log('');
    console.log('=== DONE: ok=' + ok + ' skip=' + skip + ' fail=' + fail + ' ===');
    return;
  }

  var etf = batch[done];
  var prefix = etf.market === 'SZ' ? 'sz' : 'sh';
  var code = prefix + etf.code;
  var file = path.join(HIST_DIR, code + '.json');
  var gi = startIdx + done;

  process.stdout.write('[' + (gi+1) + '/' + pool.length + '] ' + code + ' ' + etf.name + '... ');

  if (fs.existsSync(file)) {
    try {
      var d = JSON.parse(fs.readFileSync(file, 'utf8'));
      var r = d.records || [];
      if (r.length > 0) {
        var newest = r[0].date;
        var oldest = r[r.length-1].date;
        if (newest >= TARGET_END && oldest <= TARGET_END) {
          console.log('SKIP ' + r.length + 'bars ' + oldest + '~' + newest);
          skip++;
          done++;
          processNext();
          return;
        }
      }
    } catch(e) {}
  }

  fetchAll(code, etf.name, function(records) {
    if (records.length > 0) {
      fs.writeFileSync(file, JSON.stringify({ records: records }), 'utf8');
      console.log('OK ' + records.length + 'bars ' + records[records.length-1].date + '~' + records[0].date);
      ok++;
    } else {
      console.log('FAIL');
      fail++;
    }
    done++;
    if (done < batch.length) sleep(400, processNext);
    else {
      console.log('=== DONE: ok=' + ok + ' skip=' + skip + ' fail=' + fail + ' ===');
    }
  });
}

processNext();
