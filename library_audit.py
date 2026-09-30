from pathlib import Path
import json
from library_state import reconcile,persist,load_json

def audit_library(root):
    s=reconcile(root);persist(root,s)
    cat=load_json(Path(root)/"catalogue"/"library.json",{})
    purchases=[]
    for p in cat.get("purchases",[]):
        ids=[str(p.get("id"))+"|"+str(f.get("file_id")) for prod in p.get("products",[]) for f in prod.get("files",[])]
        purchases.append({"id":p.get("id"),"title":p.get("title"),"known_files":len(ids),
          "local_files":sum(k in s["matches"] for k in ids),"diagnostics":p.get("diagnostics")})
    z=sum(x["known_files"]==0 for x in purchases)
    s["summary"]["purchases"]=len(purchases);s["summary"]["zero_file_purchases"]=z;s["purchases"]=purchases
    return s

def apply_audit(root,a):
    root=Path(root);p=root/"catalogue/library.json";cat=load_json(p,{})
    if not cat:raise RuntimeError("No existing catalogue/library.json found.")
    n=0
    for pur in cat.get("purchases",[]):
      for prod in pur.get("products",[]):
       for f in prod.get("files",[]):
        k=str(pur.get("id"))+"|"+str(f.get("file_id"));m=a.get("matches",{}).get(k)
        if m:
          n+=f.get("local_path")!=m["path"];f["local_path"]=m["path"];f["downloaded"]=True;f["matched_by"]=m["method"]
          if f.get("status") in (None,"new","missing","historical_missing"):f["status"]="downloaded"
        else:
          f["downloaded"]=False
          if f.get("status")!="checksum_mismatch":f["status"]="missing"
    cat["last_local_audit"]=a["generated_at"];p.write_text(json.dumps(cat,indent=2,ensure_ascii=False),encoding="utf-8")
    persist(root,a);return n
