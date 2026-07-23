const fs = require('fs');
const path = require('path');

const file = 'D:\\QClaw_Trading\\data\\index_history\\hkHSI.json';
const data = JSON.parse(fs.readFileSync(file));

console.log('keys:', Object.keys(data));
console.log('has records:', !!data.records);

if (data.records) {
  const arr = Object.values(data.records);
  console.log('records count:', arr.length);
  console.log('first record:', arr[0]);
  console.log('last record:', arr[arr.length - 1]);
}
