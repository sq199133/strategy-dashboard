const https = require('https');
const codes = ['sh159259','sh515700','sh513120','sh518880','sh513100','sh000300','sz399006','hkHSI','usSPX'];
const url = 'https://qt.gtimg.cn/q=' + codes.join(',');
https.get(url, (res) => {
  let data = '';
  res.on('data', (chunk) => data += chunk);
  res.on('end', () => {
    const lines = data.split('\n');
    lines.forEach(line => {
      if (line.includes('~')) {
        const parts = line.split('~');
        if (parts.length > 32) {
          const name = parts[1];
          const price = parts[3];
          const prevClose = parts[4];
          const changePct = parts[32];
          const vol = parts[6];
          const code = parts[0].replace(/v_pv_pv_/, '').replace(/"/g, '').trim();
          console.log(code + '|' + name + '|' + price + '|' + prevClose + '|' + changePct);
        }
      }
    });
  });
}).on('error', e => console.error('ERR:' + e.message));
