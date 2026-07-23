// Test various S&P 500 data sources
'use strict';

async function testYahoo() {
  var codes = ['%5EGSPC', '%5EIXIC', '%5EHSI'];
  var hosts = ['query1.finance.yahoo.com', 'query2.finance.yahoo.com'];
  for (var h of hosts) {
    for (var c of codes) {
      var url = 'https://' + h + '/v8/finance/chart/' + c + '?range=1mo&interval=1d';
      try {
        var r = await fetch(url, { signal: AbortSignal.timeout(8000) });
        console.log(h + '/' + c + ' => ' + r.status);
        if (r.ok) {
          var j = await r.json();
          var ts = j.chart && j.chart.result && j.chart.result[0];
          console.log('  points=' + (ts ? ts.timestamp.length : 0) + ' name=' + (ts ? ts.meta.symbol : ''));
        }
      } catch(e) { console.log(h + '/' + c + ' => ERROR ' + e.message); }
    }
  }
}

async function testWebFetch() {
  // Try fetching from a financial data website
  var urls = [
    'https://www.google.com/finance/quote/.INX:INDEXSP', // won't work but let's see
  ];
}

async function testStooq() {
  // Stooq.com provides free historical data
  var url = 'https://stooq.com/q/d/l/?s=^spx&d1=20260401&d2=20260421&i=d';
  try {
    var r = await fetch(url, { signal: AbortSignal.timeout(10000) });
    console.log('stooq => ' + r.status);
    if (r.ok) {
      var text = await r.text();
      var lines = text.trim().split('\n');
      console.log('  lines=' + lines.length + ' first=' + lines[0] + ' last=' + lines[lines.length - 1]);
    }
  } catch(e) { console.log('stooq => ERROR ' + e.message); }
}

async function testInvesting() {
  // Try fetching S&P 500 from various free sources
  var sources = [
    { name: 'stooq_spy', url: 'https://stooq.com/q/d/l/?s=spy.us&d1=20260401&d2=20260421&i=d' },
    { name: 'stooq_ndx', url: 'https://stooq.com/q/d/l/?s=^ndq&d1=20260401&d2=20260421&i=d' },
    { name: 'stooq_hsi', url: 'https://stooq.com/q/d/l/?s=^hsi&d1=20260401&d2=20260421&i=d' },
  ];
  for (var s of sources) {
    try {
      var r = await fetch(s.url, { signal: AbortSignal.timeout(10000) });
      console.log(s.name + ' => ' + r.status);
      if (r.ok) {
        var text = await r.text();
        var lines = text.trim().split('\n');
        console.log('  lines=' + lines.length + ' header=' + lines[0]);
        if (lines.length > 1) console.log('  last=' + lines[lines.length - 1]);
      }
    } catch(e) { console.log(s.name + ' => ERROR ' + e.message); }
  }
}

async function main() {
  console.log('=== Testing Yahoo Finance ===');
  await testYahoo();
  console.log('\n=== Testing Stooq ===');
  await testStooq();
  console.log('\n=== Testing Stooq (more indices) ===');
  await testInvesting();
}

main();
