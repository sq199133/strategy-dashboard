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
  m.printCorrMatrix(result.matrix, result.etfs);
  process.exit(0);
})();
