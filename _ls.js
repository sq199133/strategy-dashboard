const fs=require('fs');
const path=require('path');
function ls(d,depth){
  if(!depth)depth=0;
  try{
    const r=fs.readdirSync(d);
    r.forEach(f=>{
      const fp=path.join(d,f);
      try{
        const s=fs.statSync(fp);
        if(s.isDirectory()){console.log('  '.repeat(depth)+'[DIR] '+f);ls(fp,depth+1);}
        else{console.log('  '.repeat(depth)+f+' ('+s.size+'b)');}
      }catch(e){}
    });
  }catch(e){}
}
console.log('=== D:/QClaw_Trading ===');
ls('D:/QClaw_Trading');