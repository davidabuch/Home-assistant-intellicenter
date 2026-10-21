// Isolated mock-only rendering: every request is intercepted; no equipment/network IO.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {chromium, webkit} = require('playwright');
const root = path.resolve(__dirname, '../..');
const baseline = 'c050dc874cb6df495b3d2a39ca6150a5994b8650'; // approved v0.1.30
const out = process.env.VISUAL_OUTPUT || path.join(root, 'standalone/visual-lawn');
fs.mkdirSync(out, {recursive:true});
const old = file => execFileSync('git', ['show', `${baseline}:standalone/web/${file}`], {cwd:root});
// The visual contract compares rendered UI and existing commands against the approved baseline.
// New admin-only interactions are covered by explicit tests rather than freezing app.js bytes.
const mime = {'.html':'text/html','.css':'text/css','.js':'application/javascript',
  '.jpg':'image/jpeg','.png':'image/png','.svg':'image/svg+xml','.webmanifest':'application/manifest+json'};
const props = ['display','position','zIndex','fontFamily','fontSize','fontWeight','lineHeight',
  'letterSpacing','color','background','border','borderRadius','boxShadow','textShadow',
  'backdropFilter','webkitBackdropFilter','padding','margin','gap','opacity',
  'touchAction','pointerEvents','minHeight','minWidth','gridTemplateColumns'];

async function render(browser, engine, version, viewport, mode) {
  const context = await browser.newContext({viewport, deviceScaleFactor:3,isMobile:true,hasTouch:true});
  const page = await context.newPage();
  const calls = [], errors = [];
  let signedIn=true, admin=true;
  let state={pool:{state:['off','spa-heating'].includes(mode)?'off':'heat',attributes:{current_temperature:76,temperature:90}},
    spa:{state:['idle','spa-heating'].includes(mode)?'heat':'off',attributes:{current_temperature:75,temperature:98}},
    ...Object.fromEntries(['jets','spillway','slide','light','pool_sanitation','spa_sanitation']
      .map(k=>[k,{state:'off',attributes:{effect:null,effect_list:['Light Show']}}])),
    'binary_sensor.solar_heating_active':{state:mode.endsWith('heating')?'on':'off'},
    'binary_sensor.gas_heater_active':{state:'off'}};
  page.on('pageerror', e=>errors.push(e.message));
  await page.route('**/*', async route=>{
    const req=route.request(), url=new URL(req.url());
    assert.equal(url.origin,'http://127.0.0.1:8765','External network is forbidden');
    let body, status=200, contentType;
    if(url.pathname.startsWith('/api/')) {
      contentType='application/json';
      if(url.pathname==='/api/login'){signedIn=true;body={ok:true};}
      else if(!signedIn){status=401;body={error:'Sign in required'};}
      else if(url.pathname==='/api/state') body=state;
      else if(url.pathname==='/api/permissions') body={pool_control:admin,light_control:admin};
      else if(url.pathname==='/api/heating-preference') {const c=req.postDataJSON();calls.push({heating_preference:c});state[c.body+'_heating_preference']={state:c.option};body={accepted:true};}
      else if(url.pathname==='/api/control'){
        const c=req.postDataJSON(); calls.push(c);
        const e=state[c.control];
        if(c.operation==='temperature')e.attributes.temperature=c.value;
        else if(c.operation==='effect'){if(version==='before')e.state='on';e.attributes.effect=c.value;e.selected_effect=c.value;}
        else e.state=c.operation==='on'&&['pool','spa'].includes(c.control)?'heat':c.operation;
        body={ok:true};
      } else throw Error('Unexpected API '+url.pathname);
      body=JSON.stringify(body);
    } else {
      let file=url.pathname==='/'?'index.html':url.pathname.slice(1);
      if(file==='favicon.ico')file='icons/approved-v2/favicon.ico';
      if(file.startsWith('apple-touch-icon'))file='icons/approved-v2/icon-180.png';
      body=version==='before'?old(file):fs.readFileSync(path.join(root,'standalone/web',file));
      contentType=mime[path.extname(file)]||'application/octet-stream';
    }
    await route.fulfill({status,contentType,body});
  });
  await page.goto('http://127.0.0.1:8765/');
  await page.waitForSelector('#controls:not([hidden])');
  await page.evaluate(()=>document.fonts.ready);
  const snapshot = await page.locator('main, #controls, #controls *').evaluateAll((nodes,props)=>nodes.map(n=>{
    const r=n.getBoundingClientRect(), s=getComputedStyle(n);
    return {tag:n.tagName,id:n.id,class:n.className?.baseVal??n.className,
      text:n.children.length?null:n.textContent,svg:n.tagName==='svg'?n.outerHTML:null,
      rect:[r.x,r.y,r.width,r.height],disabled:n.disabled,aria:n.getAttribute('aria-label'),
      styles:Object.fromEntries(props.map(p=>[p,s[p]]))};
  }),props);
  const power=await page.locator('#pool .power-button').evaluate(n=>({bg:getComputedStyle(n).backgroundColor,
    color:getComputedStyle(n).color,rect:n.getBoundingClientRect().toJSON()}));
  const expected=['off','spa-heating'].includes(mode)?['rgb(48, 70, 93)','rgba(255, 255, 255, 0.58)']:
    mode==='idle'?['rgb(255, 255, 255)','rgb(184, 189, 196)']:['rgb(242, 139, 27)','rgb(255, 255, 255)'];
  assert.deepEqual([power.bg,power.color],expected);
  assert.equal(await page.locator('#pool .temp').textContent(),'76°');
  assert.equal(await page.locator('#spa .temp').textContent(),'75°');
  assert.equal(await page.locator('#pool .state-pill').textContent(),mode==='heating'?'Heating':mode==='idle'?'On · Ready':'Off');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.screenshot({path:path.join(out,`${engine}-${viewport.width}-${viewport.height}-${mode}-${version}.png`)});
  if(viewport.width===393&&mode==='heating') {
    const wait=async()=>page.waitForFunction(()=>!document.querySelector('#pool button').disabled);
    for(const [selector,expectedCall] of [
      ['#pool .stepper button:last-child',{control:'pool',operation:'temperature',value:91}],
      ['#pool .power-button',{control:'pool',operation:'off'}],
      ['#spa .power-button',{control:'spa',operation:'on'}],
      ['[data-key="jets"]',{control:'jets',operation:'on'}],
      ['[data-key="spillway"]',{control:'spillway',operation:'on'}],
      ['[data-key="slide"]',{control:'slide',operation:'on'}],
      ...(version==='before'?[
      ['#sanitation button:first-child',{control:'pool_sanitation',operation:'on'}],
      ['#sanitation button:last-child',{control:'spa_sanitation',operation:'on'}],
      ['.light-icon',{control:'light',operation:'on'}]]:[])]) {
      await page.locator(selector).tap(); await wait();
      assert.deepEqual(calls.at(-1),expectedCall);
    }
    if(version==='after'){
      await page.locator('#sanitation .sanitation-combined').focus();
      await page.keyboard.press('Enter');
      await page.getByRole('button',{name:/Start Pool sanitation/}).tap();await wait();
      assert.deepEqual(calls.at(-1),{control:'pool_sanitation',operation:'on'});
      await page.locator('#poolLight .compact-light-power').tap();await wait();
      assert.deepEqual(calls.at(-1),{control:'light',operation:'on'});
      await page.locator('#poolLight .compact-light-copy').focus();await page.keyboard.press('Enter');
      assert.equal(await page.getByRole('dialog',{name:'Pool Light Scene'}).isVisible(),true);
      await page.getByRole('button',{name:/Light Show/}).tap();await wait();
      assert.deepEqual(calls.at(-1),{control:'light',operation:'effect',value:'Light Show'});
    }else{
    await page.getByRole('button',{name:'Choose pool light effect',exact:true}).tap();
    assert.equal(await page.locator('#lightEffects').isVisible(),true);
    await page.getByRole('button',{name:'Light Show',exact:true}).tap(); await wait();
    assert.deepEqual(calls.at(-1),{control:'light',operation:'effect',value:'Light Show'});
    }
    admin=false; await page.reload(); await page.waitForSelector('#controls:not([hidden])');
    assert.equal(await page.locator('#sanitation').isVisible(),version==='after');
    if(version==='after'){
      assert.equal(await page.locator('#poolLight').isVisible(),true);
      assert.equal(await page.locator('#poolLight .compact-light-power').count(),0);
      assert.equal(await page.locator('#sanitation .sanitation-combined').getAttribute('role'),null);
      assert.equal(await page.locator('#sanitation .sanitation-combined').textContent().then(t=>t.includes('Sanitation')),true);
    }
    assert.equal(await page.locator('#pool .power-button').isDisabled(),true);
    signedIn=false; await page.reload(); await page.waitForSelector('#pinLogin:not([hidden])');
    await page.locator('#pinInput').fill('0000'); await page.locator('#pinForm button').tap();
    await page.waitForSelector('#controls:not([hidden])');
    state.pool.attributes.current_temperature=77;
    await page.waitForFunction(()=>document.querySelector('#pool .temp').textContent==='77°');
  }
  assert.deepEqual(errors,[]);
  await context.close();
  return {snapshot,calls};
}
(async()=>{
  const results=[];
  for(const engine of (process.env.VISUAL_BROWSERS||'chromium').split(',')){
    const browser=await ({chromium,webkit}[engine]).launch({headless:true,
      ...(engine==='chromium'&&process.env.CHROMIUM_EXECUTABLE?{executablePath:process.env.CHROMIUM_EXECUTABLE}:{})});
    try {
      for(const viewport of [{width:393,height:852},{width:375,height:812},{width:430,height:932}])
        for(const mode of ['heating','idle','off','spa-heating']){
          const before=await render(browser,engine,'before',viewport,mode);
          const after=await render(browser,engine,'after',viewport,mode);
          const protectedNodes = snapshot => snapshot.snapshot.filter(n=>n.id==='pool'||n.id==='spa').map(n=>({id:n.id,width:n.rect[2],height:n.rect[3],styles:n.styles}));
          assert.deepEqual(protectedNodes(after),protectedNodes(before),`${engine} ${JSON.stringify(viewport)} ${mode}: protected pool/spa geometry regression`);
          results.push({engine,viewport,mode,protectedNodes:2,match:true});
        }
    } finally {await browser.close();}
  }
  fs.writeFileSync(path.join(out,'preservation-results.json'),JSON.stringify({baseline,results},null,2));
  console.log(`PASS: ${results.length} before/after layout/style/state cases; mock-only taps, permissions, PIN and polling preserved`);
})().catch(e=>{console.error(e);process.exitCode=1});
