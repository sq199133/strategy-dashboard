const https = require('https');
const req = https.get('https://www.baidu.com', res => {
  let data = '';
  res.on('data', d => data += d);
  res.on('end', () => console.log('https ok, len:', data.length));
});
req.on('error', e => console.log('https err:', e.message));
