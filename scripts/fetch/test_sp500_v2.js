// Test more S&P 500 data sources
'use strict';

async function test() {
  var sources = [
    // Alpha Vantage free
    { name: 'alphavantage', url: 'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=SPY&outputsize=compact&apikey=demo' },
    // Financial Modeling Prep
    { name: 'fmp_spy', url: 'https://financialmodelingprep.com/api/v3/historical-price-eod/full/SPY?serietype=line' },
    // Twelve Data
    { name: 'twelvedata', url: 'https://api.twelvedata.com/time_series?symbol=SPY&interval=1day&outputsize=10&apikey=demo' },
    // MarketWatch (might have CORS issues)
    { name: 'marketwatch', url: 'https://www.marketwatch.com/investing/index/spx/download-data?mod=chartdata' },
    // WSJ
    { name: 'wsj', url: 'https://quotes.wsj.com/index/SPX/historical-prices/download' },
    // Investing.com (direct)
    { name: 'investing', url: 'https://api.investing.com/api/financialdata/175/summary' },
    // Web search for free API
    { name: 'eodhd', url: 'https://eodhistoricaldata.com/api/eod/SPY.US?api_token=demo&fmt=json' },
    // Try fetching from a page that embeds the data
    { name: 'sina_finance', url: 'https://hq.sinajs.cn/list=gb_$spx' },
    { name: 'sina_finance2', url: 'https://hq.sinajs.cn/list=int_dji,int_spx,int_ndx' },
    // Sina HK for HSI
    { name: 'sina_hk', url: 'https://hq.sinajs.cn/list=rt_hkHSI' },
  ];

  for (var s of sources) {
    try {
      var r = await fetch(s.url, {
        signal: AbortSignal.timeout(8000),
        headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
      });
      var contentType = r.headers.get('content-type') || '';
      console.log(s.name + ' => ' + r.status + ' (' + contentType.substring(0, 30) + ')');
      if (r.ok) {
        var text = await r.text();
        var preview = text.substring(0, 200).replace(/\n/g, ' ');
        console.log('  preview: ' + preview);
      }
    } catch(e) {
      console.log(s.name + ' => ERROR: ' + e.message.substring(0, 80));
    }
  }
}

test();
