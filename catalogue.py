from __future__ import annotations
import html,json,re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse,unquote,quote
import yaml
from library_paths import title,year,category,archive_path

SCHEMA_VERSION="1.2"; VERSION="2.1.6"

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
                    oldlp=old.get("local_path"); olddest=(root/oldlp) if oldlp else None; dest=olddest if olddest and olddest.exists() else archive_path(root,o,ff)
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

GENERIC_BOOK_SVG="""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 320"><rect width="240" height="320" rx="18" fill="#293b70"/><path d="M55 55h125a15 15 0 0 1 15 15v190H75a20 20 0 0 0-20 20V55z" fill="#f3f7ff"/><path d="M82 105h82M82 135h82M82 165h55" stroke="#3b5287" stroke-width="10" stroke-linecap="round"/><text x="122" y="220" text-anchor="middle" font-family="sans-serif" font-size="25" fill="#3b5287">BOOKS</text></svg>"""

CSS="""body{font:15px system-ui;margin:0;background:#0b1020;color:#eef3ff}main{max-width:1180px;margin:auto;padding:28px}a{color:#82d8ff}.card{background:#151d33;border:1px solid #2d395b;border-radius:15px;padding:16px;margin:12px 0}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px}.muted{color:#9ba8c8}.badge{background:#293653;border-radius:20px;padding:4px 8px;font-size:12px}input,select{background:#0b1327;color:#fff;border:1px solid #394566;border-radius:9px;padding:10px}.files{width:100%;border-collapse:collapse}.files td,.files th{text-align:left;border-bottom:1px solid #29334e;padding:8px}.cover{max-width:120px;max-height:150px;border-radius:8px}.ok{color:#62e2c0}.warn{color:#ffcf70}.covers{display:flex;gap:7px;height:105px;margin:0 0 12px}.covers img{height:100px;max-width:78px;object-fit:cover;border-radius:7px}.ok{color:#62e2c0}.warn{color:#ffcf70}.bad{color:#ff8f9c}footer{margin-top:24px;padding:12px 0;color:#8995b1;border-top:1px solid #29334e;font-size:10px;line-height:1.45}footer a{color:#b7c8ff}"""

def footer():
    return """<footer>Humble Library Manager v2.1.4 · Originally created by Arun Sutharshan · <a href='https://www.sutharshan.co.uk'>sutharshan.co.uk</a> · Community Open-Source Project · MIT License<br>Independent project — not affiliated with or endorsed by Humble Bundle.</footer>"""

def export_catalogue(details,archive_root):
    root=Path(archive_root);cat=root/"catalogue";pages=cat/"purchases";assets=cat/"assets"
    pages.mkdir(parents=True,exist_ok=True);assets.mkdir(parents=True,exist_ok=True)
    model=reconcile_catalogue(details,root)
    (cat/"library.json").write_text(json.dumps(model,indent=2,ensure_ascii=False),encoding="utf-8")
    (cat/"library.yml").write_text(yaml.safe_dump(model,sort_keys=False,allow_unicode=True),encoding="utf-8")
    (assets/"catalogue.css").write_text(CSS,encoding="utf-8");(assets/"generic-book.svg").write_text(GENERIC_BOOK_SVG,encoding="utf-8")
    cards=[]
    for p in model["purchases"]:
        slug=re.sub(r"[^A-Za-z0-9._-]+","-",p["title"]).strip("-")[:80]+"-"+str(p["id"])[:10]
        count=sum(len(x["files"]) for x in p["products"])
        local=sum(1 for x in p["products"] for f in x["files"] if f.get("downloaded"))
        if count==0: stat="nofiles"; label="No files discovered"; cls="warn"
        elif local==count: stat="complete"; label=f"{local}/{count} local files"; cls="ok"
        elif local==0: stat="missing"; label=f"0/{count} local files"; cls="bad"
        else: stat="partial"; label=f"{local}/{count} local files"; cls="warn"
        imgs=[]
        for prod in p["products"]:
            if prod.get("image") and prod["image"] not in imgs: imgs.append(prod["image"])
            if len(imgs)>=4: break
        covers="".join(f"<img src='{html.escape(x)}' alt=''>" for x in imgs) if imgs else "<img src='catalogue/assets/generic-book.svg' alt='Books'>"
        searchable=" ".join([p["title"]]+[x.get("title","") for x in p["products"]]+[f.get("filename","") for x in p["products"] for f in x.get("files",[])])
        cards.append(f"<article class='card item' data-title='{html.escape(searchable.lower())}' data-cat='{html.escape(p['category'])}' data-status='{stat}'><div class='covers'>{covers}</div><span class='badge'>{html.escape(p['category'])}</span><h3><a href='catalogue/purchases/{slug}.html'>{html.escape(p['title'])}</a></h3><div class='muted'>{html.escape(str(p.get('purchase_date') or ''))}</div><div class='{cls}'>{label}</div></article>")
        blocks=[]
        for prod in p["products"]:
            img=f"<img class='cover' src='{html.escape(prod['image'])}' alt=''>" if prod.get("image") else ""
            rows=[]
            for f in prod["files"]:
                # purchase page is root/catalogue/purchases, local archive is two levels up.
                link=f"<a href='../../{quote(f['local_path'])}'>Open local</a>" if f.get("downloaded") else ""
                cls="warn" if "mismatch" in str(f.get("status")) or "missing" in str(f.get("status")) else "ok"
                rows.append(f"<tr><td>{html.escape(str(f['platform']))}</td><td>{html.escape(str(f['format']))}</td><td>{html.escape(f['filename'])}</td><td>{html.escape(str(f.get('human_size') or f.get('size_bytes') or ''))}</td><td class='{cls}'>{html.escape(str(f.get('status') or ''))}</td><td>{link}</td></tr>")
            body=f"<table class='files'><tr><th>Platform</th><th>Type</th><th>File</th><th>Size</th><th>Status</th><th>Link</th></tr>{''.join(rows)}</table>" if rows else "<p class='warn'>No downloadable files were discovered for this product in the available metadata.</p>"
        blocks.append(f"<section class='card'>{img}<h2>{html.escape(prod['title'])}</h2>{body}</section>")
        page=f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><link rel='stylesheet' href='../assets/catalogue.css'><main><p><a href='../../index.html'>← Library</a></p><h1>{html.escape(p['title'])}</h1><p class='muted'>Purchased: {html.escape(str(p.get('purchase_date') or ''))} · Category: {html.escape(p['category'])}</p>{''.join(blocks)}{footer()}</main>"
        (pages/f"{slug}.html").write_text(page,encoding="utf-8")
    cats="".join(f"<option>{html.escape(x)}</option>" for x in sorted(set(p["category"] for p in model["purchases"])))
    idx=f"""<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Humble Library Catalogue</title><link rel='stylesheet' href='catalogue/assets/catalogue.css'><main><h1>Humble Library Catalogue</h1><p class='muted'>{model['statistics']['purchases']} purchases · {model['statistics']['products']} products · {model['statistics']['files']} files</p><input id='q' placeholder='Search purchases…'> <select id='cat'><option value=''>All categories</option>{cats}</select> <select id='status'><option value=''>All statuses</option><option value='complete'>Complete</option><option value='partial'>Partial</option><option value='missing'>Missing locally</option><option value='nofiles'>No files discovered</option></select><div class='grid'>{''.join(cards)}</div><script>const q=document.querySelector('#q'),c=document.querySelector('#cat'),s=document.querySelector('#status');function f(){{document.querySelectorAll('.item').forEach(x=>x.style.display=(!q.value||x.dataset.title.includes(q.value.toLowerCase()))&&(!c.value||x.dataset.cat===c.value)&&(!s.value||x.dataset.status===s.value)?'block':'none')}}q.oninput=f;c.onchange=f;s.onchange=f;</script>{footer()}</main>"""
    (root/"index.html").write_text(idx,encoding="utf-8")
    return model

def render_existing_catalogue(archive_root):
    root=Path(archive_root);p=root/"catalogue"/"library.json"
    try:model=json.loads(p.read_text(encoding="utf-8"))
    except Exception:raise RuntimeError("No existing catalogue/library.json found.")
    model["generated_at"]=datetime.now(timezone.utc).isoformat()
    model.setdefault("generator",{})["version"]=VERSION
    model["statistics"]={"purchases":len(model.get("purchases",[])),"products":sum(len(x.get("products",[])) for x in model.get("purchases",[])),"files":sum(len(y.get("files",[])) for x in model.get("purchases",[]) for y in x.get("products",[]))}
    # Reuse exporter HTML generation by temporarily rendering from this model via a small local renderer.
    cat=root/"catalogue";pages=cat/"purchases";assets=cat/"assets";pages.mkdir(parents=True,exist_ok=True);assets.mkdir(parents=True,exist_ok=True)
    (assets/"catalogue.css").write_text(CSS,encoding="utf-8");(assets/"generic-book.svg").write_text(GENERIC_BOOK_SVG,encoding="utf-8")
    cards=[]
    for pur in model.get("purchases",[]):
        slug=re.sub(r"[^A-Za-z0-9._-]+","-",pur["title"]).strip("-")[:80]+"-"+str(pur["id"])[:10]
        n=sum(len(x.get("files",[])) for x in pur.get("products",[]));local=sum(1 for x in pur.get("products",[]) for f in x.get("files",[]) if f.get("downloaded"))
        if n==0:stat,label,cls="nofiles","No files discovered","warn"
        elif local==n:stat,label,cls="complete",f"{local}/{n} local files","ok"
        elif local==0:stat,label,cls="missing",f"0/{n} local files","bad"
        else:stat,label,cls="partial",f"{local}/{n} local files","warn"
        imgs=[x["image"] for x in pur.get("products",[]) if x.get("image")][:4]
        covers="".join(f"<img src='{html.escape(x)}' alt=''>" for x in imgs) if imgs else "<img src='catalogue/assets/generic-book.svg' alt='Books'>"
        search=" ".join([pur["title"]]+[x.get("title","") for x in pur.get("products",[])]+[f.get("filename","") for x in pur.get("products",[]) for f in x.get("files",[])])
        cards.append(f"<article class='card item' data-title='{html.escape(search.lower())}' data-cat='{html.escape(pur.get('category','Other'))}' data-status='{stat}'><div class='covers'>{covers}</div><span class='badge'>{html.escape(pur.get('category','Other'))}</span><h3><a href='catalogue/purchases/{slug}.html'>{html.escape(pur['title'])}</a></h3><div class='muted'>{html.escape(str(pur.get('purchase_date') or ''))}</div><div class='{cls}'>{label}</div></article>")
        blocks=[]
        for prod in pur.get("products",[]):
            rows=[]
            for f in prod.get("files",[]):
                link=f"<a href='../../{quote(f['local_path'])}'>Open local</a>" if f.get("downloaded") else ""
                st=str(f.get("status") or "");cl="bad" if "missing" in st else ("warn" if "mismatch" in st else "ok")
                rows.append(f"<tr><td>{html.escape(str(f.get('platform','')))}</td><td>{html.escape(str(f.get('format','')))}</td><td>{html.escape(str(f.get('filename','')))}</td><td>{html.escape(str(f.get('human_size') or f.get('size_bytes') or ''))}</td><td class='{cl}'>{html.escape(st)}</td><td>{link}</td></tr>")
            img=f"<img class='cover' src='{html.escape(prod['image'])}' alt=''>" if prod.get("image") else "<img class='cover' src='../assets/generic-book.svg' alt=''>"
            body=f"<table class='files'><tr><th>Platform</th><th>Type</th><th>File</th><th>Size</th><th>Status</th><th>Link</th></tr>{''.join(rows)}</table>" if rows else "<p class='warn'>No downloadable files were discovered for this product in the available metadata.</p>"
            blocks.append(f"<section class='card'>{img}<h2>{html.escape(prod.get('title','Product'))}</h2>{body}</section>")
        (pages/f"{slug}.html").write_text(f"<!doctype html><meta charset='utf-8'><link rel='stylesheet' href='../assets/catalogue.css'><main><p><a href='../../index.html'>← Library</a></p><h1>{html.escape(pur['title'])}</h1>{''.join(blocks) if blocks else '<section class=card><p class=warn>No product/file metadata is currently available for this purchase.</p></section>'}{footer()}</main>",encoding="utf-8")
    cats="".join(f"<option>{html.escape(x)}</option>" for x in sorted(set(x.get("category","Other") for x in model.get("purchases",[]))))
    script="""<script>const q=document.querySelector('#q'),c=document.querySelector('#cat'),s=document.querySelector('#status');function f(){document.querySelectorAll('.item').forEach(x=>x.style.display=(!q.value||x.dataset.title.includes(q.value.toLowerCase()))&&(!c.value||x.dataset.cat===c.value)&&(!s.value||x.dataset.status===s.value)?'block':'none')}q.oninput=f;c.onchange=f;s.onchange=f;</script>"""
    (root/"index.html").write_text(f"<!doctype html><meta charset='utf-8'><title>Humble Library Catalogue</title><link rel='stylesheet' href='catalogue/assets/catalogue.css'><main><h1>Humble Library Catalogue</h1><p class='muted'>{model['statistics']['purchases']} purchases · {model['statistics']['files']} files</p><input id='q' placeholder='Search purchases, products and files…'> <select id='cat'><option value=''>All categories</option>{cats}</select> <select id='status'><option value=''>All statuses</option><option value='complete'>Complete</option><option value='partial'>Partial</option><option value='missing'>Missing locally</option><option value='nofiles'>No files discovered</option></select><div class='grid'>{''.join(cards)}</div>{script}{footer()}</main>",encoding="utf-8")
    p.write_text(json.dumps(model,indent=2,ensure_ascii=False),encoding="utf-8")
    try:(cat/"library.yml").write_text(yaml.safe_dump(model,sort_keys=False,allow_unicode=True),encoding="utf-8")
    except Exception:pass
    return model

# v2.1.6 compact catalogue renderer overrides
def _icon(fmt,filename=""):
    x=(str(fmt)+" "+str(filename)).lower()
    if "pdf" in x:return "📕"
    if "epub" in x:return "📘"
    if any(k in x for k in ("mobi","azw","kindle")):return "📗"
    if any(k in x for k in ("zip","rar","7z")):return "🗜️"
    if any(k in x for k in ("exe","msi","windows")):return "🪟"
    if any(k in x for k in ("dmg","pkg","mac")):return "🍎"
    if "apk" in x:return "🤖"
    if any(k in x for k in ("mp3","m4a","flac","wav","audio")):return "🎵"
    return "📄"
def _compact_render(model,root):
    root=Path(root);cat=root/"catalogue";pages=cat/"purchases";assets=cat/"assets";pages.mkdir(parents=True,exist_ok=True);assets.mkdir(parents=True,exist_ok=True)
    css="""body{font:14px system-ui;margin:0;background:#0b1020;color:#eef3ff}main{max-width:1180px;margin:auto;padding:22px}a{color:#73d3ff}.muted{color:#96a4c3}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.toolbar input,.toolbar select{background:#0d1529;color:#fff;border:1px solid #34415f;border-radius:7px;padding:8px}.list{border:1px solid #2c3856;border-radius:10px;overflow:hidden}.row{display:grid;grid-template-columns:70px 1fr 115px 110px;gap:14px;align-items:center;padding:10px 14px;border-bottom:1px solid #29344f}.row:last-child{border-bottom:0}.thumb{width:54px;height:72px;object-fit:cover;border-radius:5px;background:#273451}.title{font-size:15px;font-weight:650}.status{font-size:12px}.ok{color:#62e2c0}.warn{color:#ffcf70}.bad{color:#ff8f9c}.book{display:grid;grid-template-columns:74px 1fr;gap:14px;padding:12px 0;border-bottom:1px solid #29344f}.book img{width:64px;max-height:88px;object-fit:cover;border-radius:5px}.formats{display:flex;gap:7px;flex-wrap:wrap;margin-top:7px}.format{display:inline-flex;gap:5px;align-items:center;background:#202c47;border:1px solid #394969;border-radius:6px;padding:5px 8px;font-size:12px}.format a{text-decoration:none}.missing{opacity:.68}.pager{display:flex;gap:5px;justify-content:flex-end;margin:12px 0}.pager button{padding:6px 9px;background:#17223b;color:#fff;border:1px solid #3a4867;border-radius:5px}footer{margin-top:22px;padding:10px 0;color:#8995b1;border-top:1px solid #29334e;font-size:10px;line-height:1.45}footer a{color:#aab8d5}@media(max-width:700px){.row{grid-template-columns:52px 1fr}.row .date,.row .count{display:none}}"""
    (assets/"catalogue.css").write_text(css,encoding="utf-8")
    if 'GENERIC_BOOK_SVG' in globals():(assets/"generic-book.svg").write_text(GENERIC_BOOK_SVG,encoding="utf-8")
    rows=[]
    for pur in model.get("purchases",[]):
        slug=re.sub(r"[^A-Za-z0-9._-]+","-",pur["title"]).strip("-")[:80]+"-"+str(pur["id"])[:10]
        known=sum(len(x.get("files",[])) for x in pur.get("products",[]));local=sum(1 for x in pur.get("products",[]) for f in x.get("files",[]) if f.get("downloaded"))
        stat="nofiles" if known==0 else ("complete" if local==known else ("missing" if local==0 else "partial"))
        cls="ok" if stat=="complete" else ("bad" if stat=="missing" else "warn")
        label="No files discovered" if known==0 else f"{local}/{known} local"
        imgs=[x.get("image") for x in pur.get("products",[]) if x.get("image")];img=imgs[0] if imgs else "catalogue/assets/generic-book.svg"
        search=" ".join([pur["title"]]+[x.get("title","") for x in pur.get("products",[])]+[f.get("filename","") for x in pur.get("products",[]) for f in x.get("files",[])])
        rows.append(f"<div class='row item' data-search='{html.escape(search.lower())}' data-cat='{html.escape(pur.get('category','Other'))}' data-status='{stat}'><img class='thumb' src='{html.escape(img)}'><div><a class='title' href='catalogue/purchases/{slug}.html'>{html.escape(pur['title'])}</a><div class='muted'>{html.escape(pur.get('category','Other'))}</div></div><div class='date muted'>{html.escape(str(pur.get('purchase_date') or '')[:10])}</div><div class='count {cls}'>{label}</div></div>")
        books=[]
        for prod in pur.get("products",[]):
            formats=[]
            for f in prod.get("files",[]):
                localf=f.get("downloaded");link=f"../../{quote(f.get('local_path',''))}" if localf else ""
                txt=f"{_icon(f.get('format'),f.get('filename'))} {html.escape(str(f.get('format') or Path(str(f.get('filename',''))).suffix.lstrip('.').upper() or 'FILE'))}"
                size=html.escape(str(f.get("human_size") or f.get("size_bytes") or ""))
                formats.append(f"<span class='format {' ' if localf else 'missing'}'>{('<a href='+repr(link)+'>'+txt+'</a>') if localf else txt} <span class='muted'>{size}</span></span>")
            img=prod.get("image") or "../assets/generic-book.svg"
            books.append(f"<div class='book'><img src='{html.escape(img)}'><div><div class='title'>{html.escape(prod.get('title','Product'))}</div><div class='formats'>{''.join(formats) if formats else '<span class=warn>No downloadable files discovered</span>'}</div></div></div>")
        (pages/f"{slug}.html").write_text(f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><link rel='stylesheet' href='../assets/catalogue.css'><main><p><a href='../../index.html'>← Library</a></p><h1>{html.escape(pur['title'])}</h1><p class='muted'>{html.escape(str(pur.get('purchase_date') or '')[:10])} · {html.escape(pur.get('category','Other'))} · {local}/{known} local</p>{''.join(books) if books else '<p class=warn>No product/file metadata is currently available.</p>'}{footer()}</main>",encoding="utf-8")
    cats="".join(f"<option>{html.escape(x)}</option>" for x in sorted(set(x.get("category","Other") for x in model.get("purchases",[]))))
    script="""<script>const q=document.querySelector('#q'),c=document.querySelector('#cat'),s=document.querySelector('#status'),ps=document.querySelector('#ps');let page=1;function f(){let a=[...document.querySelectorAll('.item')].filter(x=>(!q.value||x.dataset.search.includes(q.value.toLowerCase()))&&(!c.value||x.dataset.cat===c.value)&&(!s.value||x.dataset.status===s.value)),n=+ps.value,start=(page-1)*n;document.querySelectorAll('.item').forEach(x=>x.style.display='none');a.slice(start,start+n).forEach(x=>x.style.display='grid');document.querySelector('#page').textContent=`Page ${page} of ${Math.max(1,Math.ceil(a.length/n))}`)}function nav(d){page=Math.max(1,page+d);f()}q.oninput=()=>{page=1;f()};c.onchange=s.onchange=ps.onchange=()=>{page=1;f()};window.onload=f;</script>"""
    index=f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Humble Library Catalogue</title><link rel='stylesheet' href='catalogue/assets/catalogue.css'><main><h1>Humble Library Catalogue</h1><p class='muted'>{model.get('statistics',{}).get('purchases',0)} purchases · {model.get('statistics',{}).get('files',0)} known files</p><div class='toolbar'><input id='q' placeholder='Search purchases, books and files…'><select id='cat'><option value=''>All categories</option>{cats}</select><select id='status'><option value=''>All statuses</option><option value='complete'>Complete</option><option value='partial'>Partial</option><option value='missing'>Missing</option><option value='nofiles'>No files discovered</option></select><select id='ps'><option>25</option><option>50</option><option>100</option></select></div><div class='list'>{''.join(rows)}</div><div class='pager'><button onclick='nav(-1)'>‹</button><span id='page'></span><button onclick='nav(1)'>›</button></div>{script}{footer()}</main>"
    (root/"index.html").write_text(index,encoding="utf-8")
def render_existing_catalogue(archive_root):
    root=Path(archive_root);p=root/"catalogue/library.json"
    try:model=json.loads(p.read_text(encoding="utf-8"))
    except Exception:raise RuntimeError("No existing catalogue/library.json found.")
    model["generated_at"]=datetime.now(timezone.utc).isoformat();model.setdefault("generator",{})["version"]=VERSION
    model["statistics"]={"purchases":len(model.get("purchases",[])),"products":sum(len(x.get("products",[])) for x in model.get("purchases",[])),"files":sum(len(y.get("files",[])) for x in model.get("purchases",[]) for y in x.get("products",[]))}
    p.write_text(json.dumps(model,indent=2,ensure_ascii=False),encoding="utf-8")
    try:(root/"catalogue/library.yml").write_text(yaml.safe_dump(model,sort_keys=False,allow_unicode=True),encoding="utf-8")
    except Exception:pass
    _compact_render(model,root);return model

_original_export_catalogue=export_catalogue
def export_catalogue(details,archive_root):
    model=_original_export_catalogue(details,archive_root)
    _compact_render(model,archive_root)
    return model
