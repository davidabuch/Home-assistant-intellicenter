function featureIcon(key){const ns="http://www.w3.org/2000/svg";const svg=document.createElementNS(ns,"svg");svg.setAttribute("viewBox","0 0 64 64");svg.setAttribute("class","feature-svg");svg.setAttribute("aria-hidden","true");svg.setAttribute("fill","none");svg.setAttribute("stroke","currentColor");svg.setAttribute("stroke-width","4");svg.setAttribute("stroke-linecap","round");svg.setAttribute("stroke-linejoin","round");const paths={jets:[["circle",{cx:13,cy:13,r:4}],["circle",{cx:40,cy:9,r:6}],["circle",{cx:27,cy:27,r:4.5}],["circle",{cx:53,cy:31,r:4}],["circle",{cx:11,cy:44,r:6}],["circle",{cx:36,cy:51,r:5}],["circle",{cx:55,cy:55,r:3}]],spillway:[["path",{d:"M8 12h48v12H8z M13 24v25 M23 24v28 M33 24v28 M43 24v28 M53 24v25 M8 57q12-6 24 0t24 0"}]],slide:[["path",{d:"M10 8h22q8 0 8 8v6q0 7 7 11l7 4 M10 18h17q4 0 4 5v5q0 9 10 15l13 7 M7 53q8-5 16 0t16 0t16 0 M16 8v10"}]]};for(const [tag,attrs] of paths[key]||[]){const el=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,String(v));svg.append(el)}return svg}
const $=id=>document.getElementById(id);let state={},busy=false,lightEffectsOpen=false,permissions={pool_control:false,light_control:false};const names={pool:"Pool",spa:"Hot Tub",jets:"Jets",spillway:"Waterfall",slide:"Water Slide",light:"Pool Light",pool_sanitation:"Pool Sanitation",spa_sanitation:"Spa Sanitation"};function say(s){$("status").textContent=s}async function api(path,data){const response=await fetch("/api/"+path,{method:data?"POST":"GET",headers:{"Content-Type":"application/json"},credentials:"same-origin",cache:"no-store",body:data?JSON.stringify(data):undefined});const json=await response.json();if(!response.ok)throw Error(json.error||"Request failed");return json}function button(text,fn,active=false){const b=document.createElement("button");b.textContent=text;b.className=active?"active":"";b.disabled=busy;b.addEventListener("click",fn);return b}async function send(control,operation,value){if(busy)return;busy=true;say("Sending request…");render();try{await api("control",{control,operation,value});say("Request accepted — checking equipment…");await verify(control,operation,value)}catch(e){say(e.message)}finally{busy=false;render()}}async function verify(control,operation,value){const expected=operation==="on"?(control==="pool"||control==="spa"?"heat":"on"):operation==="off"?"off":null;for(let i=0;i<6;i++){await new Promise(resolve=>setTimeout(resolve,700));try{state=await api("state");render();const actual=state[control];const confirmed=operation==="effect"?(actual?.selected_effect===value&&(actual?.state==="off"||actual?.attributes?.effect===value)):expected?actual?.state===expected:Number(actual?.attributes?.temperature)===Number(value);if(actual&&confirmed){say("Confirmed · "+names[control]+" updated");return}}catch(e){say("Checking equipment…")}}say("Request sent, but equipment state not yet confirmed. Check current status before retrying.")}/* The backyard photograph is permanently decorative and intentionally independent of HA state.
   Actual equipment buttons and readouts continue to use confirmed HA state. */
function updateScene(){}
let heatDialog=null;
function closeHeatDialog(){if(heatDialog){heatDialog.remove();heatDialog=null}}
function showHeatDialog(key){
 if(!permissions.pool_control||busy)return;
 closeHeatDialog();
 const overlay=document.createElement("div");overlay.className="heat-overlay";
 const panel=document.createElement("div");panel.className="heat-dialog";panel.setAttribute("role","dialog");panel.setAttribute("aria-modal","true");panel.setAttribute("aria-label",names[key]+" heat source");
 const heading=document.createElement("h2");heading.textContent=names[key]+" — Heat Source";
 const hint=document.createElement("p");hint.textContent="Heating preference only — circulation is unchanged.";
 panel.append(heading,hint);
 const selected=state[key+"_heating_preference"]?.state;
 for(const option of ["Solar","Gas","Eco Heat","Off"]){
  const item=document.createElement("button");item.type="button";item.className="heat-option";item.textContent=option+(selected===option?" ✓":"");
  item.setAttribute("aria-pressed",String(selected===option));
  item.addEventListener("click",async()=>{if(busy)return;closeHeatDialog();busy=true;say("Setting "+names[key]+" heating preference…");try{
   await api("heating-preference",{body:key,option});say("Preference requested — verifying…");
   for(let i=0;i<6;i++){await new Promise(resolve=>setTimeout(resolve,700));state=await api("state");if(state[key+"_heating_preference"]?.state===option){say(names[key]+" heat preference confirmed: "+option);break}if(i===5)say("Preference sent; confirmation pending. Check current status.")}
  }catch(e){say(e.message)}finally{busy=false;render()}});
  panel.append(item);
 }
 overlay.addEventListener("click",e=>{if(e.target===overlay)closeHeatDialog()});
 panel.addEventListener("keydown",e=>{if(e.key==="Escape")closeHeatDialog()});
 overlay.append(panel);document.body.append(overlay);heatDialog=overlay;panel.tabIndex=-1;panel.focus();
}
function attachHeatLongPress(root,key){
 if(!permissions.pool_control||root.dataset.heatLongPressBound)return;
 root.dataset.heatLongPressBound="true";
 let startX=0,startY=0,timer=null;
 const cancel=()=>{clearTimeout(timer);timer=null};
 root.addEventListener("pointerdown",e=>{if(e.target.closest("button")||e.button!==0||!e.isPrimary)return;startX=e.clientX;startY=e.clientY;cancel();timer=setTimeout(()=>{timer=null;showHeatDialog(key)},800)});
 root.addEventListener("pointermove",e=>{if(Math.hypot(e.clientX-startX,e.clientY-startY)>12)cancel()});
 for(const event of ["pointerup","pointercancel","pointerleave"])root.addEventListener(event,cancel);
 root.addEventListener("contextmenu",e=>{if(!e.target.closest("button"))e.preventDefault()});
}
function render(){updateScene();renderFiltrationProgress();for(const [id,key] of [["airTemp","sensor.air_temperature"],["roofTemp","sensor.solar_temperature"]]){const value=Number(state[key]?.state);$(id).textContent=Number.isFinite(value)&&state[key]?.state!==""?Math.round(value)+"°F":"—";}$("settingsNav").hidden=!permissions.pool_control||settingsOpen;for(const key of ["pool","spa"]){const root=$(key),entity=state[key]||{},on=entity.state==="heat",available=entity.state&&!["unavailable","unknown"].includes(entity.state),a=entity.attributes||{},current=a.current_temperature??"—",target=a.temperature??"—";root.replaceChildren();const solarActive=state["binary_sensor.solar_heating_active"]?.state==="on";const gasActive=state["binary_sensor.gas_heater_active"]?.state==="on";const heating=on&&(solarActive||gasActive);root.classList.toggle("is-on",on);root.classList.toggle("is-heating",heating);root.classList.toggle("is-off",!on);const top=document.createElement("div");top.className="top";const title=document.createElement("h2");title.textContent=names[key];const indicator=document.createElement("span");indicator.className="state-pill";indicator.textContent=available?(heating?"Heating":on?"On · Ready":"Off"):"Unavailable";top.append(title,indicator);const temp=document.createElement("div");temp.className="temp";temp.textContent=current+"°";const desc=document.createElement("p");desc.className="muted";desc.textContent="Water temperature";const actions=document.createElement("div");actions.className="actions";const power=button(on?"Turn off":"Turn on",()=>send(key,on?"off":"on"),on);power.classList.add("power-button");power.setAttribute("aria-label",(on?"Turn off ":"Turn on ")+names[key]);const powerSymbol=document.createElement("span");powerSymbol.className="power-symbol";powerSymbol.textContent="⏻";power.replaceChildren(powerSymbol);actions.append(power);const readout=document.createElement("div");readout.className="readout";const reading=document.createElement("div");reading.className="reading";reading.append(temp,desc);readout.append(reading,actions);const step=document.createElement("div");step.className="stepper";const targetLabel=document.createElement("span");targetLabel.className="target-label";targetLabel.textContent="Target  "+target+"°F";const minus=button("−",()=>send(key,"temperature",Number(target)-1));minus.setAttribute("aria-label","Lower "+names[key]+" target temperature");const plus=button("+",()=>send(key,"temperature",Number(target)+1));plus.setAttribute("aria-label","Raise "+names[key]+" target temperature");step.append(targetLabel,minus,plus);root.append(top,readout,step);attachHeatLongPress(root,key);root.querySelectorAll("button").forEach(b=>b.disabled=busy||!available||(key==="pool"&&!permissions.pool_control))}renderLight();const f=$("features");f.replaceChildren();for(const key of ["jets","spillway","slide"]){const e=state[key]||{},on=e.state==="on";const label=key==="jets"?"Jets":key==="spillway"?"Waterfall":"Water Slide";const toggle=button(label,()=>send(key,on?"off":"on"),on);toggle.classList.add("feature","feature-tile");toggle.dataset.key=key;toggle.insertBefore(featureIcon(key),toggle.firstChild);toggle.setAttribute("role","switch");toggle.setAttribute("aria-checked",String(on));toggle.setAttribute("aria-label",label+(on?", on":", off"));toggle.disabled=busy||!["on","off"].includes(e.state);f.append(toggle)}renderSanitation()}let poolDialog=null;
function closePoolDialog(){if(poolDialog){poolDialog.remove();poolDialog=null}}
function openPoolDialog(title,options){
 closePoolDialog();
 const overlay=document.createElement("div");overlay.className="heat-overlay pool-choice-overlay";
 const panel=document.createElement("div");panel.className="heat-dialog";panel.setAttribute("role","dialog");panel.setAttribute("aria-modal","true");panel.setAttribute("aria-label",title);
 const heading=document.createElement("h2");heading.textContent=title;panel.append(heading);
 for(const option of options){const b=document.createElement("button");b.type="button";b.className="heat-option";b.textContent=option.label;b.disabled=option.disabled===true;b.addEventListener("click",()=>{closePoolDialog();option.action()});panel.append(b)}
 overlay.addEventListener("click",e=>{if(e.target===overlay)closePoolDialog()});
 panel.addEventListener("keydown",e=>{if(e.key==="Escape")closePoolDialog()});
 overlay.append(panel);document.body.append(overlay);poolDialog=overlay;panel.tabIndex=-1;panel.focus();
}
function attachHold(root,fn){
 let timer=null,x=0,y=0,handled=false;
 const cancel=()=>{clearTimeout(timer);timer=null};
 root.addEventListener("pointerdown",e=>{if(e.button!==0||!e.isPrimary||e.target.closest("button"))return;handled=false;x=e.clientX;y=e.clientY;cancel();timer=setTimeout(()=>{handled=true;timer=null;fn()},650)});
 root.addEventListener("pointermove",e=>{if(Math.hypot(e.clientX-x,e.clientY-y)>12)cancel()});
 for(const type of ["pointerup","pointercancel","pointerleave"])root.addEventListener(type,cancel);
 root.addEventListener("contextmenu",e=>{if(!e.target.closest("button"))e.preventDefault()});
 root.addEventListener("click",e=>{if(handled){e.preventDefault();e.stopPropagation();handled=false}},true);
}
function sanitationRemaining(){
 const timer=state.sanitation_timer||{},a=timer.attributes||{};
 if(timer.state==="active"&&a.finishes_at){const ms=Date.parse(a.finishes_at)-Date.now();if(Number.isFinite(ms))return Math.max(0,Math.ceil(ms/1000))}
 const raw=a.remaining||a.duration||"03:00:00",parts=String(raw).split(":").map(Number);
 if(parts.length===3&&parts.every(Number.isFinite))return parts[0]*3600+parts[1]*60+parts[2];
 return null;
}
function renderSanitation(){
 const root=$("sanitation"),allowed=permissions.pool_control===true;root.hidden=false;root.replaceChildren();
 const pool=state.pool_sanitation?.state==="on",spa=state.spa_sanitation?.state==="on",active=pool||spa;
 const tile=document.createElement("div");tile.className="sanitation-combined"+(active?" active":"");tile.setAttribute("role","button");tile.setAttribute("tabindex","0");tile.setAttribute("aria-label",active?"Sanitation "+(spa?"Hot Tub":"Pool")+" running"+(allowed?"; hold for options":""):allowed?"Sanitation off; hold to choose Pool or Hot Tub":"Sanitation off");
 const icon=document.createElement("span");icon.className="sanitation-glyph";icon.textContent="✧";
 const details=document.createElement("div");details.className="sanitation-copy";const title=document.createElement("strong");title.textContent="Sanitation";const status=document.createElement("span");status.textContent=active?(spa?"Hot Tub running":"Pool running"):allowed?"Hold to choose Pool or Hot Tub":"Off";
 const remaining=document.createElement("small");remaining.className="sanitation-remaining";const seconds=sanitationRemaining();remaining.textContent=active?(seconds===null?"Timer unavailable":Math.floor(seconds/3600)+"h "+String(Math.floor(seconds%3600/60)).padStart(2,"0")+"m remaining"):"";
 details.append(title,status,remaining);tile.append(icon,details);
 const open=()=>openPoolDialog("Sanitation",active?[
 {label:"Stop "+(spa?"Hot Tub":"Pool")+" sanitation",action:()=>send(spa?"spa_sanitation":"pool_sanitation","off")},
 {label:"Cancel",action:()=>{}}
 ]:[
 {label:"Start Pool sanitation · 3 hours",disabled:busy||state.pool_sanitation?.state!=="off"||state.spa_sanitation?.state!=="off",action:()=>send("pool_sanitation","on")},
 {label:"Start Hot Tub sanitation · 3 hours",disabled:busy||state.pool_sanitation?.state!=="off"||state.spa_sanitation?.state!=="off",action:()=>send("spa_sanitation","on")}
 ]);
 if(allowed){attachHold(tile,open);tile.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();open()}})}else{tile.removeAttribute("role");tile.removeAttribute("tabindex");tile.setAttribute("aria-label","Sanitation "+(active?(spa?"Hot Tub":"Pool")+" running":"off"))}root.append(tile);
}
function renderLight(){
 const root=$("poolLight"),allowed=permissions.light_control===true;root.hidden=false;
 const e=state.light||{},a=e.attributes||{},on=e.state==="on",available=["on","off"].includes(e.state);
 root.replaceChildren();root.classList.toggle("light-active",on);
 const details=document.createElement("div");details.className="compact-light-copy";const title=document.createElement("strong");title.textContent="Pool Light";const effect=document.createElement("span");effect.textContent=available?(e.selected_effect||a.effect||"No scene selected"):"Unavailable";details.append(title,effect);
 const power=button("",()=>send("light",on?"off":"on"),on);power.classList.add("power-button","compact-light-power");power.setAttribute("aria-label",on?"Turn pool light off":"Turn pool light on");const glyph=document.createElement("span");glyph.className="power-symbol";glyph.textContent="⏻";power.append(glyph);power.disabled=busy||!available;
 root.append(details);if(allowed)root.append(power);
 const show=()=>openPoolDialog("Pool Light Scene",(Array.isArray(a.effect_list)?a.effect_list:[]).map(name=>({label:name+((e.selected_effect||a.effect)===name?" ✓":""),action:()=>send("light","effect",name)})));
 if(allowed){attachHold(root,show);
 details.addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();show()}});
 details.tabIndex=0;details.setAttribute("role","button");details.setAttribute("aria-label","Hold to choose pool light scene")}
}

async function refresh(){try{state=await api("state");try{permissions=await api("permissions")}catch(e){permissions={pool_control:false,light_control:false}}$("controls").hidden=settingsOpen;$("pinLogin").hidden=true;render();say("Live status · updated "+new Date().toLocaleTimeString())}catch(e){if(e.message==="Sign in required"){$("controls").hidden=true;$("settingsScreen").hidden=true;$("settingsNav").hidden=true;settingsOpen=false;$("pinLogin").hidden=false;state={};updateScene();say("Enter your device PIN to continue.")}else say(e.message)}}refresh();setInterval(()=>{if(!busy&&!document.hidden)refresh()},4000);document.addEventListener("visibilitychange",()=>{document.body.classList.toggle("scene-paused",document.hidden);if(!document.hidden)refresh()});
if("serviceWorker" in navigator && location.protocol==="https:"){navigator.serviceWorker.register("/sw.js").catch(()=>{});}
document.getElementById("pinForm").addEventListener("submit",async event=>{event.preventDefault();const field=document.getElementById("pinInput");try{await api("login",{pin:field.value});field.value="";await refresh()}catch(error){field.value="";say(error.message)}});


/* Admin settings are a separate view; all writes remain server-authorized. */
const settingNames={pool_chlorine:"Pool Chlorine",spa_chlorine:"Spa Chlorine",pool_rpm:"Pool Circulation",spa_rpm:"Spa",sanitation_rpm:"Sanitation",heater_rpm:"Gas Heater",solar_rpm:"Solar Heating",cleaning_rpm:"Pool Cleaning",outage_rpm:"Grid Outage"};
const speedKeys=["pool_rpm","spa_rpm","sanitation_rpm","heater_rpm","solar_rpm","cleaning_rpm","outage_rpm"];
let settingsData={},settingsBusy=false,settingsOpen=false,settingsDirty=false;
const settingQueues=new Map(),settingDrafts=new Map();
let settingsModalOpen=false;
function settingsMessage(message){$("settingsFeedback").textContent=message}
function settingValue(key){const n=Number(settingsData[key]?.state);return Number.isFinite(n)&&settingsData[key]?.state!=="unavailable"&&settingsData[key]?.state!=="unknown"?n:null}
function renderSettingGroup(target,keys){
 const root=$(target);root.replaceChildren();
 for(const key of keys){
  const entity=settingsData[key]||{},attrs=entity.attributes||{},value=settingDrafts.has(key)?settingDrafts.get(key):settingValue(key),rpm=key.endsWith("_rpm"),step=Number(attrs.step)||1;
  const tile=document.createElement("div");tile.className="settings-tile";
  const name=document.createElement("strong");name.textContent=settingNames[key];
  const controls=document.createElement("div");controls.className="settings-stepper";
  const minus=document.createElement("button");minus.textContent="−";minus.setAttribute("aria-label","Decrease "+settingNames[key]);
  const number=document.createElement("button");number.className="settings-value";number.textContent=value===null?"Unavailable":value.toLocaleString()+ (rpm?" rpm":"%");
  number.setAttribute("aria-label","Enter "+settingNames[key]+" using keypad");
  const plus=document.createElement("button");plus.textContent="+";plus.setAttribute("aria-label","Increase "+settingNames[key]);
  const save=(next)=>{
   if(value===null||!Number.isFinite(next))return;
   const min=Math.max(Number(attrs.min),rpm?Number(attrs.approved_minimum_rpm??attrs.min):Number(attrs.min));
   const max=Number(attrs.max);
   if(next<min||next>max){settingsMessage("Allowed range: "+min+" to "+max);return}
   // Keep the intended value visible while Home Assistant reports the previous state.
   settingDrafts.set(key,next);
   renderSettingGroup(rpm?"pumpSettings":"chlorineSettings",rpm?speedKeys:["pool_chlorine","spa_chlorine"]);
   settingsMessage("Saving "+settingNames[key]+"…");
   const previous=settingQueues.get(key)||Promise.resolve();
   const current=previous.catch(()=>{}).then(async()=>{
    await api("settings",{operation:"set",key,value:next});
    if(rpm)settingsDirty=true;
   });
   settingQueues.set(key,current);
   current.then(async()=>{
    if(settingQueues.get(key)!==current)return;
    // Allow the controller's asynchronous state observation to settle.
    await new Promise(resolve=>setTimeout(resolve,850));
    if(settingQueues.get(key)!==current)return;
    const fresh=await api("settings");
    if(settingQueues.get(key)!==current)return;
    settingsData=fresh;
    const observed=settingValue(key);
    settingDrafts.delete(key);
    if(settingsOpen)renderSettingGroup(rpm?"pumpSettings":"chlorineSettings",rpm?speedKeys:["pool_chlorine","spa_chlorine"]);
    settingsMessage(observed===next?(rpm?"Desired speed staged; Apply Changes when ready.":"Chlorine output verified."):"Command accepted; controller still reports "+(observed===null?"unavailable":observed)+". Please verify.");
   }).catch(e=>{
    if(settingQueues.get(key)!==current)return;
    settingDrafts.delete(key);
    if(settingsOpen)loadSettings().catch(()=>{});
    settingsMessage("Unable to save "+settingNames[key]+": "+e.message);
   });
  };
  minus.addEventListener("click",()=>save((settingDrafts.get(key)??value)-step));
  plus.addEventListener("click",()=>save((settingDrafts.get(key)??value)+step));
  number.addEventListener("click",()=>{
   if(value===null)return;
   const dialog=document.createElement("div");dialog.className="settings-modal";
   const form=document.createElement("form");form.className="settings-modal-card";
   const label=document.createElement("label");label.textContent="Enter "+settingNames[key]+(rpm?" (rpm)":" (%)");
   const input=document.createElement("input");input.type="number";input.inputMode="numeric";input.min=String(attrs.min);input.max=String(attrs.max);input.step=String(step);input.value=String(value);input.required=true;
   const actions=document.createElement("div");actions.className="settings-modal-actions";
   const cancel=document.createElement("button");cancel.type="button";cancel.textContent="Cancel";cancel.addEventListener("click",()=>{dialog.remove();settingsModalOpen=false;document.body.classList.remove("settings-dialog-open")});
   const confirm=document.createElement("button");confirm.type="submit";confirm.textContent="Set Value";
   actions.append(cancel,confirm);form.append(label,input,actions);dialog.append(form);document.body.append(dialog);settingsModalOpen=true;document.body.classList.add("settings-dialog-open");input.focus();input.select();
   form.addEventListener("submit",e=>{e.preventDefault();if(!input.reportValidity())return;const next=Number(input.value);dialog.remove();settingsModalOpen=false;document.body.classList.remove("settings-dialog-open");save(next)});
  });
  for(const b of [minus,number,plus])b.disabled=value===null;
  controls.append(minus,number,plus);tile.append(name,controls);root.append(tile);
 }
}
async function loadSettings(){
 if(!settingsOpen||!permissions.pool_control)return;
 const fresh=await api("settings");if(!settingsOpen)return;settingsData=fresh;renderSettingGroup("chlorineSettings",["pool_chlorine","spa_chlorine"]);renderSettingGroup("pumpSettings",speedKeys);
 renderSuperchlorinate();
}
function settingsNavigate(open){
 if(open&&!permissions.pool_control)return;
 settingsOpen=open;
 $("settingsScreen").hidden=!open;$("controls").hidden=open;$("settingsNav").hidden=open||!permissions.pool_control;
 if(open){loadSettings().catch(e=>settingsMessage(e.message))}
}
$("settingsNav").addEventListener("click",()=>settingsNavigate(true));
$("settingsBack").addEventListener("click",()=>settingsNavigate(false));
for(const [id,operation] of [["applyPump","apply"],["reconcilePump","reconcile"]]){
 $(id).addEventListener("click",async()=>{
  if(settingsBusy)return;
  if(!confirm(operation==="apply"?"Apply staged pump speeds through Guardian safety checks?":"Reconcile the last applied pump speed configuration?"))return;
  settingsBusy=true;settingsMessage(operation==="apply"?"Requesting Guardian apply…":"Requesting Guardian reconciliation…");
  try{await api("settings",{operation});if(operation==="apply")settingsDirty=false;settingsMessage("Request accepted. Guardian will apply and verify only when safe. Check Home Assistant for final result.");await loadSettings()}
  catch(e){settingsMessage(e.message)}finally{settingsBusy=false}
 });
}

function renderFiltrationProgress(){const el=$("filtrationProgress");if(!el)return;const completed=Number(state["counter.pool_simple_filtration_minutes"]?.state),target=Number(state["sensor.pool_daily_filtration_target"]?.state);if(!Number.isFinite(completed)||!Number.isFinite(target)||target<=0||!state["counter.pool_simple_filtration_minutes"]||!state["sensor.pool_daily_filtration_target"]){el.textContent="Filtration · Unavailable";return;}const remaining=Math.max(0,Math.ceil(target-completed));const hours=Math.floor(remaining/60),minutes=remaining%60;el.textContent=remaining===0?"Filtration · Daily target complete":`Filtration · ${hours?hours+"h ":""}${minutes}m remaining · ${Math.round(completed)}/${Math.round(target)} min credited`;}
function renderSuperchlorinate(){
 const tile=$("superchlorinate"),native=settingsData.superchlorinate||{},state=native.state;
 tile.replaceChildren();tile.classList.toggle("settings-disabled",state!=="on"&&state!=="off");
 const title=document.createElement("strong");title.textContent="Superchlorinate";
 const details=document.createElement("span");details.className="superchlorinate-status";details.textContent=state==="on"?"● Active · Native duration not reported":state==="off"?"Off":"Unavailable";
 const toggle=document.createElement("button");toggle.type="button";toggle.textContent=state==="on"?"Stop Superchlorination":"Start Superchlorination";
 toggle.disabled=!["on","off"].includes(state)||settingsBusy;
 toggle.addEventListener("click",async()=>{
  const enabled=state==="off";
  if(!confirm(enabled?"Start native IntelliChlor Superchlorination? Pentair will manage the cycle.":"Stop native IntelliChlor Superchlorination?"))return;
  settingsBusy=true;toggle.disabled=true;settingsMessage(enabled?"Sending native start request…":"Sending native stop request…");
  try{
   await api("settings",{operation:"superchlorinate",enabled});
   settingsMessage("Command accepted; checking actual IntelliChlor state…");
   await new Promise(resolve=>setTimeout(resolve,1200));
   await loadSettings();
   const observed=settingsData.superchlorinate?.state;
   settingsMessage(observed===(enabled?"on":"off")?"Native Superchlorinate state verified.":"Command sent, but native state not yet verified. Check Pentair.");
  }catch(e){settingsMessage(e.message)}finally{settingsBusy=false;renderSuperchlorinate()}
 });
 tile.append(title,details,toggle);
}
