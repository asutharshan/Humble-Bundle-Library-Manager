from __future__ import annotations
import hashlib,json,os,re,threading,uuid
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse,unquote
import requests
from flask import Flask,jsonify,render_template,request
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from catalogue import export_catalogue

app=Flask(__name__); BASE="https://www.humblebundle.com"
STATE={"cookie":None,"orders":[],"details":{},"jobs":{}}; LOCK=threading.Lock()
BAD=re.compile(r'[<>:"/\\|?*\x00-\x1f]')
def safe(s,n=160):
 s=BAD.sub("_",(s or "Unknown").strip()); s=re.sub(r"\s+"," ",s).strip(" .") or "Unknown"; return s[:n].rstrip(" .")
def session():
 s=requests.Session(); s.headers.update({"User-Agent":"HumbleLibraryManager/2.0","Referer":BASE+"/home/library"})
 if STATE["cookie"]: s.cookies.set("_simpleauth_sess",STATE["cookie"],domain=".humblebundle.com")
 retry=Retry(total=4,backoff_factor=.8,status_forcelist=(429,500,502,503,504),allowed_methods=frozenset(["GET"]))
 s.mount("https://",HTTPAdapter(max_retries=retry,pool_connections=8,pool_maxsize=8)); return s
def getj(url):
 r=session().get(url,timeout=60)
 if r.status_code in (401,403): raise RuntimeError("Authentication rejected. Refresh _simpleauth_sess.")
 r.raise_for_status(); return r.json()
def title(o):
 p=o.get("product") or {}; return p.get("human_name") or p.get("machine_name") or "Humble Purchase"
def year(o):
 m=re.search(r"(?:19|20)\d{2}",str(o.get("created") or "")); return m.group(0) if m else "Unknown Year"
def category(o):
 vals=[]; p=o.get("product") or {}; vals += [str(p.get(k,"")) for k in ("human_name","machine_name","category")]
 for sp in o.get("subproducts") or []:
  vals += [str(sp.get(k,"")) for k in ("human_name","machine_name")]
  vals += [str(d.get("platform","")) for d in sp.get("downloads") or []]
 t=" ".join(vals).lower()
 if any(x in t for x in ("ebook","book bundle","books bundle")): return "Books"
 if any(x in t for x in ("audio","music bundle")): return "Audio"
 if "software" in t: return "Software"
 if any(x in t for x in ("windows","linux","mac","android")): return "Games & Software"
 return "Other"
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

@app.post("/api/start")
def start():
 b=request.json or {};dest=(b.get("destination") or "").strip()
 if not dest:return jsonify(error="Enter a download folder."),400
 jid=str(uuid.uuid4());STATE["jobs"][jid]={"status":"queued","total":0,"done":0,"downloaded":0,"skipped":0,"failed":0,"bytes_done":0,"current":"","logs":[],"cancel":False,"destination":dest}
 threading.Thread(target=run,args=(jid,b.get("keys") or [],b.get("file_ids") or {}),daemon=True).start();return jsonify(job_id=jid)
def log(j,m,l="info"):
 with LOCK:j["logs"].append({"time":datetime.now().strftime("%H:%M:%S"),"level":l,"message":m});j["logs"]=j["logs"][-500:]
def digest(p,a):
 h=hashlib.new(a)
 with p.open("rb") as fh:
  for b in iter(lambda:fh.read(1048576),b""):h.update(b)
 return h.hexdigest()
def run(jid,keys,picks):
 j=STATE["jobs"][jid];j["status"]="running";tasks=[]
 for k in keys:
  o=STATE["details"].get(k)
  if not o:continue
  chosen=picks.get(k)
  for f in files(o):
   if chosen is not None and f["id"] not in set(chosen):continue
   tasks.append((o,f))
 j["total"]=len(tasks);log(j,f"Queue contains {len(tasks)} files.")
 root=Path(j["destination"]).expanduser()
 for o,f in tasks:
  if j["cancel"]:break
  dest=root/safe(category(o))/safe(year(o))/safe(title(o))/safe(f["product"])/safe(str(f["platform"]))/safe(f["filename"],190);dest.parent.mkdir(parents=True,exist_ok=True);j["current"]=f'{f["product"]} — {f["filename"]}'
  try:
   sz=f.get("size")
   if dest.exists() and ((sz and dest.stat().st_size==int(sz)) or not sz):j["skipped"]+=1;j["done"]+=1;log(j,"Skipped existing: "+dest.name,"skip");continue
   part=Path(str(dest)+".part");pos=part.stat().st_size if part.exists() else 0;headers={"Range":f"bytes={pos}-"} if pos else {}
   r=session().get(f["url"],stream=True,timeout=90,headers=headers)
   if pos and r.status_code!=206:r.close();part.unlink(missing_ok=True);pos=0;r=session().get(f["url"],stream=True,timeout=90)
   r.raise_for_status()
   with part.open("ab" if pos else "wb") as fh:
    for chunk in r.iter_content(1048576):
     if j["cancel"]:break
     if chunk:fh.write(chunk);j["bytes_done"]+=len(chunk)
   r.close()
   if j["cancel"]:break
   chk,alg=(f.get("sha1"),"sha1") if f.get("sha1") else ((f.get("md5"),"md5") if f.get("md5") else (None,None))
   if chk and digest(part,alg).lower()!=str(chk).lower():raise RuntimeError(alg.upper()+" checksum mismatch")
   os.replace(part,dest);j["downloaded"]+=1;j["done"]+=1;log(j,"Downloaded: "+f["product"]+" / "+f["filename"],"ok")
  except Exception as e:j["failed"]+=1;j["done"]+=1;log(j,"FAILED: "+f["filename"]+" — "+str(e),"error")
 j["current"]="";j["status"]="cancelled" if j["cancel"] else "completed";lib=root/"_library";lib.mkdir(parents=True,exist_ok=True);(lib/"latest_download.json").write_text(json.dumps({k:v for k,v in j.items() if k not in ("logs","cancel")},indent=2),encoding="utf-8");log(j,"Download run "+j["status"]+".")
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
