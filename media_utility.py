import os, sys, json, re, queue, threading, subprocess, hashlib, time, shutil
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME='Media Utility'; VERSION='2.1'; APP_DATE='06 October 2026'; AUTHOR='Arun Sutharshan'
APP_DIR=Path(os.getenv('APPDATA', str(Path.home())))/'MediaUtility'; APP_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_FILE=APP_DIR/'download_history.json'; SETTINGS_FILE=APP_DIR/'settings.json'

def ensure_pip():
    try:
        subprocess.check_call([sys.executable,'-m','pip','--version'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); return True
    except Exception: pass
    try:
        subprocess.check_call([sys.executable,'-m','ensurepip','--upgrade']); return True
    except Exception: return False

def ensure_package(import_name,pip_name=None):
    try: __import__(import_name); return True
    except ImportError:
        if not ensure_pip(): return False
        try:
            subprocess.check_call([sys.executable,'-m','pip','install','--upgrade',pip_name or import_name]); __import__(import_name); return True
        except Exception: return False

if not ensure_package('yt_dlp','yt-dlp'): raise SystemExit('yt-dlp unavailable. Run INSTALL_AND_RUN.bat with a full Python installation.')
if not ensure_package('imageio_ffmpeg','imageio-ffmpeg'): raise SystemExit('imageio-ffmpeg unavailable. Run INSTALL_AND_RUN.bat.')
import yt_dlp, imageio_ffmpeg

def load_json(path,default):
    try: return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception: return default

def save_json(path,data):
    t=path.with_suffix(path.suffix+'.tmp'); t.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8'); t.replace(path)

def clean_links(text):
    out=[]; seen=set()
    for raw in text.replace(',','\n').splitlines():
        u=raw.strip()
        if u and u not in seen: seen.add(u); out.append(u)
    return out

def detect_platform(url):
    u=(url or '').lower()
    if 'youtube.com' in u or 'youtu.be' in u: return 'YouTube'
    if 'facebook.com' in u or 'fb.watch' in u or 'fb.com' in u: return 'Facebook'
    if 'tiktok.com' in u: return 'TikTok'
    return 'Auto'

def duration_text(seconds):
    try:
        seconds=int(seconds or 0); h,r=divmod(seconds,3600); m,s=divmod(r,60)
        return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'
    except Exception: return ''

def history_key(item,fmt):
    ext=item.get('extractor_key') or item.get('extractor') or item.get('platform') or 'source'
    mid=item.get('id') or item.get('url') or item.get('title') or 'unknown'
    return hashlib.sha256(f'{ext}|{mid}|{fmt.lower()}'.encode('utf-8','ignore')).hexdigest()

def ffmpeg_path():
    try: return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception: return None


def find_deno():
    """Return a usable Deno executable path when available."""
    candidates = []
    direct = shutil.which("deno")
    if direct:
        candidates.append(Path(direct))

    home = Path.home()
    local = Path(os.getenv("LOCALAPPDATA", home))
    candidates.extend([
        home / ".deno" / "bin" / "deno.exe",
        local / "Microsoft" / "WinGet" / "Links" / "deno.exe",
        local / "Programs" / "Deno" / "deno.exe",
    ])

    for p in candidates:
        try:
            if p.exists():
                return str(p)
        except Exception:
            pass
    return None

def deno_version(path=None):
    path = path or find_deno()
    if not path:
        return None
    try:
        r = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=8)
        first = (r.stdout or r.stderr or "").splitlines()
        return first[0].strip() if first else "Deno available"
    except Exception:
        return None

def ytdlp_version():
    try:
        from yt_dlp.version import __version__
        return __version__
    except Exception:
        return "unknown"

def youtube_error_kind(message):
    text = str(message or "").lower()
    if "sign in to confirm you" in text and "not a bot" in text:
        return "auth"
    if "cookies-from-browser" in text or "authentication" in text and "youtube" in text:
        return "auth"
    if "no supported javascript runtime" in text:
        return "runtime"
    return None

class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(f'{APP_NAME} v{VERSION}'); self.geometry('1240x840'); self.minsize(1050,720); self.configure(bg='#0d1422')
        self.events=queue.Queue(); self.stop_requested=False; self.pause_requested=False
        self.history=load_json(HISTORY_FILE,{}); self.settings=load_json(SETTINGS_FILE,{})
        self.destination=tk.StringVar(value=self.settings.get('destination',str(Path.home()/'Downloads')))
        self.cookie_browser=tk.StringVar(value=self.settings.get('cookie_browser','None'))
        self.want_mp3=tk.BooleanVar(value=self.settings.get('want_mp3',True)); self.want_mp4=tk.BooleanVar(value=self.settings.get('want_mp4',False))
        self.mp3_quality=tk.StringVar(value=self.settings.get('mp3_quality','192')); self.mp4_resolution=tk.StringVar(value=self.settings.get('mp4_resolution','1080'))
        self.embed_thumb=tk.BooleanVar(value=self.settings.get('embed_thumb',True)); self.embed_metadata=tk.BooleanVar(value=self.settings.get('embed_metadata',True)); self.skip_duplicates=tk.BooleanVar(value=self.settings.get('skip_duplicates',True))
        self.status=tk.StringVar(value='Ready'); self.progress=tk.DoubleVar(value=0); self.current_file=tk.StringVar(value=''); self.runtime_status=tk.StringVar(value='Checking runtime…'); self.auth_status=tk.StringVar(value='Authentication: not tested')
        self.items=[]; self.tree_to_index={}; self._style(); self._ui(); self.protocol('WM_DELETE_WINDOW',self._on_close); self.after(200,self.refresh_runtime_status); self.after(100,self._pump)

    def _style(self):
        s=ttk.Style(self)
        try:s.theme_use('clam')
        except:pass
        s.configure('.',background='#0d1422',foreground='#eef6ff',font=('Segoe UI',10)); s.configure('TFrame',background='#0d1422'); s.configure('Panel.TFrame',background='#162238')
        s.configure('TLabel',background='#0d1422',foreground='#eef6ff'); s.configure('Panel.TLabel',background='#162238',foreground='#eef6ff'); s.configure('Title.TLabel',background='#0d1422',foreground='#66e0d0',font=('Segoe UI Semibold',24)); s.configure('Muted.TLabel',background='#0d1422',foreground='#9eb0cc')
        s.configure('TButton',padding=7); s.configure('Accent.TButton',padding=9,font=('Segoe UI Semibold',10)); s.configure('TCheckbutton',background='#162238',foreground='#eef6ff')
        s.configure('Treeview',background='#0a1020',fieldbackground='#0a1020',foreground='#e8f0ff',rowheight=26); s.configure('Treeview.Heading',background='#22314c',foreground='#fff',font=('Segoe UI Semibold',9)); s.map('Treeview',background=[('selected','#2b5d7e')]); s.configure('Horizontal.TProgressbar',troughcolor='#22314c',background='#66e0d0')

    def _ui(self):
        o=ttk.Frame(self,padding=18); o.pack(fill='both',expand=True)
        ttk.Label(o,text=APP_NAME,style='Title.TLabel').pack(anchor='w'); ttk.Label(o,text=f'Authorised Media Utility • Version {VERSION} • {APP_DATE} • {AUTHOR}',style='Muted.TLabel').pack(anchor='w',pady=(2,10))
        tk.Label(o,text='AUTHORISED USE NOTICE — Use only with media you own, created, are licensed to use, or are otherwise authorised to access and download. Browser-cookie support is only for content you are legitimately entitled to access. Media Utility does not bypass DRM or technical access controls.',bg='#3b2432',fg='#ffd6df',justify='left',wraplength=1180,padx=10,pady=8,font=('Segoe UI',9)).pack(fill='x',pady=(0,10))
        nb=ttk.Notebook(o); nb.pack(fill='both',expand=True); self.dtab=ttk.Frame(nb,padding=12); self.htab=ttk.Frame(nb,padding=12); nb.add(self.dtab,text='Download / Library'); nb.add(self.htab,text='History'); self._download_tab(); self._history_tab()

    def _download_tab(self):
        top=ttk.Frame(self.dtab,style='Panel.TFrame',padding=12); top.pack(fill='x')
        ttk.Label(top,text='URL(s), playlist or channel URL',style='Panel.TLabel').grid(row=0,column=0,columnspan=6,sticky='w')
        self.links=tk.Text(top,height=4,bg='#09111f',fg='#eaf3ff',insertbackground='white',font=('Consolas',10),relief='flat',padx=8,pady=8); self.links.grid(row=1,column=0,columnspan=6,sticky='ew',pady=(4,10))
        ttk.Label(top,text='Destination',style='Panel.TLabel').grid(row=2,column=0,sticky='w'); tk.Entry(top,textvariable=self.destination,bg='#09111f',fg='#eaf3ff',insertbackground='white',relief='flat',font=('Segoe UI',10)).grid(row=3,column=0,columnspan=4,sticky='ew',padx=(0,6),ipady=6)
        ttk.Button(top,text='Browse…',command=self._browse).grid(row=3,column=4,sticky='ew'); ttk.Button(top,text='Scan / Load Library',style='Accent.TButton',command=self.scan).grid(row=3,column=5,sticky='ew',padx=(8,0))
        ttk.Label(top,text='Browser cookies',style='Panel.TLabel').grid(row=4,column=0,sticky='w',pady=(12,2)); ttk.Combobox(top,textvariable=self.cookie_browser,state='readonly',values=['None','Chrome','Edge','Firefox','Brave','Opera','Vivaldi'],width=15).grid(row=5,column=0,sticky='w')
        ttk.Label(top,text='MP3 quality',style='Panel.TLabel').grid(row=4,column=1,sticky='w',pady=(12,2)); qf=ttk.Frame(top,style='Panel.TFrame'); qf.grid(row=5,column=1,sticky='w'); ttk.Checkbutton(qf,text='MP3',variable=self.want_mp3).pack(side='left'); ttk.Combobox(qf,textvariable=self.mp3_quality,state='readonly',values=['128','160','192','256','320'],width=6).pack(side='left',padx=4)
        ttk.Label(top,text='MP4 max resolution',style='Panel.TLabel').grid(row=4,column=2,sticky='w',pady=(12,2)); vf=ttk.Frame(top,style='Panel.TFrame'); vf.grid(row=5,column=2,sticky='w'); ttk.Checkbutton(vf,text='MP4',variable=self.want_mp4).pack(side='left'); ttk.Combobox(vf,textvariable=self.mp4_resolution,state='readonly',values=['Best','2160','1440','1080','720','480','360'],width=7).pack(side='left',padx=4)
        opts=ttk.Frame(top,style='Panel.TFrame'); opts.grid(row=5,column=3,columnspan=3,sticky='w'); ttk.Checkbutton(opts,text='Thumbnail',variable=self.embed_thumb).pack(side='left',padx=(0,8)); ttk.Checkbutton(opts,text='Metadata',variable=self.embed_metadata).pack(side='left',padx=(0,8)); ttk.Checkbutton(opts,text='Skip duplicates',variable=self.skip_duplicates).pack(side='left')
        runtime=ttk.Frame(top,style='Panel.TFrame'); runtime.grid(row=6,column=0,columnspan=6,sticky='ew',pady=(12,0))
        ttk.Label(runtime,textvariable=self.runtime_status,style='Panel.TLabel').pack(side='left')
        ttk.Label(runtime,text='  |  ',style='Panel.TLabel').pack(side='left')
        ttk.Label(runtime,textvariable=self.auth_status,style='Panel.TLabel').pack(side='left')
        ttk.Button(runtime,text='Refresh Runtime',command=self.refresh_runtime_status).pack(side='right')
        ttk.Button(runtime,text='Test YouTube Auth',command=self.test_youtube_auth).pack(side='right',padx=(0,6))
        for i in range(6): top.columnconfigure(i,weight=1 if i<4 else 0)
        bar=ttk.Frame(self.dtab); bar.pack(fill='x',pady=(10,5)); ttk.Button(bar,text='Select all',command=lambda:self._set_all(True)).pack(side='left'); ttk.Button(bar,text='Select none',command=lambda:self._set_all(False)).pack(side='left',padx=5); ttk.Button(bar,text='Invert',command=self._invert).pack(side='left'); ttk.Label(bar,text='Double-click a row to toggle selection.',style='Muted.TLabel').pack(side='left',padx=12); self.count_label=ttk.Label(bar,text='0 items',style='Muted.TLabel'); self.count_label.pack(side='right')
        cols=('sel','status','source','title','duration','date','id'); self.tree=ttk.Treeview(self.dtab,columns=cols,show='headings',selectmode='browse'); widths={'sel':55,'status':110,'source':85,'title':510,'duration':75,'date':95,'id':130}; heads={'sel':'Pick','status':'Status','source':'Source','title':'Title','duration':'Duration','date':'Date','id':'Media ID'}
        for c in cols: self.tree.heading(c,text=heads[c]); self.tree.column(c,width=widths[c],stretch=(c=='title'))
        self.tree.pack(fill='both',expand=True); self.tree.bind('<Double-1>',self._toggle_row)
        ctl=ttk.Frame(self.dtab); ctl.pack(fill='x',pady=(8,0)); self.download_btn=ttk.Button(ctl,text='▶ Download Selected',style='Accent.TButton',command=self.start_download); self.download_btn.pack(side='left'); self.pause_btn=ttk.Button(ctl,text='Pause after current file',command=self.toggle_pause,state='disabled'); self.pause_btn.pack(side='left',padx=5); self.stop_btn=ttk.Button(ctl,text='Stop after current file',command=self.stop,state='disabled'); self.stop_btn.pack(side='left'); ttk.Button(ctl,text='Reset list',command=self.reset_list).pack(side='right')
        st=ttk.Frame(self.dtab); st.pack(fill='x',pady=(8,3)); ttk.Label(st,textvariable=self.status).pack(side='left'); ttk.Progressbar(st,variable=self.progress,maximum=100).pack(side='right',fill='x',expand=True,padx=(12,0)); ttk.Label(self.dtab,textvariable=self.current_file,style='Muted.TLabel').pack(anchor='w')
        self.log=tk.Text(self.dtab,height=9,bg='#080e18',fg='#d7ecff',relief='flat',font=('Consolas',9),state='disabled',padx=8,pady=8); self.log.pack(fill='x',pady=(4,0))

    def _history_tab(self):
        b=ttk.Frame(self.htab); b.pack(fill='x',pady=(0,8)); ttk.Label(b,text='Persistent duplicate/download history',style='Muted.TLabel').pack(side='left'); ttk.Button(b,text='Reset Duplicate History',command=self.reset_history).pack(side='right'); ttk.Button(b,text='Refresh',command=self.refresh_history).pack(side='right',padx=5)
        cols=('when','format','source','title','id','path'); self.hist_tree=ttk.Treeview(self.htab,columns=cols,show='headings'); heads={'when':'Downloaded','format':'Format','source':'Source','title':'Title','id':'Media ID','path':'Output'}; widths={'when':150,'format':70,'source':90,'title':360,'id':130,'path':380}
        for c in cols: self.hist_tree.heading(c,text=heads[c]); self.hist_tree.column(c,width=widths[c],stretch=(c in ('title','path')))
        self.hist_tree.pack(fill='both',expand=True); self.refresh_history()

    def emit(self,k,v): self.events.put((k,v))
    def _pump(self):
        try:
            while True:
                k,v=self.events.get_nowait()
                if k=='log': self.log.config(state='normal'); self.log.insert('end',str(v).rstrip()+'\n'); self.log.see('end'); self.log.config(state='disabled')
                elif k=='status': self.status.set(str(v))
                elif k=='progress': self.progress.set(float(v))
                elif k=='current': self.current_file.set(str(v))
                elif k=='scan_done': self._apply_scanned(v)
                elif k=='download_done': self.download_btn.config(state='normal'); self.pause_btn.config(state='disabled'); self.stop_btn.config(state='disabled'); self.refresh_history(); self.status.set(str(v)); self.progress.set(0)
                elif k=='row_status': self._row_status(v[0],v[1])
                elif k=='auth_result':
                    ok,msg=v
                    self.auth_status.set(msg)
                    if not ok:
                        messagebox.showwarning('YouTube authentication', msg)
        except queue.Empty: pass
        self.after(100,self._pump)
    def _log(self,m): self.emit('log',m)

    def _on_close(self):
        save_json(SETTINGS_FILE,{'destination':self.destination.get(),'cookie_browser':self.cookie_browser.get(),'want_mp3':self.want_mp3.get(),'want_mp4':self.want_mp4.get(),'mp3_quality':self.mp3_quality.get(),'mp4_resolution':self.mp4_resolution.get(),'embed_thumb':self.embed_thumb.get(),'embed_metadata':self.embed_metadata.get(),'skip_duplicates':self.skip_duplicates.get()}); self.destroy()
    def _browse(self):
        p=filedialog.askdirectory(initialdir=self.destination.get() or str(Path.home()));
        if p:self.destination.set(p)
    def cookie_option(self):
        b=self.cookie_browser.get().strip().lower(); return None if b=='none' else (b,)


    def runtime_options(self):
        deno=find_deno()
        if deno:
            return {'js_runtimes': {'deno': {'path': deno}}}
        # yt-dlp defaults to deno, but leaving this unset lets it report a useful warning.
        return {}

    def refresh_runtime_status(self):
        deno=find_deno()
        dver=deno_version(deno)
        ff=ffmpeg_path()
        cookie=self.cookie_browser.get()
        parts=[f"yt-dlp {ytdlp_version()}"]
        parts.append(dver if dver else "Deno: NOT FOUND")
        parts.append("FFmpeg: OK" if ff else "FFmpeg: NOT FOUND")
        parts.append(f"Cookies: {cookie}")
        self.runtime_status.set("  •  ".join(parts))

    def _youtube_common_opts(self):
        opts={}
        opts.update(self.runtime_options())
        cookie=self.cookie_option()
        if cookie:
            opts['cookiesfrombrowser']=cookie
        return opts

    def test_youtube_auth(self):
        urls=clean_links(self.links.get('1.0','end'))
        url=next((u for u in urls if detect_platform(u)=='YouTube'), None)
        if not url:
            messagebox.showinfo('Test YouTube Auth','Enter at least one YouTube video, playlist, or channel URL first.')
            return
        self.auth_status.set('Authentication: testing…')
        self._log(f"AUTH TEST | YouTube | Browser cookies={self.cookie_browser.get()} | URL={url}")
        threading.Thread(target=self._test_youtube_auth_worker,args=(url,),daemon=True).start()

    def _test_youtube_auth_worker(self,url):
        opts={
            'quiet':True,
            'no_warnings':False,
            'skip_download':True,
            'noplaylist':True,
            'extract_flat':False,
        }
        opts.update(self._youtube_common_opts())
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info=ydl.extract_info(url,download=False)
            title=(info or {}).get('title') or '(title unavailable)'
            msg=f"Authentication test passed • {self.cookie_browser.get()} • {title}"
            self._log("AUTH TEST PASSED | "+msg)
            self.emit('auth_result',(True,msg))
        except Exception as e:
            kind=youtube_error_kind(e)
            if kind=='auth':
                browser=self.cookie_browser.get()
                msg=("YouTube requires sign-in/anti-bot authentication. "
                     + ("Select the browser where you are already signed into YouTube, then retry."
                        if browser=='None' else f"Cookies from {browser} were selected but YouTube still rejected the request. Try refreshing your YouTube login/session or another supported browser such as Firefox."))
            elif kind=='runtime':
                msg="A supported JavaScript runtime is missing. Install/repair Deno and use Refresh Runtime."
            else:
                msg=f"YouTube authentication test failed: {e}"
            self._log("AUTH TEST FAILED | "+msg)
            self.emit('auth_result',(False,msg))

    def scan(self):
        urls=clean_links(self.links.get('1.0','end'))
        if not urls: messagebox.showwarning(APP_NAME,'Enter at least one URL.'); return
        self.status.set('Scanning URLs / loading library…'); self.progress.set(0); self._log('='*90); self._log('SCAN STARTED'); threading.Thread(target=self._scan_worker,args=(urls,),daemon=True).start()
    def _scan_worker(self,urls):
        collected=[]
        for n,url in enumerate(urls,1):
            self._log(f'[SCAN {n}/{len(urls)}] {url}'); opts={'quiet':True,'no_warnings':False,'extract_flat':'in_playlist','skip_download':True,'ignoreerrors':True,'lazy_playlist':False}
            opts.update(self.runtime_options())
            cookie=self.cookie_option();
            if cookie: opts['cookiesfrombrowser']=cookie
            try:
                with yt_dlp.YoutubeDL(opts) as ydl: info=ydl.extract_info(url,download=False)
                if not info: self._log('  No information returned.'); continue
                entries=info.get('entries')
                if entries:
                    entries=list(entries); self._log(f'  Library/playlist detected: {len(entries)} item(s)')
                    for e in entries:
                        if not e: continue
                        iu=e.get('webpage_url') or e.get('url'); ext=(info.get('extractor') or '').lower()
                        if iu and not str(iu).startswith('http') and ('youtube' in ext or info.get('extractor_key')=='YoutubeTab'): iu=f"https://www.youtube.com/watch?v={e.get('id')}"
                        collected.append({'selected':True,'status':'Ready','platform':detect_platform(iu or url),'title':e.get('title') or e.get('id') or 'Untitled','duration':e.get('duration'),'upload_date':e.get('upload_date') or '','id':e.get('id') or '','url':iu or url,'extractor':e.get('extractor') or info.get('extractor') or '','extractor_key':e.get('extractor_key') or info.get('extractor_key') or '','uploader':e.get('uploader') or info.get('uploader') or info.get('channel') or '','collection':info.get('title') or info.get('playlist_title') or 'Library'})
                else:
                    collected.append({'selected':True,'status':'Ready','platform':detect_platform(info.get('webpage_url') or url),'title':info.get('title') or 'Untitled','duration':info.get('duration'),'upload_date':info.get('upload_date') or '','id':info.get('id') or '','url':info.get('webpage_url') or url,'extractor':info.get('extractor') or '','extractor_key':info.get('extractor_key') or '','uploader':info.get('uploader') or info.get('channel') or '','collection':'Singles'})
            except Exception as e:
                kind=youtube_error_kind(e) if detect_platform(url)=='YouTube' else None
                if kind=='auth':
                    self._log(f"  AUTH REQUIRED: YouTube requested sign-in/anti-bot verification. Current browser cookies: {self.cookie_browser.get()}.")
                    self.emit('auth_result',(False,"YouTube requested sign-in/anti-bot verification. Select the browser where you are signed into YouTube and retry Scan / Load Library."))
                elif kind=='runtime':
                    self._log("  RUNTIME REQUIRED: YouTube needs a supported JavaScript runtime. Deno is recommended.")
                else:
                    self._log(f'  Scan failed: {e}')
        self.emit('scan_done',collected)

    def _tree_values(self,it):
        d=it.get('upload_date',''); d=f'{d[:4]}-{d[4:6]}-{d[6:]}' if len(d)==8 else d
        return ('✓' if it.get('selected') else '',it.get('status','Ready'),it.get('platform',''),it.get('title',''),duration_text(it.get('duration')),d,it.get('id',''))
    def _apply_scanned(self,items):
        self.items=items
        for x in self.tree.get_children(): self.tree.delete(x)
        self.tree_to_index.clear()
        for i,it in enumerate(items): self.tree_to_index[self.tree.insert('', 'end',values=self._tree_values(it))]=i
        self._update_count(); self.status.set(f'Scan complete: {len(items)} item(s) loaded.'); self._log(f'SCAN COMPLETE: {len(items)} item(s) loaded.'); self._mark_known_duplicates()
    def _toggle_row(self,event=None):
        iid=self.tree.focus()
        if iid in self.tree_to_index:
            i=self.tree_to_index[iid]; self.items[i]['selected']=not self.items[i].get('selected',True); self.tree.item(iid,values=self._tree_values(self.items[i])); self._update_count()
    def _set_all(self,v):
        for it in self.items: it['selected']=v
        self._refresh_tree(); self._update_count()
    def _invert(self):
        for it in self.items: it['selected']=not it.get('selected',True)
        self._refresh_tree(); self._update_count()
    def _refresh_tree(self):
        for iid,i in self.tree_to_index.items(): self.tree.item(iid,values=self._tree_values(self.items[i]))
    def _update_count(self): self.count_label.config(text=f"{sum(1 for x in self.items if x.get('selected'))} selected / {len(self.items)} loaded")
    def _row_status(self,i,text):
        if 0<=i<len(self.items):
            self.items[i]['status']=text
            for iid,n in self.tree_to_index.items():
                if n==i: self.tree.item(iid,values=self._tree_values(self.items[i])); break
    def _mark_known_duplicates(self):
        fmts=(['mp3'] if self.want_mp3.get() else [])+(['mp4'] if self.want_mp4.get() else [])
        for it in self.items:
            if fmts and all(history_key(it,f) in self.history for f in fmts): it['status']='Downloaded'
        self._refresh_tree()
    def reset_list(self):
        self.items=[]; self.tree_to_index.clear()
        for x in self.tree.get_children(): self.tree.delete(x)
        self._update_count(); self.status.set('List reset.')

    def refresh_history(self):
        for x in self.hist_tree.get_children(): self.hist_tree.delete(x)
        for r in sorted(self.history.values(),key=lambda x:x.get('downloaded_at',''),reverse=True): self.hist_tree.insert('', 'end',values=(r.get('downloaded_at',''),r.get('format','').upper(),r.get('source',''),r.get('title',''),r.get('id',''),r.get('path','')))
    def reset_history(self):
        if messagebox.askyesno('Reset duplicate history','Clear all stored duplicate/download history?\n\nThis does not delete downloaded media files.'):
            self.history={}; save_json(HISTORY_FILE,self.history); self.refresh_history(); self._mark_known_duplicates(); self.status.set('Duplicate history reset.')

    def start_download(self):
        selected=[(i,x) for i,x in enumerate(self.items) if x.get('selected')]
        if not selected: messagebox.showwarning(APP_NAME,'Scan a URL and select at least one item.'); return
        if not (self.want_mp3.get() or self.want_mp4.get()): messagebox.showwarning(APP_NAME,'Select MP3, MP4, or both.'); return
        try: Path(self.destination.get()).mkdir(parents=True,exist_ok=True)
        except Exception as e: messagebox.showerror(APP_NAME,f'Destination cannot be created:\n{e}'); return
        self.stop_requested=False; self.pause_requested=False; self.download_btn.config(state='disabled'); self.pause_btn.config(state='normal',text='Pause after current file'); self.stop_btn.config(state='normal'); self._log('='*90); self._log(f'DOWNLOAD SESSION STARTED — {len(selected)} selected media item(s)'); self._log(f'Destination: {self.destination.get()}'); threading.Thread(target=self._download_worker,args=(selected,),daemon=True).start()
    def toggle_pause(self):
        self.pause_requested=not self.pause_requested; self.pause_btn.config(text='Resume queue' if self.pause_requested else 'Pause after current file'); self.status.set('Pause requested — queue pauses after current file.' if self.pause_requested else 'Queue resumed.')
    def stop(self): self.stop_requested=True; self.status.set('Stop requested — stopping after current file.'); self._log('STOP REQUESTED: current operation will be allowed to finish.')
    def _wait_if_paused(self):
        while self.pause_requested and not self.stop_requested: self.emit('status','Queue paused.'); time.sleep(.3)
    def _progress_hook_factory(self,item,fmt):
        last_bucket={'value':-1}
        def hook(d):
            if d.get('status')=='downloading':
                pct=re.sub(r'\x1b\[[0-9;]*m','',d.get('_percent_str','')).strip(); speed=re.sub(r'\x1b\[[0-9;]*m','',d.get('_speed_str','')).strip(); eta=re.sub(r'\x1b\[[0-9;]*m','',d.get('_eta_str','')).strip()
                try:
                    value=float(pct.replace('%','').strip())
                    self.emit('progress',value)
                    bucket=int(value//5)*5
                    if bucket!=last_bucket['value']:
                        last_bucket['value']=bucket
                        self._log(f"    PROGRESS | {fmt.upper()} | {value:.1f}% | Speed={speed or 'n/a'} | ETA={eta or 'n/a'} | ID={item.get('id','')} | {item.get('title','')}")
                except: pass
                self.emit('current',f"{fmt.upper()} • {item.get('title','')} • {pct} • {speed} • ETA {eta}"); self.emit('status',f"{pct} — {item.get('title','')}")
            elif d.get('status')=='finished':
                self.emit('progress',100)
                self._log(f"    PROGRESS | {fmt.upper()} | 100% | ID={item.get('id','')} | {item.get('title','')}")
                self._log(f"    Downloaded source file: {d.get('filename','')}")
        return hook
    def _base_opts(self,item,fmt):
        output=str(Path(self.destination.get())/'%(extractor_key|source)s'/'%(uploader|channel|Unknown)s'/'%(playlist_title|Singles)s'/'%(title).180B [%(id)s].%(ext)s')
        opts={'outtmpl':output,'windowsfilenames':True,'continuedl':True,'retries':10,'fragment_retries':10,'ignoreerrors':False,'quiet':True,'no_warnings':False,'overwrites':False,'progress_hooks':[self._progress_hook_factory(item,fmt)]}; opts.update(self.runtime_options())
        fp=ffmpeg_path();
        if fp: opts['ffmpeg_location']=fp
        cookie=self.cookie_option();
        if cookie: opts['cookiesfrombrowser']=cookie
        post=[]
        if self.embed_metadata.get(): post.append({'key':'FFmpegMetadata'})
        if self.embed_thumb.get(): opts['writethumbnail']=True; post.append({'key':'EmbedThumbnail','already_have_thumbnail':False})
        if fmt=='mp3': opts['format']='bestaudio/best'; post.insert(0,{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':self.mp3_quality.get()})
        else:
            r=self.mp4_resolution.get(); opts['format']='bestvideo+bestaudio/best' if r=='Best' else f'bestvideo[height<={r}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={r}]+bestaudio/best[height<={r}][ext=mp4]/best[height<={r}]/best'; opts['merge_output_format']='mp4'
        if post: opts['postprocessors']=post
        return opts
    def _record_history(self,item,fmt,path=''):
        self.history[history_key(item,fmt)]={'downloaded_at':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'format':fmt,'source':item.get('platform',''),'title':item.get('title',''),'id':item.get('id',''),'url':item.get('url',''),'path':path}; save_json(HISTORY_FILE,self.history)
    def _download_worker(self,selected):
        fmts=(['mp3'] if self.want_mp3.get() else [])+(['mp4'] if self.want_mp4.get() else []); jobs=[(i,it,f) for i,it in selected for f in fmts]; completed=skipped=failed=0
        for n,(idx,it,fmt) in enumerate(jobs,1):
            if self.stop_requested: break
            self._wait_if_paused()
            if self.stop_requested: break
            if history_key(it,fmt) in self.history and self.skip_duplicates.get(): skipped+=1; self._log(f"[{n}/{len(jobs)}] SKIP DUPLICATE | {fmt.upper()} | {it.get('platform','')} | ID={it.get('id','')} | {it.get('title','')}"); self.emit('row_status',(idx,'Duplicate')); continue
            self.emit('row_status',(idx,f'Downloading {fmt.upper()}')); self.emit('progress',0); self._log(f"[{n}/{len(jobs)}] START | {fmt.upper()} | Source={it.get('platform','')} | ID={it.get('id','')} | Duration={duration_text(it.get('duration'))} | Title={it.get('title','')}"); self._log(f"    URL: {it.get('url','')}")
            try:
                with yt_dlp.YoutubeDL(self._base_opts(it,fmt)) as ydl:
                    result=ydl.extract_info(it.get('url'),download=True)
                    try:path=ydl.prepare_filename(result)
                    except:path=''
                self._record_history(it,fmt,path); completed+=1; self.emit('row_status',(idx,'Downloaded')); self._log(f"    COMPLETE | {fmt.upper()} | 100% | {it.get('title','')}")
            except Exception as e:
                failed+=1
                kind=youtube_error_kind(e) if it.get('platform')=='YouTube' else None
                if kind=='auth':
                    self.emit('row_status',(idx,'Auth required'))
                    self._log(f"    AUTH REQUIRED | {fmt.upper()} | {it.get('title','')} | YouTube requested sign-in/anti-bot verification. Browser={self.cookie_browser.get()}")
                    self.emit('auth_result',(False,"YouTube requested sign-in/anti-bot verification. Select the browser where you are already signed into YouTube, then retry this item."))
                elif kind=='runtime':
                    self.emit('row_status',(idx,'Runtime required'))
                    self._log(f"    RUNTIME REQUIRED | {fmt.upper()} | {it.get('title','')} | Install/repair Deno.")
                else:
                    self.emit('row_status',(idx,'Failed'))
                    self._log(f"    FAILED | {fmt.upper()} | {it.get('title','')} | {e}")
        s=f'Finished: {completed} completed, {skipped} duplicate(s) skipped, {failed} failed.'; s=('Stopped. '+s) if self.stop_requested else s; self._log(s); self.emit('download_done',s)

if __name__=='__main__': App().mainloop()
