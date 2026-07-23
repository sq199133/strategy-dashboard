/**
 * bt_final.js - 最终修正版回测（所有bug已修复）
 * 修复：循环从i=26开始（而非i=1）、正确MACD金叉判断
 */
const fs = require('fs');
const INIT = 100000;
const DATA = 'D:/QClaw_Trading/data';

function calcMA(closes, p) {
  const r = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < p-1) { r.push(null); continue; }
    let s = 0; for (let j = 0; j < p; j++) s += closes[i-j];
    r.push(s/p);
  }
  return r;
}
function calcMACD(closes) {
  const ema = (d, p) => { const k=2/(p+1); const e=[d[0]]; for(let i=1;i<d.length;i++)e.push(d[i]*k+e[i-1]*(1-k)); return e; };
  const ef=ema(closes,12), es=ema(closes,26);
  const dif=ef.map((v,i)=>v-es[i]);
  const k=2/10, dea=new Array(dif.length).fill(null);
  let seed=0; for(let i=0;i<26;i++) seed+=dif[i]; seed/=26;
  dea[25]=seed;
  for(let i=26;i<dif.length;i++) dea[i]=dif[i]*k+dea[i-1]*(1-k);
  return {dif,dea};
}
function maDir(ma,idx,lb){
  if(idx<lb||ma[idx]===null)return'flat';
  const rec=ma.slice(Math.max(0,idx-lb+1),idx+1).filter(v=>v!==null);
  if(rec.length<2)return'flat';
  return rec[rec.length-1]>rec[0]?'up':'dn';
}

function bt(bars, cfg, label) {
  if(!bars||bars.length<60)return null;
  const cl=bars.map(r=>r.close);
  const maP={}; cfg.MAs.forEach(m=>{maP[m]=calcMA(cl,m);});
  const macd=calcMACD(cl);
  let cash=INIT,sh=0,state='out',entry=0;
  const eq=[],trades=[];
  for(let i=26;i<bars.length;i++){
    const px=cl[i];
    eq.push({nav:cash+sh*px,date:bars[i].date});
    if(state==='in'){
      const sl=cfg.sl&&(px/entry-1)<-cfg.sl;
      const macdDn=macd.dif[i]<macd.dea[i]&&macd.dif[i-1]>=macd.dea[i-1];
      if(px<maP[cfg.MAs[0]][i]||macdDn||sl){
        cash+=sh*px;
        const t={action:'SELL'+(sl?'(SL)':''),date:bars[i].date,ret:(px/entry-1)*100};
        trades.push(t); sh=0; state='out';
      }
    }else{
      const mu=macd.dif[i]>0&&macd.dif[i]>macd.dea[i]&&macd.dif[i-1]<=macd.dea[i-1];
      const mUp=maDir(maP[cfg.MAs[0]],i,cfg.lb)==='up';
      let allUp=true;
      for(let m=1;m<cfg.MAs.length;m++)if(maDir(maP[cfg.MAs[m]],i,cfg.lb)!=='up'){allUp=false;break;}
      if(px>maP[cfg.MAs[0]][i]&&mUp&&allUp&&mu){
        const s=Math.floor(cash/px/100)*100;
        if(s>0){cash-=s*px;entry=px;trades.push({action:'BUY',date:bars[i].date,price:px,macdOsc:(macd.dif[i]-macd.dea[i]).toFixed(2)});sh=s;state='in';}
      }
    }
  }
  if(state==='in'){cash+=sh*cl[cl.length-1];trades.push({action:'SELL*',date:bars[bars.length-1].date,ret:(cl[cl.length-1]/entry-1)*100});}
  return stats(trades,eq,bars,label,cfg);
}

function stats(trades,eq,bars,label,cfg){
  if(eq.length<20)return null;
  const rets=[];for(let i=1;i<eq.length;i++)rets.push((eq[i].nav-eq[i-1].nav)/eq[i-1].nav);
  const avgR=rets.reduce((a,b)=>a+b,0)/rets.length||0;
  const stdR=Math.sqrt(rets.reduce((a,b)=>a+(b-avgR)**2,0)/rets.length)||0;
  const yrs=(new Date(bars[bars.length-1].date)-new Date(bars[0].date))/86400000/365.25;
  const annR=(eq[eq.length-1].nav/INIT-1)/yrs*100;
  const shp=stdR>0?(avgR/stdR)*Math.sqrt(252):0;
  let peak=INIT,mxDD=0;
  for(const e of eq){if(e.nav>peak)peak=e.nav;const d=(peak-e.nav)/peak;if(d>mxDD)mxDD=d;}
  const cl=bars.map(r=>r.close);
  const bhA=(Math.pow(cl[cl.length-1]/cl[0],1/Math.max(yrs,.01))-1)*100;
  const sells=trades.filter(t=>t.action&&t.action.startsWith('SELL'));
  const wins=sells.filter(t=>t.ret>0);
  const winR=sells.length>0?wins.length/sells.length*100:0;
  return{
    l:label, s:cfg.n, annR:+annR.toFixed(1), shp:+shp.toFixed(2), dd:+(mxDD*100).toFixed(1),
    bhA:+bhA.toFixed(1), vsBH:+(annR-bhA).toFixed(1),
    winR:+winR.toFixed(0), trades:trades.length,
    wins:wins.length, yrs:+yrs.toFixed(2), start:bars[0].date, end:bars[bars.length-1].date,
    finalNav:eq[eq.length-1].nav.toFixed(0),
  };
}

function load(fp){try{const r=JSON.parse(fs.readFileSync(fp,'utf8'));return(r.records||r).filter(x=>x.close>0).sort((a,b)=>a.date.localeCompare(b.date));}catch(e){return null;}}

const CFGS=[
  {n:'MA20+MACD',    MAs:[20],   lb:5,  sl:null},
  {n:'MA10+MACD',    MAs:[10],   lb:3,  sl:null},
  {n:'MA10+20',      MAs:[10,20],lb:3,  sl:null},
  {n:'MA20+50',      MAs:[20,50],lb:5,  sl:null},
  {n:'MA20+MACD+SL5',MAs:[20],   lb:5,  sl:.05},
  {n:'MA10+MACD+SL5',MAs:[10],   lb:3,  sl:.05},
  {n:'MA20+MACD+SL3',MAs:[20],   lb:5,  sl:.03},
  {n:'MA10+20+SL5',  MAs:[10,20],lb:3,  sl:.05},
];

const DS=[
  {l:'沪深300指数[2005-]',fp:DATA+'/index_history/sh000300.json',   st:'2005-04-08'},
  {l:'50ETF[2018-]',       fp:DATA+'/history_long/sh510050.json',  st:'2018-05-30'},
  {l:'300ETF[2018-]',      fp:DATA+'/history_long/sh510300.json',  st:'2018-05-30'},
  {l:'500ETF[2018-]',      fp:DATA+'/history_long/sh510500.json',  st:'2018-05-30'},
  {l:'纳指ETF[2018-]',     fp:DATA+'/history_long/sh513100.json',  st:'2018-05-30'},
];

console.log('╔════════════════════════════════════════════════════════════════════════════════╗');
console.log('║        MA策略综合回测  v3（修正版）  '+(new Date().toLocaleString())+'          ║');
console.log('╚════════════════════════════════════════════════════════════════════════════════╝\n');

const all=[];
DS.forEach(d=>{
  const r=load(d.fp);
  if(!r){console.log('X '+d.l+' 加载失败');return;}
  const bars=r.filter(x=>x.date>=d.st);
  console.log('【'+d.l+'】'+bars.length+' bars, '+bars[0].date+'~'+bars[bars.length-1].date);
  CFGS.forEach(c=>{
    const res=bt(bars,c,d.l);
    if(res){all.push(res);const beat=res.vsBH>=0?'O':'X';const bar=res.annR>=0?'+':'-';console.log('  '+beat+' '+c.n.padEnd(16)+'年化:'+(bar+Math.abs(res.annR).toFixed(1))+'%  夏普:'+res.shp.toFixed(2)+'  DD:'+res.dd+'%  胜:'+res.winR+'%  交易:'+res.trades+'笔  超额:'+(res.vsBH>=0?'+':'')+res.vsBH+'%  BH:'+res.bhA+'%');}
  });
  console.log('');
});

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('综合排名（按夏普降序）');
console.log('数据集'.padEnd(18)+'策略'.padEnd(16)+'年化%'.padEnd(8)+'夏普'.padEnd(7)+'DD%'.padEnd(7)+'胜率'.padEnd(7)+'交易'.padEnd(6)+'超额%'.padEnd(8)+'BH年化%');
console.log('-'.repeat(90));
all.sort((a,b)=>b.shp-a.shp).forEach(r=>console.log(r.l.padEnd(18)+r.s.padEnd(16)+r.annR.toString().padEnd(8)+r.shp.toFixed(2).padEnd(7)+r.dd.toString().padEnd(7)+r.winR.toString().padEnd(7)+r.trades.toString().padEnd(6)+(r.vsBH>=0?'+':'')+r.vsBH+'%'.padEnd(8)+r.bhA+'%'));
console.log('');
fs.writeFileSync(DATA+'/bt_final_result.json',JSON.stringify(all,null,2));
console.log('完成');
