let data=[],selected=new Set(),picks={},page=1,job=null,timer=null;const $=x=>document.getElementById(x);const esc=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
async function validate(){let c=$("cookie").value.trim();if(!c)return alert("Enter the cookie.");$("conn").textContent="Validating…";let r=await fetch("/api/validate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({cookie:c})}),j=await r.json();if(!r.ok){$("conn").textContent="Not connected";return alert(j.error)}$("cookie").value="";$("conn").textContent=`Connected • ${j.count} purchases • loading files…`;r=await fetch("/api/load",{method:"POST"});j=await r.json();data=j.orders||[];$("conn").textContent=`Connected • ${data.length} loaded`;$("lib").classList.remove("hide");$("dl").classList.remove("hide");render();if(j.errors?.length)alert(`${j.errors.length} purchase detail request(s) failed; other purchases loaded.`)}
function filt(){let q=$("search").value.toLowerCase();return data.filter(o=>!q||o.title.toLowerCase().includes(q)||o.category.toLowerCase().includes(q))}function vis(){let a=filt(),n=+$("size").value;return a.slice((page-1)*n,page*n)}
function render(){let a=filt(),n=+$("size").value,m=Math.max(1,Math.ceil(a.length/n));page=Math.min(page,m);$("stats").textContent=`${data.length} purchases • ${a.length} shown • ${selected.size} selected`;$("pages").textContent=`Page ${page} of ${m}`;$("orders").innerHTML=vis().map(o=>`<div class="order"><div class="head"><input type="checkbox" ${selected.has(o.gamekey)?"checked":""} onchange="tog('${o.gamekey}',this.checked)"><div class="grow"><b>${esc(o.title)}</b><div class="sub">${esc(o.created||"")} • ${o.file_count} files</div></div><span class="badge">${esc(o.category)}</span><button onclick="expand('${o.gamekey}')">Files</button></div><div id="x-${o.gamekey}" class="details hide">${products(o)}</div></div>`).join("")}
function products(o){return Object.entries(o.products).map(([p,fs])=>`<div><b>${esc(p)}</b>${fs.map(f=>`<label class="file"><input type="checkbox" ${(picks[o.gamekey]===undefined||picks[o.gamekey].has(f.id))?"checked":""} data-k="${o.gamekey}" data-f="${f.id}" onchange="ftog(this)"> ${esc(f.platform)} • ${esc(f.format)} • ${esc(f.filename)} ${f.human_size?"("+esc(f.human_size)+")":""}</label>`).join("")}</div>`).join("")||"<small>No downloadable files returned.</small>"}
function expand(k){$("x-"+k).classList.toggle("hide")}function tog(k,v){v?selected.add(k):selected.delete(k);render()}function allPage(v){vis().forEach(o=>v?selected.add(o.gamekey):selected.delete(o.gamekey));render()}function allMatch(v){filt().forEach(o=>v?selected.add(o.gamekey):selected.delete(o.gamekey));render()}
function ftog(e){let k=e.dataset.k,f=e.dataset.f;if(!picks[k])picks[k]=new Set(Object.values(data.find(o=>o.gamekey===k).products).flat().map(x=>x.id));e.checked?picks[k].add(f):picks[k].delete(f)}
function prev(){if(page>1){page--;render()}}function next(){if(page<Math.ceil(filt().length/+$("size").value)){page++;render()}}
async function start(){if(!selected.size)return alert("Select at least one purchase.");let fids={};for(let k of selected)if(picks[k])fids[k]=[...picks[k]];let r=await fetch("/api/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({keys:[...selected],file_ids:fids,destination:$("dest").value})}),j=await r.json();if(!r.ok)return alert(j.error);job=j.job_id;$("prog").classList.remove("hide");poll();timer=setInterval(poll,800)}
async function poll(){if(!job)return;let j=await(await fetch("/api/job/"+job)).json(),p=j.total?Math.round(j.done/j.total*100):0;$("bar").style.width=p+"%";$("pct").textContent=p+"%";$("counts").textContent=`${j.done} of ${j.total} • ${j.downloaded} downloaded • ${j.skipped} existing • ${j.checksum_mismatch} checksum mismatch • ${j.failed} failed`;$("current").textContent=j.current||j.status;let fp=j.current_percent||0;$("filebar").style.width=fp+"%";$("filepct").textContent=fp+"%";$("filesize").textContent=j.current_size?`${fmtBytes(j.current_bytes)} / ${fmtBytes(j.current_size)}`:(j.current_bytes?fmtBytes(j.current_bytes):"");$("logs").innerHTML=(j.logs||[]).map(x=>`<div class="${x.level}">${x.time} ${esc(x.message)}</div>`).join("");$("logs").scrollTop=$("logs").scrollHeight;if(["completed","cancelled"].includes(j.status)){clearInterval(timer);timer=null;checkLibrary();checkResume()}}
function fmtBytes(n){n=Number(n||0);if(!n)return "0 B";let u=["B","KB","MB","GB","TB"],i=Math.min(Math.floor(Math.log(n)/Math.log(1024)),4);return `${(n/Math.pow(1024,i)).toFixed(i?1:0)} ${u[i]}`}
async function cancel(){if(job)await fetch("/api/job/"+job+"/cancel",{method:"POST"})}
async function catalogue(){let d=$("dest").value.trim();if(!d)return alert("Enter the archive/catalogue folder.");let r=await fetch("/api/catalogue",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({destination:d})}),x=await r.json();if(!r.ok)return alert(x.error);alert(`Catalogue created.\n${x.statistics.purchases} purchases\n${x.statistics.products} products\n${x.statistics.files} files\n\nOpen: ${x.index}`)}

function helpCookie(){document.getElementById("help").showModal()}
function about(){alert("Humble Library Manager v2.1.4\n\nOriginally created by Arun Sutharshan\nwww.sutharshan.co.uk\narun@sutharshan.co.uk\n\nCommunity open-source project • MIT License\nAI-assisted development tools were used during development.\n\nIndependent project — not affiliated with or endorsed by Humble Bundle.")}
async function checkResume(){let d=$("dest").value.trim();if(!d)return;let r=await fetch("/api/resume-info",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({destination:d})}),x=await r.json();$("resumeBtn").classList.toggle("hide",!x.found);if(x.found)$("resumeBtn").textContent=`Resume Previous Download (${x.completed}/${x.total})`}
async function resumePrevious(){let r=await fetch("/api/resume",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({destination:$("dest").value})}),j=await r.json();if(!r.ok)return alert(j.error);job=j.job_id;$("prog").classList.remove("hide");poll();timer=setInterval(poll,800)}
$("dest").addEventListener("change",checkResume);setTimeout(checkResume,500);

async function chooseFolder(){
  if(window.showDirectoryPicker){
    try{
      const h=await window.showDirectoryPicker();
      alert(`Selected folder: ${h.name}\n\nFor security, the browser does not expose its full Windows path to this local web app. Enter/paste the full path in the Library folder box if it is not already correct.`);
      return;
    }catch(e){if(e.name==="AbortError")return;}
  }
  const p=prompt("Enter or paste the full library folder path:",$("dest").value);
  if(p!==null){$("dest").value=p;checkLibrary();checkResume();}
}
async function checkLibrary(){
 let d=$("dest").value.trim();if(!d)return;
 let r=await fetch("/api/library-info",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({destination:d})}),x=await r.json();
 if(!r.ok)return;
 $("libraryInfo").textContent=x.catalogue?`Existing library detected • ${x.disk_files} files on disk • ${x.catalogued_files} files in catalogue`:(x.exists?`Existing folder detected • ${x.disk_files} files on disk • no catalogue yet`:"New library folder");
}
$("dest").addEventListener("change",checkLibrary);setTimeout(checkLibrary,600);
