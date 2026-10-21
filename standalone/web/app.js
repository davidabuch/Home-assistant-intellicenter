function featureIcon(key){const ns="http://www.w3.org/2000/svg";const svg=document.createElementNS(ns,"svg");svg.setAttribute("viewBox","0 0 64 64");svg.setAttribute("class","feature-svg");svg.setAttribute("aria-hidden","true");svg.setAttribute("fill","none");svg.setAttribute("stroke","currentColor");svg.setAttribute("stroke-width","4");svg.setAttribute("stroke-linecap","round");svg.setAttribute("stroke-linejoin","round");const paths={jets:[["circle",{cx:13,cy:13,r:4}],["circle",{cx:40,cy:9,r:6}],["circle",{cx:27,cy:27,r:4.5}],["circle",{cx:53,cy:31,r:4}],["circle",{cx:11,cy:44,r:6}],["circle",{cx:36,cy:51,r:5}],["circle",{cx:55,cy:55,r:3}]],spillway:[["path",{d:"M8 12h48v12H8z M13 24v25 M23 24v28 M33 24v28 M43 24v28 M53 24v25 M8 57q12-6 24 0t24 0"}]],slide:[["path",{d:"M10 8h22q8 0 8 8v6q0 7 7 11l7 4 M10 18h17q4 0 4 5v5q0 9 10 15l13 7 M7 53q8-5 16 0t16 0t16 0 M16 8v10"}]]};for(const [tag,attrs] of paths[key]||[]){const el=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,String(v));svg.append(el)}return svg}
const $=id=>document.getElementById(id);let state={},busy=false,lightEffectsOpen=false,permissions={pool_control:false,light_control:false};const names={pool:"Pool",spa:"Hot Tub",jets:"Jets",spillway:"Waterfall",slide:"Water Slide",light:"Pool Light",pool_sanitation:"Pool Sanitation",spa_sanitation:"Spa Sanitation"};function say(s){$("status").textContent=s}async function api(path,data){const response=await fetch("/api/"+path,{method:data?"POST":"GET",headers:{"Content-Type":"application/json"},credentials:"same-origin",cache:"no-store",body:data?JSON.stringify(data):undefined});const json=await response.json();if(!response.ok)throw Error(json.error||"Request failed");return json}function button(text,fn,active=false){const b=document.createElement("button");b.textContent=text;b.className=active?"active":"";b.disabled=busy;b.addEventListener("click",fn);return b}async function send(control,operation,value){if(busy)return;busy=true;say("Sending request…");render();try{await api("control",{control,operation,value});say("Request accepted — checking equipment…");await verify(control,operation,value)}catch(e){say(e.message)}finally{busy=false;render()}}async function verify(control,operation,value){const expected=operation==="on"?(control==="pool"||control==="spa"?"heat":"on"):operation==="off"?"off":null;for(let i=0;i<6;i++){await new Promise(resolve=>setTimeout(resolve,700));try{state=await api("state");render();const actual=state[control];const confirmed=operation==="effect"?actual?.state==="on"&&actual?.attributes?.effect===value:expected?actual?.state===expected:Number(actual?.attributes?.temperature)===Number(value);if(actual&&confirmed){say("Confirmed · "+names[control]+" updated");return}}catch(e){say("Checking equipment…")}}say("Request sent, but equipment state not yet confirmed. Check current status before retrying.")}/* The backyard photograph is permanently decorative and intentionally independent of HA state.
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
function render(){updateScene();for(const key of ["pool","spa"]){const root=$(key),entity=state[key]||{},on=entity.state==="heat",available=entity.state&&!["unavailable","unknown"].includes(entity.state),a=entity.attributes||{},current=a.current_temperature??"—",target=a.temperature??"—";root.replaceChildren();const solarActive=state["binary_sensor.solar_heating_active"]?.state==="on";const gasActive=state["binary_sensor.gas_heater_active"]?.state==="on";const heating=on&&(solarActive||gasActive);root.classList.toggle("is-on",on);root.classList.toggle("is-heating",heating);root.classList.toggle("is-off",!on);const top=document.createElement("div");top.className="top";const title=document.createElement("h2");title.textContent=names[key];const indicator=document.createElement("span");indicator.className="state-pill";indicator.textContent=available?(heating?"Heating":on?"On · Ready":"Off"):"Unavailable";top.append(title,indicator);const temp=document.createElement("div");temp.className="temp";temp.textContent=current+"°";const desc=document.createElement("p");desc.className="muted";desc.textContent="Water temperature";const actions=document.createElement("div");actions.className="actions";const power=button(on?"Turn off":"Turn on",()=>send(key,on?"off":"on"),on);power.classList.add("power-button");power.setAttribute("aria-label",(on?"Turn off ":"Turn on ")+names[key]);const powerSymbol=document.createElement("span");powerSymbol.className="power-symbol";powerSymbol.textContent="⏻";power.replaceChildren(powerSymbol);actions.append(power);const readout=document.createElement("div");readout.className="readout";const reading=document.createElement("div");reading.className="reading";reading.append(temp,desc);readout.append(reading,actions);const step=document.createElement("div");step.className="stepper";const targetLabel=document.createElement("span");targetLabel.className="target-label";targetLabel.textContent="Target  "+target+"°F";const minus=button("−",()=>send(key,"temperature",Number(target)-1));minus.setAttribute("aria-label","Lower "+names[key]+" target temperature");const plus=button("+",()=>send(key,"temperature",Number(target)+1));plus.setAttribute("aria-label","Raise "+names[key]+" target temperature");step.append(targetLabel,minus,plus);root.append(top,readout,step);attachHeatLongPress(root,key);root.querySelectorAll("button").forEach(b=>b.disabled=busy||!available||(key==="pool"&&!permissions.pool_control))}renderLight();const f=$("features");f.replaceChildren();for(const key of ["jets","spillway","slide"]){const e=state[key]||{},on=e.state==="on";const label=key==="jets"?"Jets":key==="spillway"?"Waterfall":"Water Slide";const toggle=button(label,()=>send(key,on?"off":"on"),on);toggle.classList.add("feature","feature-tile");toggle.dataset.key=key;toggle.insertBefore(featureIcon(key),toggle.firstChild);toggle.setAttribute("role","switch");toggle.setAttribute("aria-checked",String(on));toggle.setAttribute("aria-label",label+(on?", on":", off"));toggle.disabled=busy||!["on","off"].includes(e.state);f.append(toggle)}renderSanitation()}let poolDialog=null;
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
 const root=$("sanitation"),allowed=permissions.pool_control===true;root.hidden=!allowed;root.replaceChildren();if(!allowed)return;
 const pool=state.pool_sanitation?.state==="on",spa=state.spa_sanitation?.state==="on",active=pool||spa;
 const tile=document.createElement("div");tile.className="sanitation-combined"+(active?" active":"");tile.setAttribute("role","button");tile.setAttribute("tabindex","0");tile.setAttribute("aria-label",active?"Sanitation "+(spa?"Hot Tub":"Pool")+" running; hold for options":"Sanitation off; hold to choose Pool or Hot Tub");
 const icon=document.createElement("span");icon.className="sanitation-glyph";icon.textContent="✧";
 const details=document.createElement("div");details.className="sanitation-copy";const title=document.createElement("strong");title.textContent="Sanitation";const status=document.createElement("span");status.textContent=active?(spa?"Hot Tub running":"Pool running"):"Hold to choose Pool or Hot Tub";
 const remaining=document.createElement("small");remaining.className="sanitation-remaining";const seconds=sanitationRemaining();remaining.textContent=active?(seconds===null?"Timer unavailable":Math.floor(seconds/3600)+"h "+String(Math.floor(seconds%3600/60)).padStart(2,"0")+"m remaining"):"";
 details.append(title,status,remaining);tile.append(icon,details);
 const open=()=>openPoolDialog("Sanitation",active?[
 {label:"Stop "+(spa?"Hot Tub":"Pool")+" sanitation",action:()=>send(spa?"spa_sanitation":"pool_sanitation","off")},
 {label:"Cancel",action:()=>{}}
 ]:[
 {label:"Start Pool sanitation · 3 hours",disabled:busy||state.pool_sanitation?.state!=="off"||state.spa_sanitation?.state!=="off",action:()=>send("pool_sanitation","on")},
 {label:"Start Hot Tub sanitation · 3 hours",disabled:busy||state.pool_sanitation?.state!=="off"||state.spa_sanitation?.state!=="off",action:()=>send("spa_sanitation","on")}
 ]);
 attachHold(tile,open);tile.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();open()}});root.append(tile);
}
function renderLight(){
 const root=$("poolLight"),allowed=permissions.light_control===true;root.hidden=!allowed;if(!allowed){root.replaceChildren();return}
 const e=state.light||{},a=e.attributes||{},on=e.state==="on",available=["on","off"].includes(e.state);
 root.replaceChildren();root.classList.toggle("light-active",on);
 const details=document.createElement("div");details.className="compact-light-copy";const title=document.createElement("strong");title.textContent="Pool Light";const effect=document.createElement("span");effect.textContent=available?(a.effect||"No scene selected"):"Unavailable";details.append(title,effect);
 const power=button("",()=>send("light",on?"off":"on"),on);power.classList.add("power-button","compact-light-power");power.setAttribute("aria-label",on?"Turn pool light off":"Turn pool light on");const glyph=document.createElement("span");glyph.className="power-symbol";glyph.textContent="⏻";power.append(glyph);power.disabled=busy||!available;
 root.append(details,power);
 const show=()=>openPoolDialog("Pool Light Scene",(Array.isArray(a.effect_list)?a.effect_list:[]).map(name=>({label:name+(a.effect===name?" ✓":""),action:()=>send("light","effect",name)})));
 attachHold(root,show);
 details.addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();show()}});
 details.tabIndex=0;details.setAttribute("role","button");details.setAttribute("aria-label","Hold to choose pool light scene");
}

async function refresh(){try{state=await api("state");try{permissions=await api("permissions")}catch(e){permissions={pool_control:false,light_control:false}}$("controls").hidden=false;$("pinLogin").hidden=true;render();say("Live status · updated "+new Date().toLocaleTimeString())}catch(e){if(e.message==="Sign in required"){$("controls").hidden=true;$("pinLogin").hidden=false;state={};updateScene();say("Enter your device PIN to continue.")}else say(e.message)}}refresh();setInterval(()=>{if(!busy&&!document.hidden)refresh()},4000);document.addEventListener("visibilitychange",()=>{document.body.classList.toggle("scene-paused",document.hidden);if(!document.hidden)refresh()});
if("serviceWorker" in navigator && location.protocol==="https:"){navigator.serviceWorker.register("/sw.js").catch(()=>{});}
document.getElementById("pinForm").addEventListener("submit",async event=>{event.preventDefault();const field=document.getElementById("pinInput");try{await api("login",{pin:field.value});field.value="";await refresh()}catch(error){field.value="";say(error.message)}});
