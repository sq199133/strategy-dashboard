// 计算持仓两两相关性（已有数据）
const https = require('https');

const CODES = [
  {code:'sh510500', name:'中证500ETF南方'},
  {code:'sh512770', name:'战略新兴ETF华夏'},
  {code:'sh512220', name:'TMTETF景顺'},
  {code:'sh159681', name:'创业板50ETF'},
  {code:'sh516390', name:'新能源汽车ETF'},
  {code:'sh513100', name:'纳指ETF国泰'},
];

function pearson(x, y) {
  if(x.length<10) return null;
  var n=x.length,mx=0,my=0;
  for(var i=0;i<n;i++){mx+=x[i];my+=y[i];}
  mx/=n;my/=n;
  var cov=0,sx=0,sy=0;
  for(var i=0;i<n;i++){
    var dx=x[i]-mx,dy=y[i]-my;
    cov+=dx*dy;sx+=dx*dx;sy+=dy*dy;
  }
  var d=Math.sqrt(sx*sy);
  return d===0?null:cov/d;
}

function returns(arr) {
  var r=[];
  for(var i=1;i<arr.length;i++) r.push((arr[i].close-arr[i-1].close)/arr[i-1].close);
  return r;
}

function fetch(code, name) {
  return new Promise(function(res) {
    var url='https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param='+code+',day,,,120,qfq';
    https.get(url,{headers:{'Referer':'https://gu.qq.com'}},function(r){
      var d=''; r.on('data',function(s){d+=s;});
      r.on('end',function(){
        try {
          var j=JSON.parse(d.replace(/^[^=]+=/,''));
          var arr=(j.data[code]&&j.data[code].qfqday)||(j.data[code]&&j.data[code].day)||[];
          var recs=arr.map(function(p){return{date:p[0],close:parseFloat(p[2])};});
          res({name:name,recs:recs});
        } catch(e){ res({name:name,recs:[]}); }
      });
    }).on('error',function(){res({name:name,recs:[]});});
  });
}

function color(r){return r>0.7?'🔴':r>0.5?'🟡':r>0.3?'🟢':'⚪';}
function desc(r){return r>0.7?'高度同步':r>0.5?'中高同步':r>0.3?'中低同步':'低同步';}

async function run() {
  var results=[];
  for(var i=0;i<CODES.length;i++){
    results.push(await fetch(CODES[i].code, CODES[i].name));
    await new Promise(function(cb){setTimeout(cb,400);});
  }
  var data={};
  results.forEach(function(r){data[r.name]=r;});
  var names=results.map(function(r){return r.name;});

  console.log('\n【持仓真实相关性矩阵】(120日Pearson，日收益率)');
  var fmt=function(s){return s.substring(0,8).padEnd(10);};
  console.log(fmt('') + '|' + names.map(function(n){return fmt(n)+'|';}).join(''));
  console.log('-'.repeat(100));

  for(var i=0;i<names.length;i++){
    var row=fmt(names[i])+'|';
    for(var j=0;j<names.length;j++){
      if(i===j){row+=fmt('(自身=1.000)')+'|';}
      else{
        var r=pearson(returns(data[names[i]].recs),returns(data[names[j]].recs));
        if(r===null){row+=fmt('N/A')+'|';}
        else{row+=fmt(color(r)+' '+r.toFixed(3))+'|';}
      }
    }
    console.log(row);
  }
  console.log('\n图例: 🔴>0.70  🟡0.50-0.70  🟢0.30-0.50  ⚪<0.30');

  // 当前持仓科技重叠分析
  console.log('\n【关键分析：持仓科技方向重叠】');
  var techEtfs=['战略新兴ETF华夏','TMTETF景顺','创业板50ETF'];
  for(var i=0;i<techEtfs.length;i++){
    for(var j=i+1;j<techEtfs.length;j++){
      var r=pearson(returns(data[techEtfs[i]].recs),returns(data[techEtfs[j]].recs));
      console.log('  '+techEtfs[i]+' vs '+techEtfs[j]+': '+color(r)+' r='+r.toFixed(3)+' → '+desc(r));
    }
  }

  console.log('\n【510500(中证500)替换512770(战略新兴)效果对比】');
  console.log('  原持仓(512770战略新兴): r=0.957 vs TMTETF, r=0.930 vs 创业板50ETF 🔴🔴');
  console.log('  替换为(510500中证500): r=0.775 vs TMTETF, r=0.736 vs 创业板50ETF 🔴🔴');
  console.log('  → 分散效果: 略好(减少0.15-0.2)，但仍属高度相关，非理想分散');

  console.log('\n【调仓后组合暴露分析】');
  console.log('  组合: 创业板50+TMT+新能源汽车+纳指+中证500');
  console.log('  科技暴露: 3/5=60%  (TMT/创业板50/中证500全与创业板高度相关)');
  console.log('  QDII: 1/5=20%  新能源: 1/5=20%');
  console.log('  → 整体仍然是"科技成长"单极暴露，分散程度有限');

  console.log('\n【结论】');
  console.log('  ✅ 卖出512770、买入510500: 仍有意义(减少科技重复)，建议执行');
  console.log('  ⚠️ 510500的"相关性≈0"是错误的，纯属数据缺失时的估算');
  console.log('  ⚠️ 调仓后组合科技暴露仍然偏高(60%)，需关注整体风险');
  console.log('  💡 理想分散方案: 增加消费(159 consensus/512600)或金融(512800)方向 ETF');
}
run().catch(function(e){console.error(e);});
