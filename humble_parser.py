from pathlib import Path
from urllib.parse import urlparse, unquote

def _web_url(d):
    u=d.get("url")
    if isinstance(u,dict): return u.get("web") or u.get("url")
    if isinstance(u,str): return u
    return d.get("web") or d.get("download_url")

def _groups(node, inherited="Files", trail="root"):
    """Yield download_struct groups found anywhere below a Humble subproduct."""
    if isinstance(node,dict):
        platform=node.get("platform") or node.get("machine_name") or inherited or "Files"
        ds=node.get("download_struct")
        if isinstance(ds,list):
            yield platform, ds, trail
        for k,v in node.items():
            if k=="download_struct": continue
            if isinstance(v,(dict,list)):
                yield from _groups(v, platform, f"{trail}.{k}")
    elif isinstance(node,list):
        for i,v in enumerate(node):
            yield from _groups(v,inherited,f"{trail}[{i}]")

def parse_order_files(order):
    out=[]; seen=set()
    subs=order.get("subproducts") or []
    for pi,sp in enumerate(subs):
        pn=sp.get("human_name") or sp.get("machine_name") or f"Product {pi+1}"
        gi=0
        for platform,struct,trail in _groups(sp, "Files", f"subproducts[{pi}]"):
            for fi,d in enumerate(struct):
                if not isinstance(d,dict): continue
                u=_web_url(d)
                if not u: continue
                fn=Path(unquote(urlparse(u).path)).name or d.get("filename") or f"download_{fi+1}"
                sig=(pn,platform,fn,u)
                if sig in seen: continue
                seen.add(sig)
                out.append({
                    "id":f"{pi}:{gi}:{fi}",
                    "product":pn,"platform":platform,
                    "format":d.get("name") or Path(fn).suffix.lstrip(".") or "file",
                    "filename":fn,"url":u,
                    "size":d.get("file_size") or d.get("size"),
                    "human_size":d.get("human_size"),
                    "sha1":d.get("sha1"),"md5":d.get("md5"),
                    "metadata_path":trail
                })
            gi+=1
    return out

def order_diagnostics(order):
    subs=order.get("subproducts") or []
    groups=0; structs=0; url_files=0
    paths=[]
    for pi,sp in enumerate(subs):
        for platform,struct,trail in _groups(sp,"Files",f"subproducts[{pi}]"):
            groups+=1;structs+=len(struct);paths.append(trail)
            url_files+=sum(1 for d in struct if isinstance(d,dict) and _web_url(d))
    parsed=parse_order_files(order)
    return {
        "subproducts":len(subs),
        "download_groups":groups,
        "download_struct_entries":structs,
        "entries_with_web_url":url_files,
        "parsed_files":len(parsed),
        "metadata_paths":paths[:25],
        "needs_investigation":len(parsed)==0,
        "reason":("No downloadable file URL was discovered in the returned purchase metadata."
                  if len(parsed)==0 else None)
    }
