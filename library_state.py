from pathlib import Path
import json
from datetime import datetime,timezone
from record_registry import records as registry_records, confirm as registry_confirm, bootstrap as registry_bootstrap

EXCLUDE={"catalogue","_library",".git","__pycache__"}

def load_json(p,d=None):
    try:return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:return {} if d is None else d

def inventory(root):
    root=Path(root);out=[]
    if not root.exists():return out
    for p in root.rglob("*"):
        if not p.is_file():continue
        rel=p.relative_to(root)
        if any(x in EXCLUDE for x in rel.parts):continue
        # index.html is HLM's generated catalogue entry point, not a library payload.
        if len(rel.parts)==1 and p.name.lower()=="index.html":continue
        partial=p.name.endswith(".part")
        try:size=p.stat().st_size
        except OSError:size=None
        out.append({"path":rel.as_posix(),"name":p.name[:-5] if partial else p.name,
                    "actual_name":p.name,"size":size,"partial":partial})
    return out

def expected_records(root):
    cat=load_json(Path(root)/"catalogue"/"library.json",{})
    rows=[]
    for pur in cat.get("purchases",[]):
      for prod in pur.get("products",[]):
       for f in prod.get("files",[]):
        rows.append({"purchase_id":str(pur.get("id")),"purchase":pur.get("title"),"file_id":str(f.get("file_id")),
          "filename":f.get("filename"),"size":f.get("size_bytes"),"local_path":f.get("local_path"),"status":f.get("status"),
          "sha1":f.get("sha1"),"md5":f.get("md5")})
    return rows

def reconcile(root):
    root=Path(root);registry_bootstrap(root)
    disk=inventory(root);expected=expected_records(root)
    files=[x for x in disk if not x["partial"]];partials=[x for x in disk if x["partial"]]
    bypath={x["path"].lower():x for x in files};byname={}
    for x in files:byname.setdefault(x["name"].lower(),[]).append(x)
    reg=registry_records(root);matches={};amb=[];missing=[];used=set()
    for e in expected:
        key=e["purchase_id"]+"|"+e["file_id"];hit=None;method=None
        rr=reg.get(key,{})
        rp=str(rr.get("local_path") or "").replace("\\","/")
        if rp and rp.lower() in bypath:
            hit=bypath[rp.lower()];method="record_registry"
        lp=str(e.get("local_path") or "").replace("\\","/")
        if not hit and lp and lp.lower() in bypath:
            hit=bypath[lp.lower()];method="recorded_path"
        if not hit:
            cand=[x for x in byname.get(str(e.get("filename") or "").lower(),[]) if x["path"].lower() not in used]
            sized=[x for x in cand if e.get("size") is not None and x.get("size")==e.get("size")]
            if len(sized)==1:hit=sized[0];method="filename_size"
            elif len(sized)>1:amb.append({"record":e,"candidates":sized})
            elif e.get("size") is None and len(cand)==1:hit=cand[0];method="unique_filename"
        if hit:
            matches[key]={"path":hit["path"],"size":hit["size"],"method":method};used.add(hit["path"].lower())
            registry_confirm(root,key,hit["path"],hit["size"],"present",method)
        else:missing.append(e)
    unmapped=[x for x in files if x["path"].lower() not in used]
    return {"generated_at":datetime.now(timezone.utc).isoformat(),"root":str(root),
      "summary":{"known":len(expected),"physical_payload_files":len(files),"confirmed_local":len(matches),
                 "matched":len(matches),"missing":len(missing),"unmapped":len(unmapped),
                 "ambiguous":len(amb),"partial":len(partials)},
      "matches":matches,"missing":missing,"unmapped":unmapped,"ambiguous":amb,"partials":partials}

def persist(root,state):
    p=Path(root)/"_library";p.mkdir(parents=True,exist_ok=True)
    t=p/"reconciled_state.json.tmp";t.write_text(json.dumps(state,indent=2,ensure_ascii=False),encoding="utf-8")
    t.replace(p/"reconciled_state.json")

def load_state(root):return load_json(Path(root)/"_library"/"reconciled_state.json",{})
