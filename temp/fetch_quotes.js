const https = require('https');
function fetch(code) {
  return new Promise((resolve, reject) => {
    const url = 'https://qt.gtimg.cn/q=' + code;
    https.get(url, {headers:{'User-Agent':'Mozilla/5.0'}}, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => resolve(data));
    }).on('error', reject);
  });
}
(async () => {
  const codes = [
    ['sh000300','HS300'],
    ['sz399006','CYB'],
    ['sh000001','SH'],
    ['sz399001','SZC'],
    ['hkHSI','HSI'],
    ['usSPX','SPX'],
    ['sz159259','CZETF'],
    ['sh515700','XNYC'],
    ['sh513120','GKCXY'],
    ['sh518880','HJ'],
    ['sh513100','NZ'],
    ['sh000905','ZZ500'],
    ['sh000852','ZZ1000'],
    ['hkHSCTECH','HSTECH'],
    ['sh511010','GZ'],
    ['sz159100','BAX'],
    ['sh513000','RJ225'],
    ['sz159329','SAETF'],
  ];
  for (const [c, name] of codes) {
    try {
      const data = await fetch(c);
      const m = data.match(/v_([\w]+)=\"([^\"]+)\"/);
      if (m) {
        const p = m[2].split('~');
        console.log(name + '|' + c + '|' + p[1] + '|' + p[3] + '|' + p[4] + '|' + p[5] + '|' + p[32]);
      } else {
        console.log(name + '|' + c + '|NODATA');
      }
    } catch(e) {
      console.log(name + '|' + c + '|ERROR');
    }
  }
})();
