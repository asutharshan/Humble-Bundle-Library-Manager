from pathlib import Path
import json
from datetime import datetime,timezone
EXCLUDE={"catalogue","_library",".git","__pycache__"}
EXT={".pdf",".epub",".mobi",".azw",".azw3",".cbz",".cbr",".djvu",".zip",".rar",".7z",".exe",".msi",".dmg",".pkg",".apk",".mp3",".m4a",".flac",".wav",".txt",".rtf"}
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
        partial=p.name.endswith(".part")
        if not partial and p.suffix.lower() not in EXT:continue
        try:size=p.stat().st_size
        except OSError:size=None
        out.append({"path":rel.as_posix(),"name":p.name[:-5] if partial else p.name,"actual_name":p.name,"size":size,"partial":partial})
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
    root=Path(root);disk=inventory(root);expected=expected_records(root)
    files=[x for x in disk if not x["partial"]];partials=[x for x in disk if x["partial"]]
    bypath={x["path"].lower():x for x in files};byname={}
    for x in files:byname.setdefault(x["name"].lower(),[]).append(x)
    matches={};amb=[];missing=[]
    used=set()
    for e in expected:
        hit=None;method=None;lp=str(e.get("local_path") or "").replace("\\","/")
        if lp and lp.lower() in bypath:hit=bypath[lp.lower()];method="recorded_path"
        if not hit:
            cand=[x for x in byname.get(str(e.get("filename") or "").lower(),[]) if x["path"].lower() not in used]
            sized=[x for x in cand if e.get("size") is not None and x.get("size")==e.get("size")]
            if len(sized)==1:hit=sized[0];method="filename_size"
            elif len(sized)>1:amb.append({"record":e,"candidates":sized})
            elif e.get("size") is None and len(cand)==1:hit=cand[0];method="unique_filename"
        key=e["purchase_id"]+"|"+e["file_id"]
        if hit:matches[key]={"path":hit["path"],"size":hit["size"],"method":method};used.add(hit["path"].lower())
        else:missing.append(e)
    unmapped=[x for x in files if x["path"].lower() not in used]
    return {"generated_at":datetime.now(timezone.utc).isoformat(),"root":str(root),
      "summary":{"known":len(expected),"files_on_disk":len(files),"matched":len(matches),"missing":len(missing),
                 "unmapped":len(unmapped),"ambiguous":len(amb),"partial":len(partials)},
      "matches":matches,"missing":missing,"unmapped":unmapped,"ambiguous":amb,"partials":partials}
def persist(root,state):
    p=Path(root)/"_library";p.mkdir(parents=True,exist_ok=True)
    (p/"reconciled_state.json").write_text(json.dumps(state,indent=2,ensure_ascii=False),encoding="utf-8")
def load_state(root):return load_json(Path(root)/"_library"/"reconciled_state.json",{})
