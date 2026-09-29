from __future__ import annotations
import ctypes, hashlib, json, os, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, unquote
import requests
from flask import Flask, jsonify, render_template, request
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from catalogue import export_catalogue, reconcile_catalogue, render_existing_catalogue
from library_audit import audit_library, apply_audit
from library_state import reconcile as reconcile_local, persist as persist_local
from library_paths import title, year, category, archive_path

app=Flask(__name__)
BASE="https://www.humblebundle.com"; VERSION="2.1.6"
STATE={"cookie":None,"orders":[],"details":{},"jobs":{}}
LOCK=threading.Lock()

def prevent_sleep(enable=True):
    try:
        if os.name=="nt":
            ES_CONTINUOUS=0x80000000; ES_SYSTEM_REQUIRED=0x00000001
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS|ES_SYSTEM_REQUIRED if enable else ES_CONTINUOUS)
    except Exception: pass

def session():
    s=requests.Session()
    s.headers.update({"User-Agent":f"HumbleLibraryManager/{VERSION}","Referer":BASE+"/home/library"})
    if STATE["cookie"]: s.cookies.set("_simpleauth_sess",STATE["cookie"],domain=".humblebundle.com")
    retry=Retry(total=4,backoff_factor=.8,status_forcelist=(429,500,502,503,504),allowed_methods=frozenset(["GET"]))
    s.mount("https://",HTTPAdapter(max_retries=retry,pool_connections=8,pool_maxsize=8))
    return s

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
                out.append({"id":f"{pi}:{gi}:{fi}","product":pn,"platform":platform,
                    "format":d.get("name") or Path(fn).suffix.lstrip(".") or "file",
                    "filename":fn,"url":u,"size":d.get("file_size"),"human_size":d.get("human_size"),
                    "sha1":d.get("sha1"),"md5":d.get("md5")})
    return out

def public(o):
    fs=files(o); ps={}
    for f in fs: ps.setdefault(f["product"],[]).append({k:v for k,v in f.items() if k!="url"})
    return {"gamekey":o["gamekey"],"title":title(o),"created":o.get("created"),"year":year(o),
            "category":category(o),"file_count":len(fs),"products":ps}

def queue_file(root): return Path(root).expanduser()/"_library"/"download_queue.json"
def status_file(root): return Path(root).expanduser()/"_library"/"file_status.json"

def atomic_json(path,payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    t=Path(str(path)+".tmp");t.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8");os.replace(t,path)

def load_status(root):
    p=status_file(root)
    try:return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:return {}

def save_status(root,data): atomic_json(status_file(root),data)

def human_bytes(n):
    if n is None:return "Unknown size"
    try:n=float(n)
    except Exception:return str(n)
    for unit in ("B","KB","MB","GB","TB"):
        if n<1024 or unit=="TB":return f"{n:.1f} {unit}" if unit!="B" else f"{int(n)} B"
        n/=1024

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
        STATE["orders"]=x;STATE["details"]={}
        return jsonify(ok=True,count=len(x))
    except Exception as e:
        STATE["cookie"]=None;return jsonify(error=str(e)),400

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
    d=[public(o) for o in STATE["details"].values()]
    d.sort(key=lambda x:str(x["created"] or ""),reverse=True)
    return jsonify(orders=d,errors=errors)


@app.post("/api/choose-folder")
def choose_folder():
    try:
        import tkinter as tk
        from tkinter import filedialog
        top=tk.Tk();top.withdraw();top.attributes("-topmost",True)
        initial=(request.json or {}).get("initial") or str(Path.cwd())
        p=filedialog.askdirectory(initialdir=str(Path(initial).expanduser()) if Path(initial).expanduser().exists() else str(Path.cwd()),title="Select Humble Library folder")
        top.destroy()
        return jsonify(path=p or "")
    except Exception as e:return jsonify(error=f"Folder picker unavailable: {e}"),500

@app.post("/api/library-info")
def library_info():
    b=request.json or {};dest=(b.get("destination") or "").strip()
    if not dest:return jsonify(error="Enter a library folder."),400
    root=Path(dest).expanduser()
    cat=root/"catalogue"/"library.json"
    old={}
    try:old=json.loads(cat.read_text(encoding="utf-8")) if cat.exists() else {}
    except Exception:old={}
    state=reconcile_local(root) if root.exists() else {"summary":{"files_on_disk":0,"matched":0,"missing":0,"partial":0}}
    oldfiles=(old.get("statistics") or {}).get("files",0)
    s=state["summary"]
    return jsonify(exists=root.exists(),catalogue=cat.exists(),catalogued_files=oldfiles,disk_files=s["files_on_disk"],matched=s["matched"],missing=s["missing"],partial=s["partial"])

@app.post("/api/audit")
def local_audit():
    b=request.json or {};dest=(b.get("destination") or "").strip()
    if not dest:return jsonify(error="Enter an existing library folder."),400
    try:
        x=audit_library(dest);atomic_json(Path(dest).expanduser()/"_library"/"catalogue_audit.json",x);return jsonify(ok=True,audit=x)
    except Exception as e:return jsonify(error=str(e)),500

@app.post("/api/repair-catalogue")
def repair_catalogue():
    b=request.json or {};dest=(b.get("destination") or "").strip()
    if not dest:return jsonify(error="Enter an existing library folder."),400
    try:
        x=audit_library(dest);n=apply_audit(dest,x);m=render_existing_catalogue(dest)
        return jsonify(ok=True,audit=x,updated_paths=n,statistics=m.get("statistics",{}))
    except Exception as e:return jsonify(error=str(e)),500

@app.post("/api/catalogue")
def catalogue_export():
    b=request.json or {};dest=(b.get("destination") or "").strip()
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
    keys=b.get("keys") or [];picks=b.get("file_ids") or {}
    jid=str(uuid.uuid4())
    STATE["jobs"][jid]={"status":"queued","total":0,"done":0,"downloaded":0,"verified":0,
      "checksum_mismatch":0,"skipped":0,"failed":0,"retrying":0,"bytes_done":0,
      "current":"","current_purchase":"","current_file":"","current_size":0,
      "current_bytes":0,"current_percent":0,"logs":[],"cancel":False,"destination":dest}
    threading.Thread(target=run,args=(jid,keys,picks),daemon=True).start()
    return jsonify(job_id=jid)

@app.post("/api/resume-info")
def resume_info():
    b=request.json or {};dest=(b.get("destination") or "").strip();q=queue_file(dest) if dest else None
    if not q or not q.exists():return jsonify(found=False)
    try:
        x=json.loads(q.read_text(encoding="utf-8"))
        if x.get("status")=="completed":return jsonify(found=False)
        return jsonify(found=True,total=x.get("total",0),completed=len(x.get("completed_ids",[])))
    except Exception:return jsonify(found=False)

@app.post("/api/resume")
def resume():
    b=request.json or {};dest=(b.get("destination") or "").strip();q=queue_file(dest)
    if not q.exists():return jsonify(error="No incomplete download session found."),404
    if not STATE["details"]:return jsonify(error="Load the Humble library first, then resume."),400
    x=json.loads(q.read_text(encoding="utf-8"))
    return start_from_saved(dest,x)

def start_from_saved(dest,x):
    jid=str(uuid.uuid4())
    STATE["jobs"][jid]={"status":"queued","total":0,"done":0,"downloaded":0,"verified":0,
      "checksum_mismatch":0,"skipped":0,"failed":0,"retrying":0,"bytes_done":0,
      "current":"","current_purchase":"","current_file":"","current_size":0,
      "current_bytes":0,"current_percent":0,"logs":[],"cancel":False,"destination":dest}
    threading.Thread(target=run,args=(jid,x.get("keys") or [],x.get("file_ids") or {}),daemon=True).start()
    return jsonify(job_id=jid)

def log(j,m,l="info"):
    with LOCK:
        j["logs"].append({"time":datetime.now().strftime("%H:%M:%S"),"level":l,"message":m})
        j["logs"]=j["logs"][-1000:]

def digest(p,a):
    h=hashlib.new(a)
    with p.open("rb") as fh:
        for b in iter(lambda:fh.read(1048576),b""):h.update(b)
    return h.hexdigest()

def run(jid,keys,picks):
    j=STATE["jobs"][jid];j["status"]="running";prevent_sleep(True)
    root=Path(j["destination"]).expanduser(); statuses=load_status(root)
    tasks=[]
    try:
        for k in keys:
            o=STATE["details"].get(k)
            if not o:continue
            chosen=picks.get(k)
            chosen=set(chosen) if chosen is not None else None
            for f in files(o):
                if chosen is not None and f["id"] not in chosen:continue
                tasks.append((len(tasks)+1,o,f))
        # Reconcile the existing catalogue against the actual filesystem first.
        # Only known missing/partial records are queued when the catalogue can identify them.
        state=reconcile_local(root);persist_local(root,state)
        if state.get("summary",{}).get("known"):
            missing_keys={str(x.get("purchase_id"))+"|"+str(x.get("file_id")) for x in state.get("missing",[])}
            filtered=[]
            for _,o,f in tasks:
                k=str(o.get("gamekey"))+"|"+str(f.get("id"))
                if k in missing_keys: filtered.append((len(filtered)+1,o,f))
            existing_count=len(tasks)-len(filtered);tasks=filtered
            log(j,f"Reconciled library: {state['summary']['matched']} matched, {state['summary']['missing']} missing, {state['summary']['partial']} partial, {state['summary']['unmapped']} unmapped.")
            if existing_count:log(j,f"{existing_count} selected file(s) already exist and were excluded from the download queue.")
        j["total"]=len(tasks);log(j,f"Download queue contains {len(tasks)} genuinely missing file(s).")
        atomic_json(queue_file(root),{"version":VERSION,"status":"running","total":len(tasks),"keys":keys,"file_ids":picks,"completed_ids":[]})
        pending=[(idx,o,f,1) for idx,o,f in tasks];completed=[]
        max_attempts=5
        while pending and not j["cancel"]:
            current=pending;pending=[]
            round_no=current[0][3] if current else 1
            if round_no>1:
                j["retrying"]=len(current);log(j,f"Retry round {round_no}/{max_attempts} — {len(current)} file(s).")
                time.sleep(min(2*(round_no-1),8))
            for idx,o,f,attempt in current:
                if j["cancel"]:break
                purchase=title(o);prefix=f"[{idx} of {j['total']}] {purchase} — {f['filename']}"
                if attempt>1:prefix+=f" [Attempt {attempt} of {max_attempts}]"
                j["current_purchase"]=purchase;j["current_file"]=f["filename"];j["current_size"]=int(f.get("size") or 0)
                j["current_bytes"]=0;j["current_percent"]=0;j["current"]=prefix
                key=f"{o.get('gamekey')}|{f['id']}"
                try:
                    dest=archive_path(root,o,f);dest.parent.mkdir(parents=True,exist_ok=True)
                    sz=int(f.get("size") or 0)
                    prior=statuses.get(key,{})
                    # A previously completed mismatch is accepted unless the file is now missing.
                    if dest.exists() and prior.get("status") in ("checksum_mismatch","verified","downloaded"):
                        j["skipped"]+=1;j["done"]+=1;completed.append(key)
                        log(j,f"{prefix} — already downloaded ({human_bytes(dest.stat().st_size)}), status: {prior.get('status')}.","skip");continue
                    if dest.exists() and ((sz and dest.stat().st_size==sz) or not sz):
                        j["skipped"]+=1;j["done"]+=1;completed.append(key)
                        statuses[key]={"status":"downloaded","local_path":str(dest.relative_to(root)).replace("\\","/"),"size":dest.stat().st_size,"updated_at":datetime.now(timezone.utc).isoformat()}
                        save_status(root,statuses);log(j,f"{prefix} — existing file found ({human_bytes(dest.stat().st_size)}).","skip");continue
                    part=Path(str(dest)+".part");pos=part.stat().st_size if part.exists() else 0
                    headers={"Range":f"bytes={pos}-"} if pos else {}
                    r=session().get(f["url"],stream=True,timeout=90,headers=headers)
                    if pos and r.status_code!=206:
                        r.close();part.unlink(missing_ok=True);pos=0;r=session().get(f["url"],stream=True,timeout=90)
                    r.raise_for_status()
                    total=sz or (pos+int(r.headers.get("Content-Length") or 0))
                    j["current_size"]=total;j["current_bytes"]=pos
                    log(j,f"{prefix} — downloading {human_bytes(pos)} / {human_bytes(total)} ({int(pos*100/total) if total else 0}%).")
                    last_report=-1
                    with part.open("ab" if pos else "wb") as fh:
                        for chunk in r.iter_content(1048576):
                            if j["cancel"]:break
                            if chunk:
                                fh.write(chunk);j["bytes_done"]+=len(chunk);j["current_bytes"]+=len(chunk)
                                pct=int(j["current_bytes"]*100/total) if total else 0;j["current_percent"]=min(100,pct)
                                bucket=pct//10
                                if bucket>last_report and pct<100:
                                    last_report=bucket;log(j,f"{prefix} — {human_bytes(j['current_bytes'])} / {human_bytes(total)} ({pct}%).")
                    r.close()
                    if j["cancel"]:break
                    chk,alg=(f.get("sha1"),"sha1") if f.get("sha1") else ((f.get("md5"),"md5") if f.get("md5") else (None,None))
                    actual=digest(part,alg).lower() if chk else None
                    mismatch=bool(chk and actual!=str(chk).lower())
                    os.replace(part,dest);j["downloaded"]+=1;j["done"]+=1;completed.append(key);j["current_percent"]=100
                    stat={"status":"checksum_mismatch" if mismatch else ("verified" if chk else "downloaded"),
                          "local_path":str(dest.relative_to(root)).replace("\\","/"),"size":dest.stat().st_size,
                          "checksum_algorithm":alg,"expected_checksum":chk,"actual_checksum":actual,
                          "updated_at":datetime.now(timezone.utc).isoformat()}
                    statuses[key]=stat;save_status(root,statuses)
                    if mismatch:
                        j["checksum_mismatch"]+=1
                        log(j,f"{prefix} — downloaded {human_bytes(dest.stat().st_size)} — CHECKSUM MISMATCH retained. Expected {alg.upper()}={chk}; actual={actual}.","warn")
                    else:
                        if chk:j["verified"]+=1
                        log(j,f"{prefix} — downloaded {human_bytes(dest.stat().st_size)} — {'checksum verified' if chk else 'complete'}.","ok")
                except Exception as e:
                    if attempt<max_attempts:
                        pending.append((idx,o,f,attempt+1));log(j,f"{prefix} — FAILED, queued for rotational retry: {e}","error")
                    else:
                        j["failed"]+=1;j["done"]+=1;completed.append(key);log(j,f"{prefix} — FAILED after {max_attempts} attempts: {e}","error")
                atomic_json(queue_file(root),{"version":VERSION,"status":"running","total":j["total"],"keys":keys,"file_ids":picks,"completed_ids":completed})
            j["retrying"]=len(pending)
        j["current"]="";j["current_purchase"]="";j["current_file"]="";j["current_size"]=0;j["current_bytes"]=0;j["current_percent"]=0
        j["retrying"]=0;j["status"]="cancelled" if j["cancel"] else "completed"
        atomic_json(queue_file(root),{"version":VERSION,"status":j["status"],"total":j["total"],"keys":keys,"file_ids":picks,"completed_ids":completed})
        lib=root/"_library";lib.mkdir(parents=True,exist_ok=True)
        summary={k:v for k,v in j.items() if k not in ("logs","cancel")}
        atomic_json(lib/"latest_download.json",summary)
        if not j["cancel"]:
            log(j,f"Completed: {j['done']} of {j['total']} queued files processed; {j['downloaded']} downloaded ({j['verified']} verified, {j['checksum_mismatch']} checksum mismatch retained), {j['failed']} failed.")
            try:
                audit=audit_library(root);apply_audit(root,audit);render_existing_catalogue(root)
                log(j,f"Post-download audit: {audit['summary']['matched']} matched, {audit['summary']['missing']} missing, {audit['summary']['partial']} partial. Catalogue regenerated.","ok")
            except Exception as e:log(j,f"Post-download catalogue refresh warning: {e}","warn")
        else:log(j,"Download run cancelled. Partial files and session state were retained.")
    finally:
        prevent_sleep(False)

@app.get("/api/job/<jid>")
def job(jid):
    j=STATE["jobs"].get(jid)
    return jsonify({k:v for k,v in j.items() if k!="cancel"}) if j else (jsonify(error="Job not found"),404)

@app.post("/api/job/<jid>/cancel")
def cancel(jid):
    if jid in STATE["jobs"]:STATE["jobs"][jid]["cancel"]=True
    return jsonify(ok=True)

if __name__=="__main__":
    import webbrowser
    threading.Timer(1,lambda:webbrowser.open("http://127.0.0.1:8765")).start()
    app.run(host="127.0.0.1",port=8765,debug=False,threaded=True)
