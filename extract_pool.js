const fs = require('fs');
const path = require('path');

// Read the source file
const poolPath = path.join(__dirname, 'data', 'etf_pool.js');
const content = fs.readFileSync(poolPath, 'utf8');

// Extract all ETFs using regex
const etfs = [];
const lines = content.split('\n');
for (const line of lines) {
  const codeMatch = line.match(/code:'([^']+)'/);
  const nameMatch = line.match(/name:'([^']+)'/);
  const marketMatch = line.match(/market:'([^']+)'/);
  const catMatch = line.match(/category:'([^']+)'/);
  
  if (codeMatch && nameMatch && marketMatch && catMatch) {
    etfs.push({
      code: codeMatch[1],
      name: nameMatch[1],
      market: marketMatch[1],
      category: catMatch[1]
    });
  }
}

// Simple deduplicate by code
const seen = new Set();
const unique = [];
for (const e of etfs) {
  if (!seen.has(e.code)) {
    seen.add(e.code);
    unique.push(e);
  }
}

console.log('Total ETFs: ' + unique.length);

// Write to scan directory
const outPath = path.join(__dirname, 'scripts', 'scan', 'etf_pool.json');
fs.writeFileSync(outPath, JSON.stringify(unique, null, 2), 'utf8');
console.log('Saved to: ' + outPath);