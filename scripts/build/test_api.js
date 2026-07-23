// Debug: test the API directly
const https = require('https');
const url = 'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5&po=1&np=1&fltt=2&invt=2&fid=f3&fs=b:MK0021&fields=f12,f13,f14,f2,f3,f6,f20';
https.get(url, { timeout: 10000 }, (res) => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    console.log('Status:', res.statusCode);
    console.log('Response length:', data.length);
    console.log('First 500 chars:', data.substring(0, 500));
    try {
      const j = JSON.parse(data);
      console.log('Parsed:', JSON.stringify(j).substring(0, 500));
    } catch(e) {
      console.log('Parse error:', e.message);
    }
  });
}).on('error', e => console.log('Error:', e.message));
