from __future__ import annotations
import html,json,re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse,unquote,quote
import yaml
from library_paths import title,year,category,archive_path

SCHEMA_VERSION="1.1"; VERSION="2.1.4"

def image_for(sp):
    for k in ("icon","image","logo","thumbnail"):
        v=sp.get(k)
        if isinstance(v,str) and v.startswith(("http://","https://")):return v
    return None

def _old_map(root):
    p=Path(root)/"catalogue"/"library.json"
    try:
        old=json.loads(p.read_text(encoding="utf-8"))
    except Exception:return {},[]
    m={}
    for purchase in old.get("purchases",[]):
        for product in purchase.get("products",[]):
            for f in product.get("files",[]):
                key=(str(purchase.get("id")),str(f.get("file_id") or ""),str(f.get("filename") or ""))
                m[key]=f
    return m,old.get("purchases",[])

def _status(root):
    p=Path(root)/"_library"/"file_status.json"
    try:return json.loads(p.read_text(encoding="utf-8"))
    except Exception:return {}

def reconcile_catalogue(details,archive_root):
    root=Path(archive_root);oldmap,oldpurchases=_old_map(root);statuses=_status(root)
    purchases=[];seen_purchase=set();pc=fc=0
    for o in details.values():
        products=[];pid=str(o.get("gamekey"));seen_purchase.add(pid)
        for pi,sp in enumerate(o.get("subproducts") or []):
            pn=sp.get("human_name") or sp.get("machine_name") or f"Product {pi+1}";fs=[]
            for gi,g in enumerate(sp.get("downloads") or []):
                platform=g.get("platform") or g.get("machine_name") or "Files"
                for fi,d in enumerate(g.get("download_struct") or []):
                    u=(d.get("url") or {}).get("web")
                    if not u:continue
                    fid=f"{pi}:{gi}:{fi}";fn=Path(unquote(urlparse(u).path)).name or "download"
                    ff={"product":pn,"platform":platform,"filename":fn}
                    dest=archive_path(root,o,ff)
                    try:local=dest.relative_to(root).as_posix()
                    except Exception:local=str(dest)
                    st=statuses.get(f"{pid}|{fid}",{})
                    old=oldmap.get((pid,fid,fn),{})
                    exists=dest.exists()
                    status=st.get("status") or ("downloaded" if exists else ("missing" if old.get("downloaded") else "new"))
                    fs.append({"file_id":fid,"format":d.get("name") or Path(fn).suffix.lstrip(".") or "file",
                      "platform":platform,"filename":fn,"size_bytes":d.get("file_size"),"human_size":d.get("human_size"),
                      "sha1":d.get("sha1"),"md5":d.get("md5"),"source_url":u,"local_path":local,
                      "downloaded":exists,"status":status,
                      "checksum_algorithm":st.get("checksum_algorithm"),"expected_checksum":st.get("expected_checksum"),
                      "actual_checksum":st.get("actual_checksum"),"last_checked":st.get("updated_at")});fc+=1
            products.append({"title":pn,"machine_name":sp.get("machine_name"),"image":image_for(sp),"files":fs});pc+=1
        purchases.append({"id":pid,"title":title(o),"purchase_date":o.get("created"),"category":category(o),"year":year(o),"products":products})
    # Preserve historical catalogue entries no longer returned by the current API.
    for op in oldpurchases:
        if str(op.get("id")) not in seen_purchase:
            cp=json.loads(json.dumps(op));cp["historical_only"]=True
            for prod in cp.get("products",[]):
                for f in prod.get("files",[]):
                    lp=f.get("local_path");exists=bool(lp and (root/lp).exists())
                    f["downloaded"]=exists;f["status"]="historical" if exists else "historical_missing";fc+=1
                pc+=1
            purchases.append(cp)
    purchases.sort(key=lambda x:str(x.get("purchase_date") or ""),reverse=True)
    return {"schema":"humble-library-catalogue","schema_version":SCHEMA_VERSION,
      "generated_at":datetime.now(timezone.utc).isoformat(),
      "generator":{"name":"Humble Library Manager","version":VERSION,"original_creator":"Arun Sutharshan","website":"https://www.sutharshan.co.uk"},
      "source":"Humble Bundle","statistics":{"purchases":len(purchases),"products":pc,"files":fc},"purchases":purchases}

CSS="""body{font:15px system-ui;margin:0;background:#0b1020;color:#eef3ff}main{max-width:1180px;margin:auto;padding:28px}a{color:#82d8ff}.card{background:#151d33;border:1px solid #2d395b;border-radius:15px;padding:16px;margin:12px 0}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px}.muted{color:#9ba8c8}.badge{background:#293653;border-radius:20px;padding:4px 8px;font-size:12px}input,select{background:#0b1327;color:#fff;border:1px solid #394566;border-radius:9px;padding:10px}.files{width:100%;border-collapse:collapse}.files td,.files th{text-align:left;border-bottom:1px solid #29334e;padding:8px}.cover{max-width:120px;max-height:150px;border-radius:8px}.ok{color:#62e2c0}.warn{color:#ffcf70}footer{margin-top:30px;padding:20px 0;color:#9ba8c8;border-top:1px solid #29334e;font-size:13px}footer a{color:#b7c8ff}"""

def footer():
    return """<footer>Humble Library Manager v2.1.4 · Originally created by Arun Sutharshan · <a href='https://www.sutharshan.co.uk'>sutharshan.co.uk</a> · Community Open-Source Project · MIT License<br>Independent project — not affiliated with or endorsed by Humble Bundle.</footer>"""

def export_catalogue(details,archive_root):
    root=Path(archive_root);cat=root/"catalogue";pages=cat/"purchases";assets=cat/"assets"
    pages.mkdir(parents=True,exist_ok=True);assets.mkdir(parents=True,exist_ok=True)
    model=reconcile_catalogue(details,root)
    (cat/"library.json").write_text(json.dumps(model,indent=2,ensure_ascii=False),encoding="utf-8")
    (cat/"library.yml").write_text(yaml.safe_dump(model,sort_keys=False,allow_unicode=True),encoding="utf-8")
    (assets/"catalogue.css").write_text(CSS,encoding="utf-8")
    cards=[]
    for p in model["purchases"]:
        slug=re.sub(r"[^A-Za-z0-9._-]+","-",p["title"]).strip("-")[:80]+"-"+str(p["id"])[:10]
        count=sum(len(x["files"]) for x in p["products"])
        local=sum(1 for x in p["products"] for f in x["files"] if f.get("downloaded"))
        cards.append(f"<article class='card item' data-title='{html.escape(p['title'].lower())}' data-cat='{html.escape(p['category'])}'><span class='badge'>{html.escape(p['category'])}</span><h3><a href='catalogue/purchases/{slug}.html'>{html.escape(p['title'])}</a></h3><div class='muted'>{html.escape(str(p.get('purchase_date') or ''))} · {local}/{count} local files</div></article>")
        blocks=[]
        for prod in p["products"]:
            img=f"<img class='cover' src='{html.escape(prod['image'])}' alt=''>" if prod.get("image") else ""
            rows=[]
            for f in prod["files"]:
                # purchase page is root/catalogue/purchases, local archive is two levels up.
                link=f"<a href='../../{quote(f['local_path'])}'>Open local</a>" if f.get("downloaded") else ""
                cls="warn" if "mismatch" in str(f.get("status")) or "missing" in str(f.get("status")) else "ok"
                rows.append(f"<tr><td>{html.escape(str(f['platform']))}</td><td>{html.escape(str(f['format']))}</td><td>{html.escape(f['filename'])}</td><td>{html.escape(str(f.get('human_size') or f.get('size_bytes') or ''))}</td><td class='{cls}'>{html.escape(str(f.get('status') or ''))}</td><td>{link}</td></tr>")
            blocks.append(f"<section class='card'>{img}<h2>{html.escape(prod['title'])}</h2><table class='files'><tr><th>Platform</th><th>Type</th><th>File</th><th>Size</th><th>Status</th><th>Link</th></tr>{''.join(rows)}</table></section>")
        page=f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><link rel='stylesheet' href='../assets/catalogue.css'><main><p><a href='../../index.html'>← Library</a></p><h1>{html.escape(p['title'])}</h1><p class='muted'>Purchased: {html.escape(str(p.get('purchase_date') or ''))} · Category: {html.escape(p['category'])}</p>{''.join(blocks)}{footer()}</main>"
        (pages/f"{slug}.html").write_text(page,encoding="utf-8")
    cats="".join(f"<option>{html.escape(x)}</option>" for x in sorted(set(p["category"] for p in model["purchases"])))
    idx=f"""<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Humble Library Catalogue</title><link rel='stylesheet' href='catalogue/assets/catalogue.css'><main><h1>Humble Library Catalogue</h1><p class='muted'>{model['statistics']['purchases']} purchases · {model['statistics']['products']} products · {model['statistics']['files']} files</p><input id='q' placeholder='Search purchases…'> <select id='cat'><option value=''>All categories</option>{cats}</select><div class='grid'>{''.join(cards)}</div><script>const q=document.querySelector('#q'),c=document.querySelector('#cat');function f(){{document.querySelectorAll('.item').forEach(x=>x.style.display=(!q.value||x.dataset.title.includes(q.value.toLowerCase()))&&(!c.value||x.dataset.cat===c.value)?'block':'none')}}q.oninput=f;c.onchange=f;</script>{footer()}</main>"""
    (root/"index.html").write_text(idx,encoding="utf-8")
    return model
