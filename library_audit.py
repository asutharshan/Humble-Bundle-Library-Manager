from pathlib import Path
import json
from datetime import datetime,timezone
EX={"catalogue","_library",".git","__pycache__"}
EXT={".pdf",".epub",".mobi",".azw",".azw3",".cbz",".cbr",".djvu",".zip",".rar",".7z",".exe",".msi",".dmg",".pkg",".apk",".mp3",".m4a",".flac",".wav"}
def load(p,d={}):
    try:return json.loads(Path(p).read_text(encoding="utf-8"))
    except:return d
def audit_library(root):
    root=Path(root); disk=[]
    if root.exists():
      for p in root.rglob("*"):
        if not p.is_file():continue
        rel=p.relative_to(root)
        if any(x in EX for x in rel.parts):continue
        if p.name.endswith(".part") or p.suffix.lower() in EXT:
          disk.append({"path":rel.as_posix(),"name":p.name,"size":p.stat().st_size,"partial":p.name.endswith(".part")})
    cat=load(root/"catalogue/library.json",{})
    bypath={x["path"].lower():x for x in disk}; byname={}
    for x in disk:byname.setdefault(x["name"].lower(),[]).append(x)
    matched=[];missing=[];amb=[];purchases=[]
    for p in cat.get("purchases",[]):
      flags=[]
      for prod in p.get("products",[]):
       for f in prod.get("files",[]):
        lp=str(f.get("local_path") or "").replace("\\","/"); hit=bypath.get(lp.lower()) if lp else None; method="recorded_path" if hit else None
        if not hit:
          cand=[x for x in byname.get(str(f.get("filename") or "").lower(),[]) if not x["partial"]]; sz=f.get("size_bytes")
          sized=[x for x in cand if sz is not None and x["size"]==sz]
          if len(sized)==1:hit=sized[0];method="filename_size"
          elif len(sized)>1:amb.append({"purchase":p.get("title"),"filename":f.get("filename"),"candidates":[x["path"] for x in sized]})
          elif sz is None and len(cand)==1:hit=cand[0];method="unique_filename"
        if hit:matched.append({"purchase_id":str(p.get("id")),"file_id":str(f.get("file_id")),"filename":f.get("filename"),"path":hit["path"],"method":method});flags.append(1)
        else:missing.append({"purchase":p.get("title"),"filename":f.get("filename"),"recorded_path":lp});flags.append(0)
      purchases.append({"id":p.get("id"),"title":p.get("title"),"known_files":len(flags),"local_files":sum(flags)})
    mp={x["path"].lower() for x in matched}
    unmapped=[x for x in disk if not x["partial"] and x["path"].lower() not in mp];partial=[x for x in disk if x["partial"]]
    return {"generated_at":datetime.now(timezone.utc).isoformat(),"root":str(root),"catalogue_found":bool(cat),
      "summary":{"purchases":len(purchases),"known_files":sum(x["known_files"] for x in purchases),"files_on_disk":sum(not x["partial"] for x in disk),"matched":len(matched),"missing":len(missing),"unmapped":len(unmapped),"ambiguous":len(amb),"partial":len(partial),"zero_file_purchases":sum(x["known_files"]==0 for x in purchases)},
      "purchases":purchases,"matched":matched,"missing":missing,"unmapped":unmapped,"ambiguous":amb,"partial":partial}
def apply_audit(root,a):
    root=Path(root);p=root/"catalogue/library.json";cat=load(p,{})
    if not cat:raise RuntimeError("No existing catalogue/library.json found.")
    mm={(x["purchase_id"],x["file_id"],str(x["filename"])):x for x in a["matched"]};n=0
    for pur in cat.get("purchases",[]):
      for prod in pur.get("products",[]):
       for f in prod.get("files",[]):
        x=mm.get((str(pur.get("id")),str(f.get("file_id")),str(f.get("filename"))))
        if x:
          n+=f.get("local_path")!=x["path"];f["local_path"]=x["path"];f["downloaded"]=True;f["matched_by"]=x["method"]
          if f.get("status") in (None,"new","missing","historical_missing"):f["status"]="downloaded"
        elif not (f.get("local_path") and (root/f["local_path"]).exists()):
          f["downloaded"]=False
          if f.get("status")!="checksum_mismatch":f["status"]="missing"
    cat["last_local_audit"]=a["generated_at"];p.write_text(json.dumps(cat,indent=2,ensure_ascii=False),encoding="utf-8")
    lib=root/"_library";lib.mkdir(parents=True,exist_ok=True);(lib/"catalogue_audit.json").write_text(json.dumps(a,indent=2,ensure_ascii=False),encoding="utf-8")
    return n
