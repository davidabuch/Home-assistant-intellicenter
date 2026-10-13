const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../../web/admin-handoff.js'),'utf8');
const HOME='https://home-local.davidbuchmd.com';
function receiver({configured=true,accepted=true,openerPresent=true}={}){
 const calls=[],messages=[],navigation=[],listeners=new Map(),status={textContent:''};
 const opener={postMessage:(data,origin)=>messages.push({data,origin})};
 const window={opener:openerPresent?opener:null,location:{replace:target=>navigation.push(target)},
  addEventListener:(type,fn)=>listeners.set(type,fn),removeEventListener:type=>listeners.delete(type)};
 const fetch=async(url,options)=>{calls.push({url,options});return {ok:url.includes('config')?configured:accepted,json:async()=>({home_origin:HOME})}};
 vm.runInNewContext(source,{window,document:{getElementById:()=>status},fetch,setTimeout:()=>1,clearTimeout:()=>{}});
 return {window,opener,calls,messages,navigation,listeners,status};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
test('receiver validates both sender origin and opener, then exchanges JSON without navigation secrets',async()=>{
 const r=receiver();await settle();assert.deepEqual(r.messages.map(x=>x.data.type),['pool-admin-ready']);
 const receive=r.listeners.get('message');
 for(const event of [{origin:'https://evil.test',source:r.opener},{origin:HOME,source:{}}])await receive({...event,data:{type:'pool-admin-ticket',ticket:'mock-ticket'}});
 assert.equal(r.calls.length,1);
 await receive({origin:HOME,source:r.opener,data:{type:'pool-admin-ticket',ticket:'mock-ticket'}});
 assert.equal(r.calls[1].url,'/api/admin/handoff');assert.equal(r.calls[1].options.method,'POST');
 assert.equal(r.calls[1].options.body,JSON.stringify({ticket:'mock-ticket'}));
 assert.deepEqual(r.navigation,['/']);assert.equal(r.window.opener,null);
 assert.equal(r.messages[1].data.type,'pool-admin-complete');assert.equal(r.messages[1].origin,HOME);
 await receive({origin:HOME,source:r.opener,data:{type:'pool-admin-ticket',ticket:'mock-ticket'}});
 assert.equal(r.calls.length,2,'Duplicate messages cannot replay the exchange');
});
test('receiver fails closed on missing config, opener, or rejected ticket',async()=>{
 for(const options of [{configured:false},{openerPresent:false},{accepted:false}]){
  const r=receiver(options);await settle();
  if(options.accepted===false)await r.listeners.get('message')({origin:HOME,source:r.opener,data:{type:'pool-admin-ticket',ticket:'mock-ticket'}});
  assert.deepEqual(r.navigation,[]);assert.match(r.status.textContent,/Authorization failed/);
 }
});
const familySource=process.env.FAMILY_HOME_SOURCE;
test('both real browser scripts complete a POST-only handoff end to end',{skip:!familySource},async()=>{
 const familyScript=fs.readFileSync(path.join(familySource,'public/pool-handoff.js'),'utf8');
 const homeListeners=new Map(),poolListeners=new Map(),requests=[],nav=[],errors=[];
 const HOME='https://home-local.davidbuchmd.com',POOL='https://pool-local.davidbuchmd.com';
 const home={addEventListener:(t,f)=>homeListeners.set(t,f),removeEventListener:t=>homeListeners.delete(t)};
 const pool={addEventListener:(t,f)=>poolListeners.set(t,f),removeEventListener:t=>poolListeners.delete(t),
  location:{replace:url=>nav.push(url)}};
 // postMessage is delivered asynchronously, as in browsers, with real source objects.
 home.postMessage=(data,target)=>setImmediate(()=>{assert.equal(target,HOME);homeListeners.get('message')?.({data,origin:POOL,source:pool})});
 pool.postMessage=(data,target)=>setImmediate(()=>{assert.equal(target,POOL);poolListeners.get('message')?.({data,origin:HOME,source:home})});
 pool.opener=home;
 home.open=(url,target)=>{requests.push({navigation:url,target});assert.equal(url,POOL+'/admin-handoff.html');return pool};
 const timers={setTimeout:()=>1,clearTimeout:()=>{}};
 vm.runInNewContext(familyScript,{window:home,...timers});
 home.openPoolAdministrator(POOL,async(endpoint,options)=>{requests.push({endpoint,options});return {ticket:'mock-signed-ticket',pool_origin:POOL}},error=>errors.push(error));
 vm.runInNewContext(source,{window:pool,document:{getElementById:()=>({textContent:''})},...timers,
  fetch:async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>({home_origin:HOME})}}});
 for(let i=0;i<5;i++)await settle();
 assert.equal(errors.length,0);assert.deepEqual(nav,['/']);
 const issuance=requests.find(r=>r.endpoint);assert.equal(issuance.endpoint,'pool-admin-handoff');assert.equal(issuance.options.method,'POST');
 const exchange=requests.find(r=>r.url==='/api/admin/handoff');assert.equal(exchange.options.method,'POST');
 assert.equal(exchange.options.body,JSON.stringify({ticket:'mock-signed-ticket'}));
 assert.equal(requests.filter(r=>r.navigation||r.url).some(r=>(r.navigation||r.url).includes('ticket')),false);
 assert.equal(pool.opener,null);assert.equal(homeListeners.size,0);assert.equal(poolListeners.size,0);
});
