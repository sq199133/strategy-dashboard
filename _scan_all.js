const fs = require('fs');
const path = require('path');

function scan(dir, depth) {
  if (depth > 3) return;
  try {
    const entries = fs.readdirSync(dir);
    entries.forEach(n => {
      if (n === 'node_modules' || n === '.git') return;
      const fp = path.join(dir, n);
      try {
        const s = fs.statSync(fp);
        if (s.isDirectory()) {
          scan(fp, depth + 1);
        } else if (n.match(/etf.*pool|pool.*etf/i)) {
          console.log(fp.replace(/\\/g, '/'));
        }
      } catch(e) {}
    });
  } catch(e) {}
}

console.log('=== Pool-related files ===');
scan('D:/QClaw_Trading', 0);
console.log('\n=== Any v5.x files ===');
scan2('D:/QClaw_Trading', 0);
function scan2(dir, depth) {
  if (depth > 3) return;
  try {
    fs.readdirSync(dir).forEach(n => {
      if (n === 'node_modules') return;
      const fp = path.join(dir, n);
      const s = fs.statSync(fp);
      if (s.isDirectory()) scan2(fp, depth+1);
      else if (n.match(/\.v5/i)) console.log(fp.replace(/\\/g,'/'));
    });
  } catch(e) {}
}