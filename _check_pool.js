const fs = require('fs');
const dirs = ['D:/QClaw_Trading/data', 'D:/QClaw_Trading/scripts/scan'];
dirs.forEach(dir => {
  console.log('\n=== ' + dir + ' ===');
  const f = fs.readdirSync(dir).filter(f => f.match(/etf_pool.*\.(js|json)$/));
  f.forEach(n => {
    const p = dir + '/' + n;
    const s = fs.statSync(p);
    const c = n.endsWith('.js') ? require(p) : JSON.parse(fs.readFileSync(p, 'utf8'));
    console.log(n + '  修改:' + s.mtime + '  大小:' + s.size + 'b  只数:' + c.length);
  });
});