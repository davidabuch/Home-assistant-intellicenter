/* Offline-only photographic water experiment. Never sends equipment commands.
   Uses the exact OFF photograph as its texture, not synthetic CSS rings. */
(()=>{"use strict";
const scene=document.getElementById("backyardScene");
const plane=scene?.querySelector(".scene-art");
if(!plane)return;
const canvas=document.createElement("canvas");
canvas.className="photo-motion";canvas.width=651;canvas.height=1199;
canvas.setAttribute("aria-hidden","true");plane.append(canvas);
const ctx=canvas.getContext("2d",{alpha:true});
const image=new Image();image.src="./backyard-off.jpg";
let ready=false;image.onload=()=>{ready=true};image.onerror=()=>{console.warn("Photo motion: missing backyard-off.jpg")};
const reduced=matchMedia("(prefers-reduced-motion: reduce)");
const shapes={
 pool:[[0,425],[88,394],[225,387],[332,410],[437,442],[520,466],[651,498],[651,1110],[110,1199],[0,950]],
 spa:[[487,470],[514,446],[566,434],[626,444],[651,460],[651,549],[602,555],[538,538],[490,508]]
};
function mask(poly){ctx.beginPath();ctx.moveTo(poly[0][0],poly[0][1]);for(let i=1;i<poly.length;i++)ctx.lineTo(poly[i][0],poly[i][1]);ctx.closePath();ctx.clip()}
function region(name,t){
 ctx.save();mask(shapes[name]);ctx.globalAlpha=name==="pool"?.48:.65;
 const y0=name==="pool"?385:430,y1=name==="pool"?1199:560;
 for(let y=y0;y<y1;y+=3){
   const dy=Math.min(3,y1-y);
   const shift=reduced.matches?0:(Math.sin(y*.052+t*.0011)*1.65+Math.sin(y*.023-t*.0008)*.85);
   ctx.drawImage(image,0,y,651,dy,shift,y,651,dy);
 }
 ctx.restore();
}
function frame(t){
 ctx.clearRect(0,0,651,1199);
 if(ready&&!document.hidden){
  if(scene.classList.contains("pool-running"))region("pool",t);
  if(scene.classList.contains("spa-running"))region("spa",t);
 }
 requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
})();
