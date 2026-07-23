var fs = require('fs');
var path = require('path');
var DATA_DIR = 'D:/QClaw_Trading/data/history';

var hs300raw = JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'sh000300.json'), 'utf8'));
console.log('hs300条数:', hs300raw.length, '格式:', typeof hs300raw[0]);

var etfraw = JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'sh510170.json'), 'utf8'));
console.log('etf records条数:', etfraw.records ? etfraw.records.length : 'NO RECORDS');
console.log('etf首条:', JSON.stringify(etfraw.records ? etfraw.records[0] : etfraw[0]));
console.log('etf末条:', JSON.stringify(etfraw.records ? etfraw.records[etfraw.records.length-1] : etfraw[etfraw.length-1]));

console.log('\nhs300末5个日期:');
for(var i=hs300raw.length-5; i<hs300raw.length; i++) console.log('  ', hs300raw[i].date, 'close:', hs300raw[i].close);

console.log('\netf末5个日期:');
var recs = etfraw.records || etfraw;
for(var i=recs.length-5; i<recs.length; i++) console.log('  ', recs[i].date, 'close:', recs[i].close);
