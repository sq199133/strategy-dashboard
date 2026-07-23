const path = 'D:/QClaw_Trading/scripts/scan/corr_engine.js';
const m = require(path);

(async () => {
  const etfList = [
    { code: '159259', name: '成长ETF', market: 'SZ' },
    { code: '515700', name: '新能源车', market: 'SH' },
    { code: '159350', name: '深证50', market: 'SZ' },
    { code: '518880', name: '黄金ETF', market: 'SH' },
    { code: '513100', name: '纳指ETF', market: 'SH' }
  ];
  
  const result = await m.calcCorrMatrix(etfList, 120);
  
  // calcCorrMatrix returns {matrix, etfs: results}
  // But the results array is local - it uses the etfList names
  // Let's print the matrix directly
  const codes = etfList.map(e => e.code);
  console.log('\nMatrix keys:', Object.keys(result.matrix));
  console.log('ETFs count:', result.etfs ? result.etfs.length : 'undefined');
  
  // Manual print
  const header = '            ' + etfList.map(e => (e.name.substring(0,6)).padEnd(9)).join('');
  console.log(header);
  
  codes.forEach((ci, idx) => {
    let row = (etfList[idx].name.substring(0,6)).padEnd(10);
    codes.forEach(cj => {
      const v = result.matrix[ci] && result.matrix[ci][cj] !== undefined ? result.matrix[ci][cj] : '?';
      row += (typeof v === 'number' ? v.toFixed(3).padEnd(9) : String(v).padEnd(9));
    });
    console.log(row);
  });
  
  process.exit(0);
})();
