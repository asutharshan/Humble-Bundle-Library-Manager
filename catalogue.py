from __future__ import annotations
import html, json, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, unquote, quote
import yaml

SCHEMA_VERSION="1.0"
VERSION="2.1.1"

def safe(s):
    s=re.sub(r'[<>:"/\\|?*\x00-\x1f]',"_",(s or "Unknown").strip())
    return re.sub(r"\s+"," ",s).strip(" .") or "Unknown"

def title(o):
    p=o.get("product") or {}
    return p.get("human_name") or p.get("machine_name") or "Humble Purchase"

def year(o):
    m=re.search(r"(?:19|20)\d{2}",str(o.get("created") or ""))
    return m.group(0) if m else "Unknown Year"

def category(o):
    vals=[]; p=o.get("product") or {}
    vals += [str(p.get(k,"")) for k in ("human_name","machine_name","category")]
    for sp in o.get("subproducts") or []:
        vals += [str(sp.get(k,"")) for k in ("human_name","machine_name")]
        vals += [str(d.get("platform","")) for d in sp.get("downloads") or []]
    t=" ".join(vals).lower()
    if any(x in t for x in ("ebook","book bundle","books bundle")): return "Books"
    if any(x in t for x in ("audio","music bundle")): return "Audio"
    if "software" in t: return "Software"
    if any(x in t for x in ("windows","linux","mac","android")): return "Games & Software"
    return "Other"

def image_for(sp):
    for k in ("icon","image","logo","thumbnail"):
        v=sp.get(k)
        if isinstance(v,str) and v.startswith(("http://","https://")): return v
    return None

def build(details, archive_root):
    archive_root=Path(archive_root); purchases=[]; pc=fc=0
    for o in details.values():
        products=[]
        for pi,sp in enumerate(o.get("subproducts") or []):
            pn=sp.get("human_name") or sp.get("machine_name") or f"Product {pi+1}"
            fs=[]
            for g in sp.get("downloads") or []:
                platform=g.get("platform") or g.get("machine_name") or "Files"
                for d in g.get("download_struct") or []:
                    u=(d.get("url") or {}).get("web")
                    if not u: continue
                    fn=Path(unquote(urlparse(u).path)).name or "download"
                    local=Path(safe(category(o),36))/safe(year(o),20)/safe(title(o),58)/safe(pn,58)/safe(str(platform),28)/safe(fn,90)
                    fs.append({
                        "format":d.get("name") or Path(fn).suffix.lstrip(".") or "file",
                        "platform":platform,"filename":fn,"size_bytes":d.get("file_size"),
                        "human_size":d.get("human_size"),"sha1":d.get("sha1"),"md5":d.get("md5"),
                        "source_url":u,"local_path":local.as_posix(),
                        "downloaded":(archive_root/local).exists()
                    }); fc+=1
            products.append({"title":pn,"machine_name":sp.get("machine_name"),"image":image_for(sp),"files":fs}); pc+=1
        purchases.append({"id":o.get("gamekey"),"title":title(o),"purchase_date":o.get("created"),
                          "category":category(o),"year":year(o),"products":products})
    purchases.sort(key=lambda x:str(x.get("purchase_date") or ""),reverse=True)
    return {
      "schema":"humble-library-catalogue","schema_version":SCHEMA_VERSION,
      "generated_at":datetime.now(timezone.utc).isoformat(),
      "generator":{"name":"Humble Library Manager","version":VERSION,
                   "original_creator":"Arun Sutharshan","website":"https://www.sutharshan.co.uk"},
      "source":"Humble Bundle","statistics":{"purchases":len(purchases),"products":pc,"files":fc},
      "purchases":purchases
    }

CSS="""body{font:15px system-ui;margin:0;background:#0b1020;color:#eef3ff}main{max-width:1180px;margin:auto;padding:28px}a{color:#82d8ff}.card{background:#151d33;border:1px solid #2d395b;border-radius:15px;padding:16px;margin:12px 0}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px}.muted{color:#9ba8c8}.badge{background:#293653;border-radius:20px;padding:4px 8px;font-size:12px}input,select{background:#0b1327;color:#fff;border:1px solid #394566;border-radius:9px;padding:10px}.files{width:100%;border-collapse:collapse}.files td,.files th{text-align:left;border-bottom:1px solid #29334e;padding:8px}.cover{max-width:120px;max-height:150px;border-radius:8px}"""

def export_catalogue(details, archive_root):
    root=Path(archive_root); cat=root/"catalogue"; pages=cat/"purchases"; assets=cat/"assets"
    pages.mkdir(parents=True,exist_ok=True); assets.mkdir(parents=True,exist_ok=True)
    model=build(details,root)
    (cat/"library.json").write_text(json.dumps(model,indent=2,ensure_ascii=False),encoding="utf-8")
    (cat/"library.yml").write_text(yaml.safe_dump(model,sort_keys=False,allow_unicode=True),encoding="utf-8")
    (assets/"catalogue.css").write_text(CSS,encoding="utf-8")
    cards=[]
    for p in model["purchases"]:
        slug=re.sub(r"[^A-Za-z0-9._-]+","-",p["title"]).strip("-")[:80]+"-"+str(p["id"])[:10]
        count=sum(len(x["files"]) for x in p["products"])
        cards.append(f"<article class='card item' data-title='{html.escape(p['title'].lower())}' data-cat='{html.escape(p['category'])}'><span class='badge'>{html.escape(p['category'])}</span><h3><a href='catalogue/purchases/{slug}.html'>{html.escape(p['title'])}</a></h3><div class='muted'>{html.escape(str(p['purchase_date'] or ''))} · {count} files</div></article>")
        blocks=[]
        for prod in p["products"]:
            img=f"<img class='cover' src='{html.escape(prod['image'])}' alt=''>" if prod.get("image") else ""
            rows=[]
            for f in prod["files"]:
                link=f"<a href='../../{quote(f['local_path'])}'>Open local</a>" if f["downloaded"] else ""
                rows.append(f"<tr><td>{html.escape(str(f['platform']))}</td><td>{html.escape(str(f['format']))}</td><td>{html.escape(f['filename'])}</td><td>{html.escape(str(f.get('human_size') or f.get('size_bytes') or ''))}</td><td>{'Downloaded' if f['downloaded'] else 'Not downloaded'}</td><td>{link}</td></tr>")
            blocks.append(f"<section class='card'>{img}<h2>{html.escape(prod['title'])}</h2><table class='files'><tr><th>Platform</th><th>Type</th><th>File</th><th>Size</th><th>Status</th><th>Link</th></tr>{''.join(rows)}</table></section>")
        page=f"<!doctype html><meta charset='utf-8'><link rel='stylesheet' href='../assets/catalogue.css'><main><p><a href='../../index.html'>← Library</a></p><h1>{html.escape(p['title'])}</h1><p class='muted'>Purchased: {html.escape(str(p['purchase_date'] or ''))} · Category: {html.escape(p['category'])}</p>{''.join(blocks)}</main>"
        (pages/f"{slug}.html").write_text(page,encoding="utf-8")
    cats="".join(f"<option>{html.escape(x)}</option>" for x in sorted(set(p["category"] for p in model["purchases"])))
    idx=f"""<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Humble Library Catalogue</title><link rel='stylesheet' href='catalogue/assets/catalogue.css'><main><h1>Humble Library Catalogue</h1><p class='muted'>{model['statistics']['purchases']} purchases · {model['statistics']['products']} products · {model['statistics']['files']} files</p><input id='q' placeholder='Search purchases…'> <select id='cat'><option value=''>All categories</option>{cats}</select><div class='grid'>{''.join(cards)}</div><script>const q=document.querySelector('#q'),c=document.querySelector('#cat');function f(){{document.querySelectorAll('.item').forEach(x=>x.style.display=(!q.value||x.dataset.title.includes(q.value.toLowerCase()))&&(!c.value||x.dataset.cat===c.value)?'block':'none')}}q.oninput=f;c.onchange=f;</script></main>"""
    (root/"index.html").write_text(idx,encoding="utf-8")
    return model
