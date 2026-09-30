from pathlib import Path
from datetime import datetime, timezone
import json, os

def _load(p,default=None):
    try:return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:return {} if default is None else default

def path_for(root): return Path(root)/"_library"/"record_registry.json"

def load(root):
    x=_load(path_for(root),{})
    return x if isinstance(x,dict) else {}

def save(root,data):
    p=path_for(root);p.parent.mkdir(parents=True,exist_ok=True)
    payload={"schema":"humble-library-record-registry","schema_version":"1.0",
             "updated_at":datetime.now(timezone.utc).isoformat(),"records":data.get("records",data)}
    t=Path(str(p)+".tmp");t.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8");os.replace(t,p)

def records(root):
    x=load(root);return x.get("records",{}) if "records" in x else x

def confirm(root,key,local_path,size=None,status="present",source="unknown",extra=None):
    data=records(root)
    row=dict(data.get(key,{}) or {})
    row.update({"local_path":str(local_path).replace("\\","/"),"size":size,"status":status,
                "confirmed_by":source,"last_confirmed":datetime.now(timezone.utc).isoformat()})
    if extra: row.update({k:v for k,v in extra.items() if v is not None})
    data[key]=row;save(root,{"records":data});return row

def bootstrap(root):
    """Upgrade v2.1.x metadata into the v2.2 registry without touching library files."""
    root=Path(root);data=records(root);added=0
    status=_load(root/"_library"/"file_status.json",{})
    for k,v in status.items():
        lp=v.get("local_path")
        if lp and (root/lp).exists():
            data[k]={**data.get(k,{}),"local_path":lp,"size":(root/lp).stat().st_size,
                     "status":v.get("status") or "present","confirmed_by":"v2.1-file-status",
                     "last_confirmed":v.get("updated_at")}
            added+=1
    state=_load(root/"_library"/"reconciled_state.json",{})
    for k,v in (state.get("matches") or {}).items():
        lp=v.get("path")
        if lp and (root/lp).exists():
            data[k]={**data.get(k,{}),"local_path":lp,"size":v.get("size"),
                     "status":"present","confirmed_by":"v2.1-reconciled-state",
                     "last_confirmed":datetime.now(timezone.utc).isoformat()}
            added+=1
    cat=_load(root/"catalogue"/"library.json",{})
    for p in cat.get("purchases",[]):
        for prod in p.get("products",[]):
            for f in prod.get("files",[]):
                lp=f.get("local_path");key=f"{p.get('id')}|{f.get('file_id')}"
                if lp and (root/lp).exists():
                    data[key]={**data.get(key,{}),"local_path":lp,"size":(root/lp).stat().st_size,
                               "status":f.get("status") or "present","confirmed_by":"catalogue-path",
                               "last_confirmed":datetime.now(timezone.utc).isoformat()}
                    added+=1
    save(root,{"records":data});return added
