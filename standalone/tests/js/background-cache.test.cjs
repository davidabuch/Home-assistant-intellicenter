const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const web=path.resolve(__dirname,'../../web');

test('new shell caches the complete photograph; API and command requests bypass cache',async()=>{
  const handlers={},deleted=[],responses=[],cached=[];
  let offline=false, skipped=false, claimed=false;
  const context={URL, self:{addEventListener:(name,fn)=>handlers[name]=fn,
    skipWaiting:async()=>{skipped=true},clients:{claim:async()=>{claimed=true}}},
    caches:{open:async name=>({addAll:async assets=>{
      for(const asset of assets){
        const url=new URL(asset,'https://pool.test');
        const file=url.pathname==='/'?'index.html':url.pathname.slice(1);
        if(file==='favicon.ico')assert.ok(fs.existsSync(path.join(web,'icons/approved-v2/favicon.ico')));
        else if(file.startsWith('apple-touch-icon'))assert.ok(fs.existsSync(path.join(web,'icons/approved-v2/icon-180.png')));
        else assert.ok(fs.existsSync(path.join(web,file)),asset+' must exist');
      }
      cached.push({name,assets});
    }}), keys:async()=>['pool-spa-family-approved-icons-v2-lawn-asset-12'],
    delete:async name=>deleted.push(name),match:async req=>({offline:req.url})},
    fetch:async req=>{if(offline)throw Error('offline');return {network:req.url}}};
  vm.runInNewContext(fs.readFileSync(path.join(web,'sw.js'),'utf8'),context);
  let pending;
  handlers.install({waitUntil:p=>pending=p});await pending;
  assert.ok(skipped);
  assert.ok(cached[0].assets.includes('/backyard-final.jpg'));
  assert.ok(!cached[0].assets.includes('/lawn-photo.svg'));
  handlers.activate({waitUntil:p=>pending=p});await pending;
  assert.ok(claimed);assert.equal(deleted.length,1);
  const request=(url,method='GET')=>handlers.fetch({request:{url,method},respondWith:p=>responses.push(p)});
  request('https://pool.test/api/state');request('https://pool.test/api/control','POST');
  assert.equal(responses.length,0,'API responses/commands must never enter shell cache');
  request('https://pool.test/backyard-final.jpg');
  assert.deepEqual(await responses.pop(),{network:'https://pool.test/backyard-final.jpg'});
  offline=true;request('https://pool.test/backyard-final.jpg');
  assert.deepEqual(await responses.pop(),{offline:'https://pool.test/backyard-final.jpg'});
});
