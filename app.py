from __future__ import annotations
import time
import hashlib,json,os,re,threading,uuid,ctypes
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse,unquote
import requests
from flask import Flask,jsonify,render_template,request
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from catalogue import export_catalogue
from library_paths import safe,title,year,category,archive_path

app=Flask(__name__); BASE="https://www.humblebundle.com"; VERSION="2.1.3"
def prevent_sleep(enable=True):
 try:
  if os.name=="nt":
   ES_CONTINUOUS=0x80000000;ES_SYSTEM_REQUIRED=0x00000001
   ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS|ES_SYSTEM_REQUIRED if enable else ES_CONTINUOUS)
 except Exception:pass
def queue_file(root):return Path(root).expanduser()/"_library"/"download_queue.json"
def save_queue(root,payload):
 q=queue_file(root);q.parent.mkdir(parents=True,exist_ok=True);q.write_text(json.dumps(payload,indent=2),encoding="utf-8")

STATE={"cookie":None,"orders":[],"details":{},"jobs":{}}; LOCK=threading.Lock()
def session():
 s=requests.Session(); s.headers.update({"User-Agent":"HumbleLibraryManager/2.0","Referer":BASE+"/home/library"})
 if STATE["cookie"]: s.cookies.set("_simpleauth_sess",STATE["cookie"],domain=".humblebundle.com")
 retry=Retry(total=4,backoff_factor=.8,status_forcelist=(429,500,502,503,504),allowed_methods=frozenset(["GET"]))
 s.mount("https://",HTTPAdapter(max_retries=retry,pool_connections=8,pool_maxsize=8)); return s
def getj(url):
 r=session().get(url,timeout=60)
 if r.status_code in (401,403): raise RuntimeError("Authentication rejected. Refresh _simpleauth_sess.")
 r.raise_for_status(); return r.json()
def files(o):
 out=[]
 for pi,sp in enumerate(o.get("subproducts") or []):
  pn=sp.get("human_name") or sp.get("machine_name") or f"Product {pi+1}"
  for gi,g in enumerate(sp.get("downloads") or []):
   platform=g.get("platform") or g.get("machine_name") or "Files"
   for fi,d in enumerate(g.get("download_struct") or []):
    u=(d.get("url") or {}).get("web")
    if not u: continue
    fn=Path(unquote(urlparse(u).path)).name or f"download_{fi+1}"
    out.append({"id":f"{pi}:{gi}:{fi}","product":pn,"platform":platform,"format":d.get("name") or Path(fn).suffix.lstrip(".") or "file","filename":fn,"url":u,"size":d.get("file_size"),"human_size":d.get("human_size"),"sha1":d.get("sha1"),"md5":d.get("md5")})
 return out
def public(o):
 fs=files(o); ps={}
 for f in fs: ps.setdefault(f["product"],[]).append({k:v for k,v in f.items() if k!="url"})
 return {"gamekey":o["gamekey"],"title":title(o),"created":o.get("created"),"year":year(o),"category":category(o),"file_count":len(fs),"products":ps}

@app.get("/")
def index(): return render_template("index.html")
@app.post("/api/validate")
def validate():
 c=(request.json or {}).get("cookie","").strip()
 if not c:return jsonify(error="Enter _simpleauth_sess."),400
 STATE["cookie"]=c
 try:
  x=getj(BASE+"/api/v1/user/order")
  if not isinstance(x,list):raise RuntimeError("Unexpected Humble library response.")
  STATE["orders"]=x;STATE["details"]={};return jsonify(ok=True,count=len(x))
 except Exception as e: STATE["cookie"]=None;return jsonify(error=str(e)),400
@app.post("/api/load")
def load():
 if not STATE["cookie"]:return jsonify(error="Validate authentication first."),401
 errors=[]
 def one(ref):
  k=ref.get("gamekey")
  if not k:return
  o=getj(BASE+f"/api/v1/order/{k}?all_tpkds=true");o["gamekey"]=k;return k,o
 with ThreadPoolExecutor(max_workers=5) as ex:
  fut=[ex.submit(one,r) for r in STATE["orders"]]
  for f in as_completed(fut):
   try:
    z=f.result()
    if z:STATE["details"][z[0]]=z[1]
   except Exception as e:errors.append(str(e))
 d=[public(o) for o in STATE["details"].values()];d.sort(key=lambda x:str(x["created"] or ""),reverse=True)
 return jsonify(orders=d,errors=errors)
@app.post("/api/catalogue")
def catalogue_export():
 b=request.json or {}; dest=(b.get("destination") or "").strip()
 if not dest:return jsonify(error="Enter a catalogue/archive folder."),400
 if not STATE["details"]:return jsonify(error="Load the library first."),400
 try:
  m=export_catalogue(STATE["details"],dest)
  return jsonify(ok=True,index=str(Path(dest)/"index.html"),statistics=m["statistics"])
 except Exception as e:return jsonify(error=str(e)),500

@app.post("/api/resume-info")
def resume_info():
 b=request.json or {};dest=(b.get("destination") or "").strip()
 if not dest:return jsonify(found=False)
 q=queue_file(dest)
 if not q.exists():return jsonify(found=False)
 try:
  x=json.loads(q.read_text(encoding="utf-8"))
  if x.get("status") in ("completed","cancelled"):return jsonify(found=False)
  return jsonify(found=True,total=x.get("total",0),completed=len(x.get("completed_ids",[])),remaining=len(x.get("remaining",[])))
 except Exception:return jsonify(found=False)

@app.post("/api/resume")
def resume():
 b=request.json or {};dest=(b.get("destination") or "").strip();q=queue_file(dest)
 if not q.exists():return jsonify(error="No incomplete download session found."),404
 try:x=json.loads(q.read_text(encoding="utf-8"))
 except Exception as e:return jsonify(error=str(e)),400
 if not STATE["details"]:return jsonify(error="Load the Humble library first, then resume."),400
 keys=x.get("keys") or [];picks=x.get("file_ids") or {}
 jid=str(uuid.uuid4());STATE["jobs"][jid]={"status":"queued","total":0,"done":0,"downloaded":0,"verified":0,"checksum_mismatch":0,"skipped":0,"failed":0,"retrying":0,"bytes_done":0,"current":"","logs":[],"cancel":False,"destination":dest}
 threading.Thread(target=run,args=(jid,keys,picks),daemon=True).start();return jsonify(job_id=jid)

@app.post("/api/start")
def start():
 b=request.json or {};dest=(b.get("destination") or "").strip()
 if not dest:return jsonify(error="Enter a download folder."),400
 jid=str(uuid.uuid4());STATE["jobs"][jid]={"status":"queued","total":0,"done":0,"downloaded":0,"verified":0,"checksum_mismatch":0,"skipped":0,"failed":0,"retrying":0,"bytes_done":0,"current":"","logs":[],"cancel":False,"destination":dest}
 threading.Thread(target=run,args=(jid,b.get("keys") or [],b.get("file_ids") or {}),daemon=True).start();return jsonify(job_id=jid)
def log(j,m,l="info"):
 with LOCK:j["logs"].append({"time":datetime.now().strftime("%H:%M:%S"),"level":l,"message":m});j["logs"]=j["logs"][-500:]
def digest(p,a):
 h=hashlib.new(a)
 with p.open("rb") as fh:
  for b in iter(lambda:fh.read(1048576),b""):h.update(b)
 return h.hexdigest()
def run(jid,keys,picks):
 j=STATE["jobs"][jid];j["status"]="running";tasks=[];prevent_sleep(True)
 for k in keys:
  o=STATE["details"].get(k)
  if not o:continue
  chosen=picks.get(k)
  for f in files(o):
   if chosen is not None and f["id"] not in set(chosen):continue
   tasks.append((o,f))
 j["total"]=len(tasks);log(j,f"Queue contains {len(tasks)} files.")
 save_queue(j["destination"],{"version":VERSION,"status":"running","total":len(tasks),"keys":keys,"file_ids":{k:list(v) if isinstance(v,set) else v for k,v in picks.items()},"completed_ids":[],"remaining":[f["id"]+"|"+str(o.get("gamekey")) for o,f in tasks]})
 root=Path(j["destination"]).expanduser()
 pending=[(o,f,1) for o,f in tasks]
 final_done=0
 max_attempts=5
 completed_ids=[]
 def checkpoint():
  save_queue(root,{"version":VERSION,"status":j["status"],"total":j["total"],"keys":keys,"file_ids":{k:list(v) if isinstance(v,set) else v for k,v in picks.items()},"completed_ids":completed_ids,"remaining":[f["id"]+"|"+str(o.get("gamekey")) for o,f,a in pending]})
 while pending and not j["cancel"]:
  current=pending;pending=[]
  round_no=current[0][2] if current else 1
  if round_no>1:
   j["retrying"]=len(current)
   log(j,f"Retry round {round_no}/{max_attempts} — {len(current)} file(s).")
   time.sleep(min(2*(round_no-1),8))
  for o,f,attempt in current:
   if j["cancel"]:break
   prefix=f"[{final_done+1} of {j['total']}]"
   if attempt>1: prefix+=f" [Attempt {attempt}/{max_attempts}]"
   try:
    dest=archive_path(root,o,f);dest.parent.mkdir(parents=True,exist_ok=True);j["current"]=f'{final_done+1} of {j["total"]}: {f["product"]} - {f["filename"]}'
   except Exception as e:
    if attempt<max_attempts:
     pending.append((o,f,attempt+1));log(j,f"{prefix} PATH ERROR — queued for retry: {f['filename']} — {e}","error")
    else:
     j["failed"]+=1;j["done"]+=1;final_done+=1;completed_ids.append(f["id"]+"|"+str(o.get("gamekey")));checkpoint();log(j,f"{prefix} FAILED after {max_attempts} attempts: {f['filename']} — {e}","error")
    continue
   try:
    sz=f.get("size")
    if dest.exists() and ((sz and dest.stat().st_size==int(sz)) or not sz):
     j["skipped"]+=1;j["done"]+=1;final_done+=1;completed_ids.append(f["id"]+"|"+str(o.get("gamekey")));checkpoint();log(j,f"{prefix} Skipped existing: {dest.name}","skip");continue
    part=Path(str(dest)+".part");pos=part.stat().st_size if part.exists() else 0;headers={"Range":f"bytes={pos}-"} if pos else {}
    r=session().get(f["url"],stream=True,timeout=90,headers=headers)
    if pos and r.status_code!=206:
     r.close();part.unlink(missing_ok=True);pos=0;r=session().get(f["url"],stream=True,timeout=90)
    r.raise_for_status()
    with part.open("ab" if pos else "wb") as fh:
     for chunk in r.iter_content(1048576):
      if j["cancel"]:break
      if chunk:fh.write(chunk);j["bytes_done"]+=len(chunk)
    r.close()
    if j["cancel"]:break
    chk,alg=(f.get("sha1"),"sha1") if f.get("sha1") else ((f.get("md5"),"md5") if f.get("md5") else (None,None))
    actual=digest(part,alg).lower() if chk else None
    mismatch=bool(chk and actual!=str(chk).lower())
    os.replace(part,dest)
    j["downloaded"]+=1;j["done"]+=1;final_done+=1;completed_ids.append(f["id"]+"|"+str(o.get("gamekey")));checkpoint()
    if mismatch:
     j["checksum_mismatch"]+=1
     log(j,f"{prefix} Downloaded — CHECKSUM MISMATCH: {f['product']} / {f['filename']} | expected {alg.upper()}={chk} | actual={actual}","warn")
    else:
     if chk:j["verified"]+=1
     log(j,f"{prefix} Downloaded: {f['product']} / {f['filename']}","ok")
   except Exception as e:
    # Genuine transfer/filesystem failures rotate to the end of the retry queue.
    if attempt<max_attempts:
     pending.append((o,f,attempt+1));log(j,f"{prefix} FAILED — queued for retry: {f['filename']} — {e}","error")
    else:
     j["failed"]+=1;j["done"]+=1;final_done+=1;completed_ids.append(f["id"]+"|"+str(o.get("gamekey")));checkpoint();log(j,f"{prefix} FAILED after {max_attempts} attempts: {f['filename']} — {e}","error")
  j["retrying"]=len(pending)
 j["current"]="";j["retrying"]=0;j["status"]="cancelled" if j["cancel"] else "completed"
 lib=root/"_library";lib.mkdir(parents=True,exist_ok=True)
 summary={k:v for k,v in j.items() if k not in ("logs","cancel")}
 (lib/"latest_download.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
 save_queue(root,{"version":VERSION,"status":j["status"],"total":j["total"],"keys":keys,"file_ids":{k:list(v) if isinstance(v,set) else v for k,v in picks.items()},"completed_ids":completed_ids,"remaining":[] if j["status"]=="completed" else [f["id"]+"|"+str(o.get("gamekey")) for o,f,a in pending]})
 prevent_sleep(False)
 if not j["cancel"]:
  log(j,f"Completed: {j['downloaded']} downloaded ({j['verified']} checksum verified, {j['checksum_mismatch']} checksum mismatch), {j['skipped']} skipped, {j['failed']} failed after retries.")
 else:log(j,"Download run cancelled.")

@app.get("/api/job/<jid>")
def job(jid):
 j=STATE["jobs"].get(jid)
 return (jsonify({k:v for k,v in j.items() if k!="cancel"}) if j else (jsonify(error="Job not found"),404))
@app.post("/api/job/<jid>/cancel")
def cancel(jid):
 if jid in STATE["jobs"]:STATE["jobs"][jid]["cancel"]=True
 return jsonify(ok=True)
if __name__=="__main__":
 import webbrowser
 threading.Timer(1,lambda:webbrowser.open("http://127.0.0.1:8765")).start()
 app.run(host="127.0.0.1",port=8765,debug=False,threaded=True)
