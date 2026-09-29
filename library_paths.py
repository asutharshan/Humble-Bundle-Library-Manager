from __future__ import annotations
import hashlib,re
from pathlib import Path

def safe(s,n=80):
    s=re.sub(r'[<>:"/\\|?*\x00-\x1f]',"_",(s or "Unknown").strip())
    s=re.sub(r"\s+"," ",s).strip(" .") or "Unknown"
    if len(s)<=n:return s
    digest=hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]
    keep=max(12,n-len(digest)-3)
    return s[:keep].rstrip(" ._-")+"__"+digest

def title(o):
    p=o.get("product") or {}
    return p.get("human_name") or p.get("machine_name") or "Humble Purchase"

def year(o):
    m=re.search(r"(?:19|20)\d{2}",str(o.get("created") or ""))
    return m.group(0) if m else "Unknown Year"

def category(o):
    vals=[];p=o.get("product") or {}
    vals += [str(p.get(k,"")) for k in ("human_name","machine_name","category")]
    for sp in o.get("subproducts") or []:
        vals += [str(sp.get(k,"")) for k in ("human_name","machine_name")]
        vals += [str(d.get("platform","")) for d in sp.get("downloads") or []]
    t=" ".join(vals).lower()
    if any(x in t for x in ("ebook","book bundle","books bundle")):return "Books"
    if any(x in t for x in ("audio","music bundle")):return "Audio"
    if "software" in t:return "Software"
    if any(x in t for x in ("windows","linux","mac","android")):return "Games & Software"
    return "Other"

def relative_archive_path(o,f):
    return Path(safe(category(o),36))/safe(year(o),20)/safe(title(o),58)/safe(f["product"],58)/safe(str(f["platform"]),28)/safe(f["filename"],90)

def archive_path(root,o,f,max_total=235):
    root=Path(root)
    parts=list(relative_archive_path(o,f).parts)
    dest=root.joinpath(*parts)
    try:total=len(str(dest.resolve()))
    except Exception:total=len(str(dest.absolute()))
    if total>max_total:
        over=total-max_total
        for idx,min_len in ((3,28),(2,28),(5,45),(0,20),(4,16)):
            if over<=0:break
            cur=parts[idx];target=max(min_len,len(cur)-over);short=safe(cur,target)
            over-=max(0,len(cur)-len(short));parts[idx]=short
        dest=root.joinpath(*parts)
    return dest
