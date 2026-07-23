var js = require('./data/etf_pool.js');
var json = require('./scripts/scan/etf_pool.json');

var jsCodes = js.map(e=>e.code);
var jsonCodes = json.map(e=>e.code);
var uniqueJs = [...new Set(jsCodes)];
var uniqueJson = [...new Set(jsonCodes)];

console.log('data/etf_pool.js  总条目:', js.length, '  去重后:', uniqueJs.length);
console.log('scan/etf_pool.json 总条目:', json.length, '  去重后:', uniqueJson.length);

if (js.length !== uniqueJs.length) {
  var dups = jsCodes.filter((c,i)=>jsCodes.indexOf(c)!==i);
  console.log('data/etf_pool.js 重复代码:', dups);
}
if (json.length !== uniqueJson.length) {
  var dups2 = jsonCodes.filter((c,i)=>jsonCodes.indexOf(c)!==i);
  console.log('scan/etf_pool.json 重复代码:', dups2);
}

// 找出json独有的
var onlyInJson = jsonCodes.filter(c=>!jsCodes.includes(c));
var onlyInJs = jsCodes.filter(c=>!jsonCodes.includes(c));
console.log('\n仅在 scripts/scan/etf_pool.json 的代码:', onlyInJson.length ? onlyInJson : '无');
console.log('仅在 data/etf_pool.js 的代码:', onlyInJs.length ? onlyInJs : '无');

// 打印json的前几条
console.log('\nscan/etf_pool.json 前10条:');
json.slice(0,10).forEach(e=>console.log(' ', e.code, e.name, e.category));
